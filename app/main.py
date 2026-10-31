from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.session_store import SESSIONS, new_session_id, get_session, destroy_session
from app.drive_service import DriveService, DriveAPIError

BASE_DIR = Path(__file__).resolve().parent

oauth = OAuth()
if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile https://www.googleapis.com/auth/drive.file",
            "code_challenge_method": "S256",
        },
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.cookie_secure,
    max_age=60 * 60 * 8,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

class DocumentCreate(BaseModel):
    data: dict[str, Any]

class DocumentPatch(BaseModel):
    data: dict[str, Any]

def get_user(request: Request) -> dict:
    sid = request.cookies.get("drivedb_session")
    session = get_session(sid)
    if not session or not session.get("access_token"):
        raise HTTPException(status_code=401, detail="Please sign in with Google.")
    return session

async def get_drive(user: dict = Depends(get_user)) -> DriveService:
    return DriveService(user["access_token"])

async def ensure_root(drive: DriveService) -> str:
    root = await drive.ensure_root()
    return root["id"]

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    sid = request.cookies.get("drivedb_session")
    session = get_session(sid)
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={"app_name": settings.app_name, "user": session.get("user") if session else None}
    )

@app.get("/auth/login")
async def login(request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        return RedirectResponse(url="/?auth_config=missing", status_code=303)
    redirect_uri = f"{settings.base_url}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri, prompt="select_account")

@app.get("/auth/callback")
async def auth_callback(request: Request):
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth is not configured.")
    try:
        token = await oauth.google.authorize_access_token(request)
        async with httpx.AsyncClient(timeout=15) as client:
            profile_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"}
            )
            profile_response.raise_for_status()
            profile = profile_response.json()
    except Exception as exc:
        return RedirectResponse(url="/?auth_error=login_failed", status_code=303)

    sid = new_session_id()
    SESSIONS[sid] = {
        "access_token": token["access_token"],
        "refresh_token": token.get("refresh_token"),
        "expires_at": token.get("expires_at"),
        "user": {
            "id": profile.get("id"),
            "name": profile.get("name", "Google user"),
            "email": profile.get("email"),
            "picture": profile.get("picture"),
        },
    }
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        "drivedb_session", sid, httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=60 * 60 * 8, path="/"
    )
    return response

@app.post("/auth/logout")
async def logout(request: Request):
    sid = request.cookies.get("drivedb_session")
    destroy_session(sid)
    request.session.clear()
    response = JSONResponse({"ok": True})
    response.delete_cookie("drivedb_session", path="/")
    return response

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}

@app.get("/api/me")
async def me(user: dict = Depends(get_user)):
    return {"authenticated": True, "user": user["user"]}

@app.get("/api/collections")
async def list_collections(drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        return {"items": await drive.list_collections(root_id)}
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()

@app.post("/api/collections")
async def create_collection(payload: CollectionCreate, drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        folder = await drive.ensure_collection(root_id, payload.name)
        return folder
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()

@app.get("/api/collections/{name}/documents")
async def list_documents(name: str, drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        collection = await drive.find_folder(drive.validate_name(name), root_id)
        if not collection:
            return {"items": []}
        return {"items": await drive.list_documents(collection["id"])}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()

@app.post("/api/collections/{name}/documents")
async def create_document(name: str, payload: DocumentCreate, drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        collection = await drive.ensure_collection(root_id, name)
        return await drive.create_document(collection["id"], payload.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()

@app.get("/api/collections/{name}/documents/{document_id}")
async def read_document(name: str, document_id: str, drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        collection = await drive.find_folder(drive.validate_name(name), root_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found.")
        # Verify the file belongs to the requested collection before reading.
        metadata = await drive._request("GET", f"https://www.googleapis.com/drive/v3/files/{document_id}", params={"fields": "id,parents,mimeType,name"})
        if collection["id"] not in metadata.get("parents", []):
            raise HTTPException(status_code=404, detail="Document not found in this collection.")
        return await drive.read_document(document_id)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()

@app.patch("/api/collections/{name}/documents/{document_id}")
async def patch_document(name: str, document_id: str, payload: DocumentPatch, drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        collection = await drive.find_folder(drive.validate_name(name), root_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found.")
        metadata = await drive._request("GET", f"https://www.googleapis.com/drive/v3/files/{document_id}", params={"fields": "id,parents,mimeType"})
        if collection["id"] not in metadata.get("parents", []):
            raise HTTPException(status_code=404, detail="Document not found in this collection.")
        current = await drive.read_document(document_id)
        if not isinstance(current.get("data"), dict):
            raise HTTPException(status_code=400, detail="Document is not a JSON object.")
        merged = {**current["data"], **payload.data}
        return await drive.update_document(document_id, merged)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()

@app.delete("/api/collections/{name}/documents/{document_id}")
async def delete_document(name: str, document_id: str, drive: DriveService = Depends(get_drive)):
    try:
        root_id = await ensure_root(drive)
        collection = await drive.find_folder(drive.validate_name(name), root_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found.")
        metadata = await drive._request("GET", f"https://www.googleapis.com/drive/v3/files/{document_id}", params={"fields": "id,parents"})
        if collection["id"] not in metadata.get("parents", []):
            raise HTTPException(status_code=404, detail="Document not found in this collection.")
        await drive.delete_document(document_id)
        return {"ok": True, "id": document_id}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except DriveAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    finally:
        await drive.close()
