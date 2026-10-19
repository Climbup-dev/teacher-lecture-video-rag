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
    Extracts 16kHz mono high-efficiency MP3 audio from any video/audio file.
    Reduces a 1-hour audio payload from 115 MB (raw WAV) down to ~12 MB (MP3 32kbps),
    completely preventing Deepgram HTTP 504 Gateway Timeouts and network latency.
    """
    input_path = Path(input_media_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_media_path}")

    if not output_audio_path:
        output_audio_path = str(input_path.parent / f"{input_path.stem}_clean_16k.mp3")

    ffmpeg_bin = get_ffmpeg_binary()

    # FFmpeg command:
    # -vn: strip video stream
    # -c:a libmp3lame: high quality MP3 encoder
    # -b:a 32k: 32kbps speech bitrate (perfect for Deepgram Nova-2)
    # -ar 16000: 16kHz speech sample rate
    # -ac 1: 1 audio channel (mono)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_path),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "32k",
        "-ar", "16000",
        "-ac", "1",
        str(output_audio_path)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        # Fallback to standard wav if mp3 codec is missing
        output_audio_path = str(input_path.parent / f"{input_path.stem}_clean_16k.wav")
        fallback_cmd = [
            ffmpeg_bin, "-y", "-i", str(input_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            output_audio_path
        ]
        subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    return str(output_audio_path)
