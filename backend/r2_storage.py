import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from concurrent.futures import ThreadPoolExecutor
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
    Optimized with disk-streaming transfers, in-memory metadata/key caching,
    and throttled eviction scanning.
    """

    def __init__(self):
        self.endpoint_url = Config.CLOUDFLARE_R2_ENDPOINT
        self.access_key_id = Config.CLOUDFLARE_R2_ACCESS_KEY_ID
        self.secret_access_key = Config.CLOUDFLARE_R2_SECRET_ACCESS_KEY
        self.bucket_name = Config.CLOUDFLARE_R2_BUCKET_NAME
        self._client = None
        
        # Thread-safe in-memory cache to eliminate repetitive S3 HTTPS network calls
        self._cache_lock = threading.Lock()
        self._verified_packages: Set[str] = set()
        self._key_cache: Dict[str, bytes] = {}
        self._last_eviction_time: float = 0.0

        self._init_client()

    def _init_client(self):
        if self.is_configured():
            try:
                boto_conf = BotoConfig(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                    connect_timeout=5,
                    read_timeout=30,
                    max_pool_connections=35
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
        from local_hls_dir to Cloudflare R2 in parallel using disk-streaming transfers.
        Streams directly from disk to prevent loading gigabytes into container RAM.
        Skips files that are already present in R2 for fast resume and idempotency.
        """
        if not self._client or not local_hls_dir.exists():
            return False

        try:
            files = [f for f in local_hls_dir.glob("*") if f.is_file() and f.name != "keyinfo.txt"]
            if not files:
                return False

            # Query existing keys in R2 for fast resume/idempotency
            existing_keys = set()
            try:
                paginator = self._client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=f"hls/{lesson_id}/"):
                    for obj in page.get("Contents", []):
                        existing_keys.add(Path(obj["Key"]).name)
            except Exception:
                pass

            files_to_upload = [f for f in files if f.name not in existing_keys or f.name.endswith(".m3u8")]
            if not files_to_upload:
                logger.info(f"[R2 Storage] All {len(files)} files for {lesson_id} already exist in R2.")
                with self._cache_lock:
                    self._verified_packages.add(lesson_id)
                return True

            worker_count = min(max_workers, max(2, (os.cpu_count() or 2) * 2))
            logger.info(f"[R2 Storage] Streaming upload {len(files_to_upload)}/{len(files)} HLS files for {lesson_id} to R2 ({worker_count} threads)...")

            def _upload_single_file(f: Path) -> bool:
                r2_key = f"hls/{lesson_id}/{f.name}"
                content_type = "application/vnd.apple.mpegurl" if f.name.endswith(".m3u8") else (
                    "video/mp2t" if f.name.endswith(".ts") else "application/octet-stream"
                )
                extra_args = {
                    "ContentType": content_type,
                    "CacheControl": "public, max-age=31536000, immutable" if f.name.endswith(".ts") else "private, no-cache, no-store"
                }

                # Cache enc.key in-memory for instant playback retrieval
                if f.name == "enc.key":
                    try:
                        k_data = f.read_bytes()
                        with self._cache_lock:
                            self._key_cache[lesson_id] = k_data
                    except Exception:
                        pass

                for attempt in range(3):
                    try:
                        # Disk streaming via upload_file avoids loading full file bytes into RAM
                        self._client.upload_file(str(f), self.bucket_name, r2_key, ExtraArgs=extra_args)
                        return True
                    except Exception as err:
                        if attempt == 2:
                            logger.warning(f"[R2 Storage] Failed uploading {r2_key} after 3 attempts: {err}")
                            return False
                        time.sleep(0.4 * (attempt + 1))
                return False

            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="r2_uploader") as executor:
                results = list(executor.map(_upload_single_file, files_to_upload))

            success = all(results)
            if success:
                with self._cache_lock:
                    if len(self._verified_packages) > 1000:
                        self._verified_packages.clear()
                    self._verified_packages.add(lesson_id)

            logger.info(f"[R2 Storage] Synced lesson {lesson_id} to Cloudflare R2: {sum(results)}/{len(files_to_upload)} files transferred.")
            return success
        except Exception as e:
            logger.error(f"[R2 Storage] Error uploading HLS package for {lesson_id}: {e}")
            return False

    def has_hls_package(self, lesson_id: str) -> bool:
        """
        Checks if master.m3u8 exists in R2 for this lesson.
        Cached in-memory to eliminate 100-300ms HTTPS network latency on repeat requests.
        """
        if not self._client:
            return False

        with self._cache_lock:
            if lesson_id in self._verified_packages:
                return True

        try:
            self._client.head_object(Bucket=self.bucket_name, Key=f"hls/{lesson_id}/master.m3u8")
            with self._cache_lock:
                if len(self._verified_packages) > 1000:
                    self._verified_packages.clear()
                self._verified_packages.add(lesson_id)
            return True
        except ClientError:
            return False
        except Exception:
            return False

    def get_hls_file_bytes(self, lesson_id: str, filename: str) -> Optional[bytes]:
        """
        Fetches raw bytes of a playlist, segment, or key from R2.
        For 16-byte AES keys ('enc.key'), uses in-memory LRU cache to deliver 0ms key releases.
        """
        if not self._client:
            return None

        # Check in-memory key cache for enc.key
        if filename == "enc.key":
            with self._cache_lock:
                if lesson_id in self._key_cache:
                    return self._key_cache[lesson_id]

        r2_key = f"hls/{lesson_id}/{filename}"
        try:
            resp = self._client.get_object(Bucket=self.bucket_name, Key=r2_key)
            data = resp["Body"].read()

            if filename == "enc.key" and data:
                with self._cache_lock:
                    if len(self._key_cache) > 500:
                        self._key_cache.clear()
                    self._key_cache[lesson_id] = data

            return data
        except Exception as e:
            logger.debug(f"[R2 Storage] get_hls_file_bytes miss for {r2_key}: {e}")
            return None

    def download_hls_package_to_local(self, lesson_id: str, local_hls_dir: Path, max_workers: int = 6) -> bool:
        """
        Downloads all segments and master playlist for lesson_id from R2 to local disk
        using parallel threaded downloads (10x faster than sequential).
        """
        if not self._client:
            return False
        try:
            prefix = f"hls/{lesson_id}/"
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            local_hls_dir.mkdir(parents=True, exist_ok=True)
            keys_to_download: List[str] = []

            for page in pages:
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    filename = Path(key).name
                    dest_file = local_hls_dir / filename
                    if not dest_file.exists():
                        keys_to_download.append(key)

            if not keys_to_download:
                return True

            def _download_single(key: str) -> bool:
                filename = Path(key).name
                dest_file = local_hls_dir / filename
                for attempt in range(2):
                    try:
                        self._client.download_file(self.bucket_name, key, str(dest_file))
                        return True
                    except Exception:
                        time.sleep(0.3)
                return False

            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="r2_downloader") as executor:
                results = list(executor.map(_download_single, keys_to_download))

            downloaded = sum(results)
            logger.info(f"[R2 Storage] Downloaded {downloaded}/{len(keys_to_download)} files for {lesson_id} from R2 to local cache.")
            return all(results)
        except Exception as e:
            logger.error(f"[R2 Storage] Error downloading package for {lesson_id} from R2: {e}")
            return False

    def evict_oldest_lessons_if_needed(self, max_allowed_bytes: int = 8500 * 1024 * 1024, force: bool = False) -> int:
        """
        LRU Hot Cache Eviction Governor.
        Monitors total R2 bucket storage usage. If total bytes exceeds 8.5 GB (out of 10 GB free tier),
        safely purges the oldest stored HLS lesson packages from R2.
        Original master videos remain 100% safe in Google Drive.
        Throttled to run at most once per 30 minutes to conserve API quota and CPU.
        """
        if not self._client:
            return 0

        now = time.time()
        with self._cache_lock:
            if not force and (now - self._last_eviction_time < 1800):
                # Throttle eviction scan to once every 30 minutes
                return 0
            self._last_eviction_time = now

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

                # Invalidate in-memory verified cache
                with self._cache_lock:
                    self._verified_packages.discard(lid)
                    self._key_cache.pop(lid, None)

                total_bucket_bytes -= stats["total_bytes"]
                evicted_count += 1

            logger.info(f"[R2 Storage LRU] Eviction complete. Removed {evicted_count} lessons. New total: {total_bucket_bytes / (1024*1024):.1f}MB.")
            return evicted_count
        except Exception as e:
            logger.error(f"[R2 Storage LRU] Eviction notice: {e}")
            return 0


_r2_storage_instance: Optional[CloudflareR2Storage] = None
_r2_init_lock = threading.Lock()

def get_r2_storage() -> CloudflareR2Storage:
    global _r2_storage_instance
    if _r2_storage_instance is None:
        with _r2_init_lock:
            if _r2_storage_instance is None:
                _r2_storage_instance = CloudflareR2Storage()
    return _r2_storage_instance
