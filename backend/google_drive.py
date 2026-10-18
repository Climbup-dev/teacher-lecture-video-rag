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

    def is_configured(self) -> bool:
        return self.service is not None

    def list_files(self, folder_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists files inside the designated Google Drive folder."""
        if not self.service:
            return []

        fid = folder_id or self.default_folder_id
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
        if not self.service:
            print("[GoogleDrive] Service not initialized, cannot upload.")
            return None

        fid = folder_id or self.default_folder_id
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
        if not self.service:
            return False

        try:
            request = self.service.files().get_media(fileId=file_id)
            with open(dest_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request, chunksize=1024 * 1024 * 4) # 4MB chunks
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        print(f"[GoogleDrive] Ingestion stream {int(status.progress() * 100)}%")
            return True
        except Exception as e:
            print(f"[GoogleDrive] Error streaming file {file_id}: {e}")
            return False

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        if not self.service:
            return None
        try:
            return self.service.files().get(fileId=file_id, fields="id, name, mimeType, size, webViewLink").execute()
        except Exception as e:
            print(f"[GoogleDrive] Error fetching metadata for {file_id}: {e}")
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
        if not self.service:
            return False
        try:
            self.service.permissions().create(
                fileId=file_id,
                body={"role": "reader", "type": "anyone"}
            ).execute()
            return True
        except Exception as e:
            print(f"[GoogleDrive] Permission notice: {e}")
            return False
