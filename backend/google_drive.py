import os
import io
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

from backend.config import Config

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/drive.file'
]

class GoogleDriveManager:
    def __init__(self, credentials_json: Optional[str] = None, default_folder_id: Optional[str] = None):
        self.raw_creds = credentials_json or getattr(Config, "GOOGLE_CREDENTIALS_JSON", "")
        self.default_folder_id = default_folder_id or getattr(Config, "GOOGLE_DRIVE_FOLDER_ID", "1VDrNYA5GE6l9h21D2Co0HuuuD87Ain6d")
        self.service = self._init_service()

    def _init_service(self):
        if not GOOGLE_LIBS_AVAILABLE or not self.raw_creds:
            return None
        try:
            if isinstance(self.raw_creds, dict):
                info = self.raw_creds
            else:
                info = json.loads(self.raw_creds)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds, cache_discovery=False)
        except Exception as e:
            print(f"[Warning] Failed to initialize Google Drive service: {e}")
            return None

    @staticmethod
    def refresh_access_token() -> str:
        """Exchanges refresh_token for a fresh access_token via Google OAuth2."""
        refresh_token = getattr(Config, "GOOGLE_OAUTH_REFRESH_TOKEN", "")
        client_id = getattr(Config, "GOOGLE_OAUTH_CLIENT_ID", "")
        client_secret = getattr(Config, "GOOGLE_OAUTH_CLIENT_SECRET", "")
        if not (refresh_token and client_id and client_secret):
            return ""
        try:
            import requests
            payload = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            }
            r = requests.post('https://oauth2.googleapis.com/token', data=payload, timeout=10)
            if r.ok:
                new_token = r.json().get('access_token', "")
                if new_token:
                    Config.GOOGLE_OAUTH_ACCESS_TOKEN = new_token
                    print(f"[GoogleDrive] Successfully auto-refreshed access_token via permanent refresh_token!")
                    return new_token
            else:
                print(f"[GoogleDrive Auto-Refresh Notice]: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"[GoogleDrive Refresh Exception]: {e}")
        return ""

    @classmethod
    def get_access_token(cls) -> str:
        """Returns active access token, auto-refreshing via permanent refresh_token if needed."""
        token = getattr(Config, "GOOGLE_OAUTH_ACCESS_TOKEN", "")
        if not token:
            token = cls.refresh_access_token()
        return token

    def is_configured(self) -> bool:
        return self.service is not None or bool(self.get_access_token())

    def list_files(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists files inside the designated Google Drive folder."""
        fid = folder_id or self.default_folder_id
        oauth_token = self.get_access_token()
        if oauth_token:
            try:
                import requests
                query = f"'{fid}' in parents and trashed=false" if fid else "trashed=false"
                url = "https://www.googleapis.com/drive/v3/files"
                params = {
                    "q": query,
                    "pageSize": 50,
                    "fields": "files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink)",
                    "orderBy": "createdTime desc",
                    "supportsAllDrives": "true"
                }
                r = requests.get(url, headers={"Authorization": f"Bearer {oauth_token}"}, params=params, timeout=15)
                if r.status_code == 401:
                    new_tok = self.refresh_access_token()
                    if new_tok:
                        r = requests.get(url, headers={"Authorization": f"Bearer {new_tok}"}, params=params, timeout=15)
                if r.ok:
                    return r.json().get('files', [])
            except Exception as e:
                print(f"[GoogleDrive] Error listing files via OAuth: {e}")

        if not self.service:
            return []

        try:
            query = f"'{fid}' in parents and trashed=false" if fid else "trashed=false"
            results = self.service.files().list(
                q=query,
                pageSize=50,
                fields="files(id, name, mimeType, size, createdTime, webViewLink, thumbnailLink)",
                orderBy="createdTime desc"
            ).execute()
            files = results.get('files', [])
            return files
        except Exception as e:
            print(f"[GoogleDrive] Error listing files: {e}")
            return []

    def upload_file(
        self,
        local_path: Path,
        filename: str,
        mime_type: str = "video/mp4",
        folder_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Directly uploads lecture video/audio to Google Drive folder so that
        the Cloud Run server does NOT act as a heavy video hosting server.
        """
        fid = folder_id or self.default_folder_id

        # 1. Primary Strategy: Direct 5TB Admin OAuth Upload (Unlimited quota)
        oauth_token = self.get_access_token()
        if oauth_token and local_path.exists():
            try:
                import requests
                file_size = local_path.stat().st_size
                init_url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true'
                headers = {
                    'Authorization': f'Bearer {oauth_token}',
                    'Content-Type': 'application/json; charset=UTF-8',
                    'X-Upload-Content-Type': mime_type,
                    'X-Upload-Content-Length': str(file_size)
                }
                meta = {
                    'name': filename,
                    'parents': [fid] if fid else []
                }
                r = requests.post(init_url, headers=headers, json=meta, timeout=15)
                if r.status_code == 401:
                    new_tok = self.refresh_access_token()
                    if new_tok:
                        headers['Authorization'] = f'Bearer {new_tok}'
                        r = requests.post(init_url, headers=headers, json=meta, timeout=15)
                if r.status_code == 200 and 'Location' in r.headers:
                    upload_url = r.headers['Location']
                    with open(local_path, 'rb') as f:
                        r_up = requests.put(
                            upload_url,
                            data=f,
                            headers={'Content-Length': str(file_size), 'Content-Type': mime_type},
                            timeout=600
                        )
                    if r_up.status_code in [200, 201]:
                        file_data = r_up.json()
                        file_id = file_data.get("id")
                        print(f"[GoogleDrive] Successfully uploaded {filename} via 5TB Admin OAuth! ID: {file_id}")
                        return {
                            "id": file_id,
                            "name": file_data.get("name"),
                            "mimeType": file_data.get("mimeType"),
                            "size": file_size,
                            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
                            "stream_url": f"https://drive.google.com/file/d/{file_id}/preview"
                        }
            except Exception as oauth_err:
                print(f"[GoogleDrive] OAuth upload exception: {oauth_err}")

        if not self.service:
            print("[GoogleDrive] Service not initialized, cannot upload.")
            return None
        try:
            file_metadata = {
                "name": filename,
                "parents": [fid] if fid else []
            }
            media = MediaFileUpload(
                str(local_path),
                mimetype=mime_type,
                resumable=True
            )
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id, name, mimeType, size, webViewLink, webContentLink"
            ).execute()

            file_id = file.get("id")
            # Try to grant read permission so video can be streamed
            try:
                self.service.permissions().create(
                    fileId=file_id,
                    body={"role": "reader", "type": "anyone"}
                ).execute()
            except Exception as pe:
                print(f"[GoogleDrive] Notice on setting public read permission: {pe}")

            return {
                "id": file_id,
                "name": file.get("name"),
                "mimeType": file.get("mimeType"),
                "size": file.get("size"),
                "webViewLink": file.get("webViewLink"),
                "stream_url": f"https://drive.google.com/file/d/{file_id}/preview",
                "direct_url": f"https://drive.google.com/uc?export=download&id={file_id}"
            }
        except Exception as e:
            print(f"[GoogleDrive] Error uploading file to Google Drive: {e}")
            return None

    def download_file(self, file_id: str, dest_path: Path) -> bool:
        """Streams and downloads a file from Google Drive to local disk for RAG processing."""
        clean_id = self.extract_file_id(file_id)
        oauth_token = getattr(Config, "GOOGLE_OAUTH_ACCESS_TOKEN", "")
        if oauth_token:
            try:
                import requests
                r = requests.get(
                    f"https://www.googleapis.com/drive/v3/files/{clean_id}?alt=media&supportsAllDrives=true",
                    headers={"Authorization": f"Bearer {oauth_token}"},
                    stream=True,
                    timeout=60
                )
                if r.ok:
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024 * 2):
                            if chunk:
                                f.write(chunk)
                    return True
            except Exception as e:
                print(f"[GoogleDrive] Error downloading file via OAuth: {e}")

        if not self.service:
            return False

        try:
            request = self.service.files().get_media(fileId=clean_id)
            with open(dest_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request, chunksize=1024 * 1024 * 4) # 4MB chunks
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        print(f"[GoogleDrive] Ingestion stream {int(status.progress() * 100)}%")
            return True
        except Exception as e:
            print(f"[GoogleDrive] Error streaming file {clean_id}: {e}")
            return False

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        clean_id = self.extract_file_id(file_id)
        oauth_token = self.get_access_token()
        if oauth_token:
            try:
                import requests
                r = requests.get(
                    f"https://www.googleapis.com/drive/v3/files/{clean_id}?fields=id,name,mimeType,size,webViewLink&supportsAllDrives=true",
                    headers={"Authorization": f"Bearer {oauth_token}"},
                    timeout=10
                )
                if r.status_code == 401:
                    new_tok = self.refresh_access_token()
                    if new_tok:
                        r = requests.get(
                            f"https://www.googleapis.com/drive/v3/files/{clean_id}?fields=id,name,mimeType,size,webViewLink&supportsAllDrives=true",
                            headers={"Authorization": f"Bearer {new_tok}"},
                            timeout=10
                        )
                if r.ok:
                    return r.json()
            except Exception as e:
                print(f"[GoogleDrive] Error fetching metadata via OAuth: {e}")

        if not self.service:
            return None
        try:
            return self.service.files().get(fileId=clean_id, fields="id, name, mimeType, size, webViewLink").execute()
        except Exception as e:
            print(f"[GoogleDrive] Error fetching metadata for {clean_id}: {e}")
            return None

    @staticmethod
    def extract_file_id(url_or_id: str) -> str:
        """Extracts Google Drive file ID from URL or raw ID."""
        import re
        if not url_or_id:
            return ""
        clean = url_or_id.strip()
        match = re.search(r'(?:file/d/|id=)([a-zA-Z0-9_-]{20,})', clean)
        if match:
            return match.group(1)
        if len(clean) >= 20 and "/" not in clean and "?" not in clean:
            return clean
        return clean

    def make_file_public_readable(self, file_id: str) -> bool:
        """Makes file readable by anyone with the link so Deepgram can stream directly."""
        clean_id = self.extract_file_id(file_id)
        oauth_token = getattr(Config, "GOOGLE_OAUTH_ACCESS_TOKEN", "")
        if oauth_token:
            try:
                import requests
                r = requests.post(
                    f"https://www.googleapis.com/drive/v3/files/{clean_id}/permissions?supportsAllDrives=true",
                    headers={"Authorization": f"Bearer {oauth_token}"},
                    json={"role": "reader", "type": "anyone"},
                    timeout=10
                )
                if r.ok:
                    return True
            except Exception as e:
                print(f"[GoogleDrive] Permission notice via OAuth: {e}")

        if not self.service:
            return False
        try:
            self.service.permissions().create(
                fileId=clean_id,
                body={"role": "reader", "type": "anyone"}
            ).execute()
            return True
        except Exception as e:
            print(f"[GoogleDrive] Permission notice: {e}")
            return False

    def stream_file_range(self, file_id: str, range_header: Optional[str] = None):
        """
        Fetches metadata and streams byte ranges from Google Drive API without buffering the full file in memory.
        Supports HTTP Range requests (206 Partial Content) and HEAD requests for seeking.
        Returns: (status_code, headers_dict, stream_generator)
        """
        import requests

        clean_id = self.extract_file_id(file_id)
        meta = self.get_file_metadata(clean_id)
        if not meta:
            raise FileNotFoundError(f"File {clean_id} not found in Google Drive.")

        total_size = int(meta.get("size") or 0)
        mime_type = meta.get("mimeType") or "video/mp4"

        # Resolve auth token (OAuth Admin token or Service Account)
        token = self.get_access_token()
        if not token and self.service:
            try:
                import google.auth.transport.requests
                creds = self.service._http.credentials
                auth_req = google.auth.transport.requests.Request()
                creds.refresh(auth_req)
                token = creds.token
            except Exception as e:
                print(f"[GoogleDrive] Creds refresh error: {e}")

        if not token:
            raise RuntimeError("Google Drive credentials not available for streaming.")

        # Parse Range header
        start = 0
        end = total_size - 1 if total_size > 0 else 0
        status_code = 200

        if range_header and range_header.startswith("bytes="):
            range_val = range_header.replace("bytes=", "").strip()
            parts = range_val.split("-")
            if parts[0]:
                start = int(parts[0])
            if len(parts) > 1 and parts[1]:
                end = int(parts[1])
            status_code = 206

        if total_size > 0 and end >= total_size:
            end = total_size - 1

        content_length = (end - start + 1) if total_size > 0 else 0

        drive_url = f"https://www.googleapis.com/drive/v3/files/{clean_id}?alt=media"
        req_headers = {
            "Authorization": f"Bearer {token}",
            "Range": f"bytes={start}-{end}"
        }

        upstream = requests.get(drive_url, headers=req_headers, stream=True, timeout=20)
        if upstream.status_code == 401:
            fresh_token = self.refresh_access_token()
            if fresh_token:
                req_headers["Authorization"] = f"Bearer {fresh_token}"
                upstream = requests.get(drive_url, headers=req_headers, stream=True, timeout=20)

        if not upstream.ok and upstream.status_code != 206:
            raise RuntimeError(f"Google Drive upstream error {upstream.status_code}")

        resp_headers = {
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Disposition": "inline",
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff"
        }
        if status_code == 206 and total_size > 0:
            resp_headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"

        def iter_chunks():
            try:
                for chunk in upstream.iter_content(chunk_size=1024 * 64):  # 64KB chunks
                    if chunk:
                        yield chunk
            except Exception as e:
                print(f"[GoogleDrive Stream Notice] Client disconnected or stream closed: {e}")
            finally:
                upstream.close()

        return status_code, resp_headers, iter_chunks()

