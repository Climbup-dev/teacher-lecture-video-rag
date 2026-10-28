import os
import shutil
import subprocess
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import Config
from backend.hls_transcoder import HLSTranscoder
from backend.security import generate_signed_stream_token

class TestHLSEncryptedStreamingSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.db_adapter import DBAdapter
        cls.client = TestClient(app)
        cls.db = DBAdapter()
        cls.test_lesson_id = "test_hls_lecture_99"
        cls.hls_dir = Config.CHUNKS_DIR / "hls" / cls.test_lesson_id
        cls.temp_video = Config.UPLOADS_DIR / "dummy_test_video.mp4"

        # Register in DB so lesson lookup succeeds
        cls.db.save_lesson(
            lesson_id=cls.test_lesson_id,
            course_id="course-applied-ai-rag",
            title="Synthetic Security Test Lecture",
            duration_seconds=120,
            video_url="/uploads/dummy_test_video.mp4",
            raw_transcript="Synthetic lecture audio transcript for security test",
            utterances=[]
        )
        # Ensure test lesson is protected (not free preview)
        store = cls.db._read_local_store()
        if cls.test_lesson_id in store.get("lessons", {}):
            store["lessons"][cls.test_lesson_id]["is_free_preview"] = False
            cls.db._write_local_store(store)

        # 1. Verify ffmpeg is available
        cls.ffmpeg_bin = HLSTranscoder.get_ffmpeg_binary()
        if cls.ffmpeg_bin:
            # Generate a tiny 2-second synthetic MP4 video
            subprocess.run([
                cls.ffmpeg_bin, "-y",
                "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
                "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
                "-c:v", "libx264", "-c:a", "aac",
                str(cls.temp_video.resolve())
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

            if cls.temp_video.exists():
                HLSTranscoder.package_video_to_encrypted_hls(
                    lesson_id=cls.test_lesson_id,
                    input_file_path=cls.temp_video,
                    output_hls_dir=cls.hls_dir,
                    segment_duration=2
                )

    @classmethod
    def tearDownClass(cls):
        # Cleanup test artifacts
        if cls.temp_video.exists():
            cls.temp_video.unlink()
        if cls.hls_dir.exists():
            shutil.rmtree(cls.hls_dir, ignore_errors=True)
        try:
            cls.db.delete_lesson(cls.test_lesson_id)
        except Exception:
            pass

    def test_01_ffmpeg_available(self):
        """Verify that ffmpeg binary is correctly resolved on the host."""
        self.assertTrue(HLSTranscoder.is_ffmpeg_available())

    def test_02_hls_packaging_structure(self):
        """Verify that AES-128 HLS packaging generates master playlist and 16-byte key."""
        if not self.ffmpeg_bin or not self.temp_video.exists():
            self.skipTest("ffmpeg video generation not available")

        playlist = self.hls_dir / "master.m3u8"
        key_file = self.hls_dir / "enc.key"
        self.assertTrue(playlist.exists())
        self.assertTrue(key_file.exists())
        self.assertEqual(len(key_file.read_bytes()), 16, "AES-128 key must be exactly 16 bytes")

        # Verify playlist contains AES-128 encryption method
        content = playlist.read_text(encoding="utf-8")
        self.assertIn("METHOD=AES-128", content)

    def test_03_playlist_token_authorization(self):
        """Verify that playlist requires valid signed token or authenticated session."""
        if not (self.hls_dir / "master.m3u8").exists():
            self.skipTest("HLS playlist not packaged")

        # Missing token & missing auth
        res_unauth = self.client.get(f"/api/lessons/{self.test_lesson_id}/hls/master.m3u8")
        # Should be 401 (unauthorized) or 404
        self.assertIn(res_unauth.status_code, [401, 403, 404])

        # Valid signed stream token
        valid_st = generate_signed_stream_token(self.test_lesson_id, "student_101", "testclient", ttl_seconds=300)
        res_valid = self.client.get(f"/api/lessons/{self.test_lesson_id}/hls/master.m3u8?st={valid_st}")
        self.assertEqual(res_valid.status_code, 200)
        self.assertIn(f"?st={valid_st}", res_valid.text)

    def test_04_playlist_blocks_automated_downloaders(self):
        """Verify that tools (yt-dlp, curl, IDM) are blocked from accessing master.m3u8."""
        valid_st = generate_signed_stream_token(self.test_lesson_id, "student_101", "testclient", ttl_seconds=300)
        for tool in ["yt-dlp/2024.08.01", "curl/8.4.0", "Mozilla/5.0 Internet Download Manager 6.42"]:
            res = self.client.get(
                f"/api/lessons/{self.test_lesson_id}/hls/master.m3u8?st={valid_st}",
                headers={"User-Agent": tool}
            )
            self.assertEqual(res.status_code, 403, f"{tool} must be blocked with 403")

    def test_05_key_endpoint_security(self):
        """Verify that the 16-byte AES-128 key is guarded by signed token and blocks scrapers."""
        if not (self.hls_dir / "enc.key").exists():
            self.skipTest("enc.key not present")

        # 1. Blocked scraper
        valid_st = generate_signed_stream_token(self.test_lesson_id, "student_101", "testclient", ttl_seconds=300)
        res_blocked = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/key?st={valid_st}",
            headers={"User-Agent": "yt-dlp"}
        )
        self.assertEqual(res_blocked.status_code, 403)

        # 2. Forged / Expired token rejected
        res_forged = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/key?st=fake.token.here",
            headers={"User-Agent": "Mozilla/5.0 Chrome/120.0.0.0"}
        )
        self.assertEqual(res_forged.status_code, 403)

        # 3. Legitimate in-app browser playback with signed stream token
        res_allowed_token = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/key?st={valid_st}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        )
        self.assertEqual(res_allowed_token.status_code, 200)
        self.assertEqual(len(res_allowed_token.content), 16)

        # 4. Legitimate playback with player handshake header
        res_allowed_header = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/key",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
                "X-Climbup-Player": "amirshaikh320340"
            }
        )
        self.assertEqual(res_allowed_header.status_code, 200)
        self.assertEqual(len(res_allowed_header.content), 16)

        # 5. Direct request without token and without player handshake header is blocked
        res_no_auth = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/key",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
        )
        self.assertEqual(res_no_auth.status_code, 403)

    def test_06_segment_scraper_protection(self):
        """Verify that segments block automated scrapers."""
        segments = list(self.hls_dir.glob("segment_*.ts"))
        if not segments:
            self.skipTest("No segments generated")

        seg_name = segments[0].name
        res = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/{seg_name}",
            headers={"User-Agent": "Wget/1.21"}
        )
        self.assertEqual(res.status_code, 403)

    def test_07_extension_origin_blocked(self):
        """Verify that browser extension origins (chrome-extension://, moz-extension://) are blocked with 403."""
        valid_st = generate_signed_stream_token(self.test_lesson_id, "student_101", "testclient", ttl_seconds=300)
        res_ext = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/master.m3u8?st={valid_st}",
            headers={"Origin": "chrome-extension://abcdefghijklmno123456"}
        )
        self.assertEqual(res_ext.status_code, 403)
        self.assertIn("Automated download tools", res_ext.json().get("detail", ""))

    def test_08_extension_downloader_useragent_blocked(self):
        """Verify that FetchV, Stream Recorder, and M3U8 Downloader are blocked with 403."""
        valid_st = generate_signed_stream_token(self.test_lesson_id, "student_101", "testclient", ttl_seconds=300)
        for ext_ua in ["FetchV/2.1", "Stream Recorder v1.2", "M3U8 Downloader Extension"]:
            res = self.client.get(
                f"/api/lessons/{self.test_lesson_id}/hls/key?st={valid_st}",
                headers={"User-Agent": ext_ua}
            )
            self.assertEqual(res.status_code, 403)

    def test_09_chunk_dumping_defense(self):
        """Verify that parallel chunk dumping (exceeding 10 segments in 4s) is throttled with 429."""
        segments = list(self.hls_dir.glob("segment_*.ts"))
        if not segments:
            self.skipTest("No segments generated")

        seg_name = segments[0].name
        valid_st = generate_signed_stream_token(self.test_lesson_id, "student_101", "testclient", ttl_seconds=300)

        # Trigger more than 10 requests within the window
        got_429 = False
        for _ in range(18):
            res = self.client.get(
                f"/api/lessons/{self.test_lesson_id}/hls/{seg_name}?st={valid_st}",
                headers={"User-Agent": "Mozilla/5.0 Chrome/120.0"}
            )
            if res.status_code == 429:
                got_429 = True
                break
        self.assertTrue(got_429, "Excessive parallel chunk requests must trigger 429 rate limit")

    def test_10_segment_signed_token_required(self):
        """Verify that media segments require valid signed stream token or player header."""
        segments = list(self.hls_dir.glob("segment_*.ts"))
        if not segments:
            self.skipTest("No segments generated")

        seg_name = segments[0].name
        # Request with invalid token from a distinct IP
        res_bad = self.client.get(
            f"/api/lessons/{self.test_lesson_id}/hls/{seg_name}?st=tampered.token",
            headers={"User-Agent": "Mozilla/5.0 Chrome/120.0", "X-Forwarded-For": "10.0.0.99"}
        )
        self.assertEqual(res_bad.status_code, 403)


if __name__ == "__main__":
    unittest.main()


