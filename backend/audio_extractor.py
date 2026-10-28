import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

_CACHED_FFMPEG: Optional[str] = None

def get_ffmpeg_binary() -> str:
    """Returns cached system ffmpeg if available, otherwise bundled imageio-ffmpeg."""
    global _CACHED_FFMPEG
    if _CACHED_FFMPEG is not None:
        return _CACHED_FFMPEG

    if shutil.which("ffmpeg"):
        _CACHED_FFMPEG = "ffmpeg"
        return _CACHED_FFMPEG
    try:
        import imageio_ffmpeg
        _CACHED_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
        return _CACHED_FFMPEG
    except Exception:
        _CACHED_FFMPEG = "ffmpeg"
        return _CACHED_FFMPEG

def extract_and_clean_audio(input_media_path: str, output_audio_path: str = None) -> str:
    """
    Extracts high-efficiency audio from video for Deepgram Nova-2.
    - Instant reuse if clean audio already extracted.
    - Strategy 1: Fast stream copy (-c:a copy) demuxes audio in ~1-3s without re-encoding.
    - Strategy 2: Multi-threaded mono 32kbps 16kHz transcoding for compact network payload.
    """
    input_path = Path(input_media_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_media_path}")

    # Instant check: if destination already exists and is non-empty, reuse it directly
    default_clean = input_path.parent / f"{input_path.stem}_clean_16k.mp3"
    if not output_audio_path and default_clean.exists() and default_clean.stat().st_size > 10240:
        return str(default_clean)

    if output_audio_path and Path(output_audio_path).exists() and Path(output_audio_path).stat().st_size > 10240:
        return str(output_audio_path)

    ffmpeg_bin = get_ffmpeg_binary()

    # Strategy 1: Instant stream copy only if audio track is already compact (<= 15MB)
    if not output_audio_path:
        fast_m4a = input_path.parent / f"{input_path.stem}_fast.m4a"
        if fast_m4a.exists() and fast_m4a.stat().st_size <= 15 * 1024 * 1024 and fast_m4a.stat().st_size > 1024:
            return str(fast_m4a)

        copy_cmd = [
            ffmpeg_bin, "-y", "-nostdin", "-loglevel", "error",
            "-i", str(input_path),
            "-vn",
            "-c:a", "copy",
            str(fast_m4a)
        ]
        try:
            copy_res = subprocess.run(copy_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
            if copy_res.returncode == 0 and fast_m4a.exists() and fast_m4a.stat().st_size > 1024:
                if fast_m4a.stat().st_size <= 15 * 1024 * 1024:
                    return str(fast_m4a)
                # Oversized audio (>15MB): clean up and transcode
                try:
                    fast_m4a.unlink()
                except Exception:
                    pass
        except Exception:
            pass

    # Strategy 2: High-efficiency transcoding (16kHz mono 32kbps)
    if not output_audio_path:
        output_audio_path = str(default_clean)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-nostdin",
        "-loglevel", "error",
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
        # Fallback to standard AAC
        output_audio_path = str(input_path.parent / f"{input_path.stem}_clean_16k.m4a")
        fallback_cmd = [
            ffmpeg_bin, "-y", "-nostdin", "-loglevel", "error",
            "-threads", "0", "-i", str(input_path),
            "-vn", "-c:a", "aac", "-b:a", "32k", "-ar", "16000", "-ac", "1",
            output_audio_path
        ]
        result2 = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200)
        if result2.returncode != 0:
            # Fallback to 16kHz mono WAV
            output_audio_path = str(input_path.parent / f"{input_path.stem}_clean_16k.wav")
            wav_cmd = [
                ffmpeg_bin, "-y", "-nostdin", "-loglevel", "error",
                "-threads", "0", "-i", str(input_path),
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                output_audio_path
            ]
            subprocess.run(wav_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1200)

    return str(output_audio_path)


