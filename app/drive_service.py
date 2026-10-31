import json
from typing import Any
import httpx

API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"

class DriveAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)

class DriveService:
    def __init__(self, access_token: str):
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    async def close(self):
        await self.client.aclose()

    async def _request(self, method: str, url: str, **kwargs):
        response = await self.client.request(method, url, **kwargs)
        if response.is_error:
            try:
                detail = response.json().get("error", {}).get("message", response.text)
            except Exception:
                detail = response.text
            raise DriveAPIError(response.status_code, str(detail))
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    async def list_files(self, q: str, page_size: int = 100, fields: str = "files(id,name,mimeType,modifiedTime,webViewLink)"):
        return await self._request("GET", f"{API}/files", params={
            "q": q, "pageSize": min(page_size, 1000), "orderBy": "name",
            "fields": f"{fields},nextPageToken"
        })

    async def find_folder(self, name: str, parent_id: str | None = None):
        q = "mimeType='application/vnd.google-apps.folder' and name='" + name.replace("'", "\\'") + "' and trashed=false"
        if parent_id:
            q += f" and '{parent_id}' in parents"
        result = await self.list_files(q, page_size=100, fields="files(id,name,mimeType)")
        return result.get("files", [None])[0]

    async def create_folder(self, name: str, parent_id: str | None = None):
        body: dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        return await self._request("POST", f"{API}/files", json=body, params={"fields": "id,name,mimeType"})

    async def ensure_root(self):
        folder = await self.find_folder("DriveDB")
        return folder or await self.create_folder("DriveDB")

    async def ensure_collection(self, root_id: str, name: str):
        safe_name = self.validate_name(name)
        folder = await self.find_folder(safe_name, root_id)
        return folder or await self.create_folder(safe_name, root_id)

    @staticmethod
    def validate_name(name: str) -> str:
        name = name.strip()
        if not name or len(name) > 80 or any(c in name for c in ("/", "\\", "\x00")):
            raise ValueError("Name must be 1–80 characters and cannot contain slashes.")
        return name

    async def list_collections(self, root_id: str):
        result = await self.list_files(
            f"'{root_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id,name,mimeType,modifiedTime)"
        )
        return result.get("files", [])

    async def list_documents(self, collection_id: str):
        result = await self.list_files(
            f"'{collection_id}' in parents and mimeType='application/json' and trashed=false",
            fields="files(id,name,mimeType,modifiedTime,webViewLink)"
        )
        docs = []
        for item in result.get("files", []):
            docs.append({
                "id": item["id"], "name": item["name"],
                "modifiedTime": item.get("modifiedTime"),
                "webViewLink": item.get("webViewLink")
            })
        return docs

    async def create_document(self, collection_id: str, data: dict[str, Any]):
        import uuid
        doc_id = uuid.uuid4().hex
        name = f"{doc_id}.json"
        metadata = {"name": name, "mimeType": "application/json", "parents": [collection_id]}
        content = json.dumps(data, ensure_ascii=False, indent=2)
        response = await self.client.post(
            f"{UPLOAD_API}/files",
            params={"uploadType": "multipart", "fields": "id,name,mimeType,modifiedTime"},
            files={
                "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
                "file": (name, content.encode("utf-8"), "application/json")
            }
        )
        if response.is_error:
            try: detail = response.json().get("error", {}).get("message", response.text)
            except Exception: detail = response.text
            raise DriveAPIError(response.status_code, str(detail))
        return response.json()

    async def read_document(self, file_id: str):
        meta = await self._request("GET", f"{API}/files/{file_id}", params={"fields": "id,name,mimeType,parents"})
        content = await self._request("GET", f"{API}/files/{file_id}", params={"alt": "media"})
        # Drive media responses may be JSON or a raw JSON response; httpx JSON parsing handles JSON.
        if isinstance(content, dict):
            return {"metadata": meta, "data": content}
        return {"metadata": meta, "data": content}

    async def update_document(self, file_id: str, data: dict[str, Any]):
        response = await self.client.patch(
            f"{UPLOAD_API}/files/{file_id}",
            params={"uploadType": "media", "fields": "id,name,modifiedTime"},
            content=json.dumps(data, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        if response.is_error:
            try: detail = response.json().get("error", {}).get("message", response.text)
            except Exception: detail = response.text
            raise DriveAPIError(response.status_code, str(detail))
        return response.json()

    async def delete_document(self, file_id: str):
        return await self._request("DELETE", f"{API}/files/{file_id}")
