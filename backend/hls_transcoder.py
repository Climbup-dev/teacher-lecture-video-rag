import os
import shutil
import secrets
import subprocess
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("climbup.hls")


class HLSTranscoder:
    """
    Enterprise-Grade AES-128 Encrypted HLS Packaging Engine.
    Slices lecture MP4s into AES-128 encrypted .ts segments for anti-piracy protection.
    Used by streaming platforms (Udemy, Hotstar) to prevent browser extensions from downloading full videos.
    """

    @classmethod
    def get_ffmpeg_binary(cls) -> Optional[str]:
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    @classmethod
    def is_ffmpeg_available(cls) -> bool:
        return cls.get_ffmpeg_binary() is not None

    @classmethod
    def package_video_to_encrypted_hls(
        cls,
        lesson_id: str,
        input_file_path: Path,
        output_hls_dir: Path,
        segment_duration: int = 4
    ) -> Optional[Dict[str, Any]]:
        """
        Remuxes an MP4 video into AES-128 encrypted HLS segments using ffmpeg -codec copy.
        Because -codec copy is used, this runs at ultra-fast speeds (~1-3 seconds for 15-minute video)
        with zero video quality loss and minimal CPU usage.
        """
        ffmpeg_bin = cls.get_ffmpeg_binary()
        if not ffmpeg_bin:
            logger.warning("[HLS] ffmpeg is not available on this host. Skipping HLS transcoding.")
            return None

        if not input_file_path.exists():
            logger.error(f"[HLS] Input file does not exist: {input_file_path}")
            return None

        output_hls_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = output_hls_dir / "master.m3u8"
        key_path = output_hls_dir / "enc.key"
        keyinfo_path = output_hls_dir / "keyinfo.txt"

        # Generate fresh 16-byte cryptographic key and 16-byte hex IV
        key_bytes = secrets.token_bytes(16)
        iv_hex = secrets.token_hex(16)

        key_path.write_bytes(key_bytes)

        # Key URI served to authorized clients by the backend API
        key_uri = f"/api/lessons/{lesson_id}/hls/key"

        # keyinfo format for ffmpeg:
        # Line 1: Key URI (written into m3u8 playlist)
        # Line 2: Path to the key file for ffmpeg to read during encryption
        # Line 3: Optional IV (hex string)
        keyinfo_content = f"{key_uri}\n{str(key_path.resolve())}\n{iv_hex}\n"
        keyinfo_path.write_text(keyinfo_content, encoding="utf-8")

        segment_pattern = str((output_hls_dir / "segment_%03d.ts").resolve())

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", str(input_file_path.resolve()),
            "-codec", "copy",
            "-hls_time", str(segment_duration),
            "-hls_list_size", "0",
            "-hls_key_info_file", str(keyinfo_path.resolve()),
            "-hls_segment_filename", segment_pattern,
            str(playlist_path.resolve())
        ]

        try:
            logger.info(f"[HLS] Packaging {lesson_id} into encrypted HLS stream...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"[HLS] ffmpeg failed: {result.stderr.decode('utf-8', errors='ignore')[:300]}")
                return None

            # Remove temporary keyinfo file (keep enc.key private in output_hls_dir)
            if keyinfo_path.exists():
                try:
                    keyinfo_path.unlink()
                except Exception:
                    pass

            segments = list(output_hls_dir.glob("segment_*.ts"))
            logger.info(f"[HLS] Successfully packaged {lesson_id} into {len(segments)} encrypted segments.")

            return {
                "lesson_id": lesson_id,
                "playlist_file": str(playlist_path),
                "key_file": str(key_path),
                "total_segments": len(segments),
                "iv": iv_hex
            }
        except Exception as e:
            logger.error(f"[HLS] Packaging exception for {lesson_id}: {e}")
            return None
