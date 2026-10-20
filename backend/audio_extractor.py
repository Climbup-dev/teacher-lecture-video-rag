import os
import shutil
import subprocess
from pathlib import Path
import imageio_ffmpeg

def get_ffmpeg_binary() -> str:
    """Returns system ffmpeg if available, otherwise bundled imageio-ffmpeg."""
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def extract_and_clean_audio(input_media_path: str, output_audio_path: str = None) -> str:
    """
    Extracts high-efficiency audio from video for Deepgram Nova-2.
    Strategy 1: Fast stream copy (-c:a copy) demuxes audio in ~2-5s without CPU re-encoding.
    Strategy 2: Multi-threaded AAC/MP3 transcoding fallback with 1200s timeout for multi-hour lectures.
    """
    input_path = Path(input_media_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_media_path}")

    ffmpeg_bin = get_ffmpeg_binary()

    # Strategy 1: Instant stream copy if video has AAC/MP3 audio track (~2-5 seconds for 4 hours)
    if not output_audio_path:
        fast_m4a = input_path.parent / f"{input_path.stem}_fast.m4a"
        copy_cmd = [
            ffmpeg_bin, "-y",
            "-i", str(input_path),
            "-vn",
            "-c:a", "copy",
            str(fast_m4a)
        ]
        try:
            copy_res = subprocess.run(copy_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            if copy_res.returncode == 0 and fast_m4a.exists() and fast_m4a.stat().st_size > 1024:
                return str(fast_m4a)
        except Exception:
            pass

    # Strategy 2: High-efficiency transcoding fallback (AAC/MP3) with all container cores
    if not output_audio_path:
        output_audio_path = str(input_path.parent / f"{input_path.stem}_clean_16k.mp3")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-threads", "0",
        "-i", str(input_path),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "32k",
        "-ar", "16000",
        "-ac", "1",
        str(output_audio_path)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200)
    if result.returncode != 0:
        # Fallback to standard wav if mp3 codec is missing
        output_audio_path = str(input_path.parent / f"{input_path.stem}_clean_16k.wav")
        fallback_cmd = [
            ffmpeg_bin, "-y", "-threads", "0", "-i", str(input_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_audio_path
        ]
        subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200)

    return str(output_audio_path)

