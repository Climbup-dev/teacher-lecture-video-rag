import os
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from backend.config import Config

logger = logging.getLogger("climbup.r2_storage")

class CloudflareR2Storage:
    """
    Enterprise Cloudflare R2 Storage Manager for ClimbUp.
    Handles high-speed S3-compatible media chunk storage, LRU hot cache eviction,
    and direct encrypted HLS delivery with zero egress bandwidth fees.
    """

    def __init__(self):
        self.endpoint_url = Config.CLOUDFLARE_R2_ENDPOINT
        self.access_key_id = Config.CLOUDFLARE_R2_ACCESS_KEY_ID
        self.secret_access_key = Config.CLOUDFLARE_R2_SECRET_ACCESS_KEY
        self.bucket_name = Config.CLOUDFLARE_R2_BUCKET_NAME
        self._client = None
        self._init_client()

    def _init_client(self):
        if self.is_configured():
            try:
                boto_conf = BotoConfig(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=5,
                    read_timeout=30,
                    max_pool_connections=25
                )
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    region_name="auto",
                    config=boto_conf
                )
                logger.info(f"[R2 Storage] Initialized Cloudflare R2 client for bucket '{self.bucket_name}'.")
            except Exception as e:
                logger.error(f"[R2 Storage] Failed to initialize Cloudflare R2 client: {e}")
                self._client = None

    def is_configured(self) -> bool:
        return bool(
            self.endpoint_url and
            self.access_key_id and
            self.secret_access_key and
            self.bucket_name
        )

    def upload_hls_package(self, lesson_id: str, local_hls_dir: Path, max_workers: int = 8) -> bool:
        """
        Uploads all encrypted HLS files (master.m3u8, segment_*.ts, enc.key)
        from local_hls_dir to Cloudflare R2 in parallel with automatic retries.
        """
        if not self._client or not local_hls_dir.exists():
            return False

        try:
            files = [f for f in local_hls_dir.glob("*") if f.is_file() and f.name != "keyinfo.txt"]
            if not files:
                return False

            logger.info(f"[R2 Storage] Parallel uploading {len(files)} HLS files for {lesson_id} to R2 ({max_workers} threads)...")

            def _upload_single_file(f: Path):
                r2_key = f"hls/{lesson_id}/{f.name}"
                content_type = "application/vnd.apple.mpegurl" if f.name.endswith(".m3u8") else (
                    "video/mp2t" if f.name.endswith(".ts") else "application/octet-stream"
                )
                data = f.read_bytes()
                for attempt in range(3):
                    try:
                        self._client.put_object(
                            Bucket=self.bucket_name,
                            Key=r2_key,
                            Body=data,
                            ContentType=content_type,
                            CacheControl="public, max-age=31536000, immutable" if f.name.endswith(".ts") else "private, no-cache, no-store"
                        )
                        return True
                    except Exception as err:
                        if attempt == 2:
                            logger.warning(f"[R2 Storage] Notice failed uploading {r2_key} after 3 attempts: {err}")
                            return False
                        time.sleep(0.5)
                return False

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(_upload_single_file, files))

            success = all(results)
            logger.info(f"[R2 Storage] Synced lesson {lesson_id} to Cloudflare R2: {sum(results)}/{len(files)} files uploaded.")
            return success
        except Exception as e:
            logger.error(f"[R2 Storage] Error uploading HLS package for {lesson_id}: {e}")
            return False

    def has_hls_package(self, lesson_id: str) -> bool:
        """Checks if master.m3u8 exists in R2 for this lesson."""
        if not self._client:
            return False
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=f"hls/{lesson_id}/master.m3u8")
            return True
        except ClientError:
            return False
        except Exception:
            return False

    def get_hls_file_bytes(self, lesson_id: str, filename: str) -> Optional[bytes]:
        """Fetches raw bytes of a playlist, segment, or key from R2."""
        if not self._client:
            return None
        r2_key = f"hls/{lesson_id}/{filename}"
        try:
            resp = self._client.get_object(Bucket=self.bucket_name, Key=r2_key)
            return resp["Body"].read()
        except Exception as e:
            logger.debug(f"[R2 Storage] get_hls_file_bytes miss for {r2_key}: {e}")
            return None

    def download_hls_package_to_local(self, lesson_id: str, local_hls_dir: Path) -> bool:
        """
        Downloads all segments and master playlist for lesson_id from R2 to local disk.
        """
        if not self._client:
            return False
        try:
            prefix = f"hls/{lesson_id}/"
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            local_hls_dir.mkdir(parents=True, exist_ok=True)
            downloaded = 0
            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    filename = Path(key).name
                    dest_file = local_hls_dir / filename
                    if not dest_file.exists():
                        resp = self._client.get_object(Bucket=self.bucket_name, Key=key)
                        dest_file.write_bytes(resp["Body"].read())
                        downloaded += 1

            logger.info(f"[R2 Storage] Downloaded {downloaded} files for {lesson_id} from R2 to local cache.")
            return True
        except Exception as e:
            logger.error(f"[R2 Storage] Error downloading package for {lesson_id} from R2: {e}")
            return False

    def evict_oldest_lessons_if_needed(self, max_allowed_bytes: int = 8500 * 1024 * 1024) -> int:
        """
        LRU Hot Cache Eviction Governor.
        Monitors total R2 bucket storage usage. If total bytes exceeds 8.5 GB (out of 10 GB free tier),
        safely purges the oldest stored HLS lesson packages from R2.
        Original master videos remain 100% safe in Google Drive.
        Returns the number of evicted lesson packages.
        """
        if not self._client:
            return 0

        try:
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix="hls/")

            lesson_stats: Dict[str, Dict[str, Any]] = {}
            total_bucket_bytes = 0

            for page in pages:
                for obj in page.get("Contents", []):
                    size = obj.get("Size", 0)
                    total_bucket_bytes += size
                    key = obj.get("Key", "")
                    parts = key.split("/")
                    if len(parts) >= 3 and parts[0] == "hls":
                        lid = parts[1]
                        if lid not in lesson_stats:
                            lesson_stats[lid] = {
                                "total_bytes": 0,
                                "keys": [],
                                "last_modified": obj.get("LastModified")
                            }
                        lesson_stats[lid]["total_bytes"] += size
                        lesson_stats[lid]["keys"].append(key)
                        if obj.get("LastModified") and (
                            not lesson_stats[lid]["last_modified"] or obj["LastModified"] < lesson_stats[lid]["last_modified"]
                        ):
                            lesson_stats[lid]["last_modified"] = obj["LastModified"]

            if total_bucket_bytes <= max_allowed_bytes:
                return 0

            logger.warning(
                f"[R2 Storage LRU] R2 storage is {total_bucket_bytes / (1024*1024):.1f}MB, "
                f"exceeding threshold of {max_allowed_bytes / (1024*1024):.1f}MB. Initiating eviction..."
            )

            # Sort lessons by oldest last_modified timestamp
            sorted_lessons = sorted(
                lesson_stats.items(),
                key=lambda item: item[1]["last_modified"] or 0
            )

            evicted_count = 0
            for lid, stats in sorted_lessons:
                if total_bucket_bytes <= max_allowed_bytes:
                    break
                logger.info(f"[R2 Storage LRU] Evicting cold lesson {lid} ({stats['total_bytes'] / (1024*1024):.1f}MB) from R2...")
                # Delete objects in batches of 1000
                keys_to_delete = [{"Key": k} for k in stats["keys"]]
                for i in range(0, len(keys_to_delete), 1000):
                    batch = keys_to_delete[i:i + 1000]
                    self._client.delete_objects(Bucket=self.bucket_name, Delete={"Objects": batch})

                total_bucket_bytes -= stats["total_bytes"]
                evicted_count += 1

            logger.info(f"[R2 Storage LRU] Eviction complete. Removed {evicted_count} lessons. New total: {total_bucket_bytes / (1024*1024):.1f}MB.")
            return evicted_count
        except Exception as e:
            logger.error(f"[R2 Storage LRU] Eviction notice: {e}")
            return 0


_r2_storage_instance = None

def get_r2_storage() -> CloudflareR2Storage:
    global _r2_storage_instance
    if _r2_storage_instance is None:
        _r2_storage_instance = CloudflareR2Storage()
    return _r2_storage_instance
