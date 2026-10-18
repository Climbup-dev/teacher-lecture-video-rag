import os
import subprocess
from pathlib import Path
import imageio_ffmpeg

def get_ffmpeg_binary() -> str:
    """Returns the bundled ffmpeg binary from imageio-ffmpeg."""
    return imageio_ffmpeg.get_ffmpeg_exe()

def extract_and_clean_audio(input_media_path: str, output_wav_path: str = None) -> str:
    """
    Extracts 16kHz mono 16-bit PCM WAV audio from any video/audio file.
    16kHz mono audio reduces file size by >90% while providing optimal clarity for Deepgram Nova-2.
    """
    input_path = Path(input_media_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_media_path}")

    if not output_wav_path:
        output_wav_path = str(input_path.parent / f"{input_path.stem}_clean_16k.wav")

    ffmpeg_bin = get_ffmpeg_binary()

    # FFmpeg command:
    # -y: overwrite output
    # -i: input file
    # -vn: strip video stream
    # -acodec pcm_s16le: 16-bit linear PCM
    # -ar 16000: 16kHz sample rate (ideal for speech-to-text)
    # -ac 1: 1 audio channel (mono)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(output_wav_path)
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    return str(output_wav_path)
