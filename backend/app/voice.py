"""Local voice pipeline: whisper.cpp for STT, Piper for TTS. Both run as CPU
subprocesses against prebuilt binaries + downloaded model weights under
voice/ — no cloud dependency, matching the zero-cost principle.

Subprocesses run via asyncio.to_thread + subprocess.run (not
asyncio.create_subprocess_exec) because the app's event loop is the Selector
policy (required by psycopg's async mode), and Windows' Selector loop does
not implement subprocess transports — only Proactor does.
"""

import asyncio
import os
import subprocess
import tempfile
import uuid

from . import config


class VoiceError(Exception):
    pass


def _run_ffmpeg_to_wav(in_path: str, wav_path: str) -> None:
    result = subprocess.run(
        [
            config.FFMPEG_EXE,
            "-y", "-i", in_path,
            "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
            wav_path,
        ],
        capture_output=True,
    )
    if result.returncode != 0 or not os.path.exists(wav_path):
        raise VoiceError(f"ffmpeg transcode failed: {result.stderr.decode(errors='ignore')}")


def _run_whisper(in_path: str, out_prefix: str) -> None:
    result = subprocess.run(
        [
            config.WHISPER_CLI,
            "-m", config.WHISPER_MODEL,
            "-f", in_path,
            "-otxt",
            "-of", out_prefix,
            "-nt",  # no timestamps
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise VoiceError(f"whisper-cli failed: {result.stderr.decode(errors='ignore')}")


async def transcribe(audio_bytes: bytes, suffix: str = ".wav") -> str:
    """Transcode arbitrary input audio to 16kHz mono WAV via ffmpeg, then run
    whisper.cpp over it and return the transcribed text. Browsers record
    WebM/Opus by default, which whisper.cpp cannot decode directly.
    """
    if not os.path.exists(config.WHISPER_CLI):
        raise VoiceError(f"whisper-cli.exe not found at {config.WHISPER_CLI}")
    if not os.path.exists(config.WHISPER_MODEL):
        raise VoiceError(f"whisper model not found at {config.WHISPER_MODEL}")
    if not os.path.exists(config.FFMPEG_EXE):
        raise VoiceError(f"ffmpeg.exe not found at {config.FFMPEG_EXE}")

    tmp_dir = tempfile.gettempdir()
    token = uuid.uuid4().hex
    in_path = os.path.join(tmp_dir, f"nexus-voice-{token}{suffix}")
    wav_path = os.path.join(tmp_dir, f"nexus-voice-{token}.16k.wav")
    out_prefix = wav_path + ".out"

    with open(in_path, "wb") as f:
        f.write(audio_bytes)

    try:
        await asyncio.to_thread(_run_ffmpeg_to_wav, in_path, wav_path)
        await asyncio.to_thread(_run_whisper, wav_path, out_prefix)

        txt_path = out_prefix + ".txt"
        if not os.path.exists(txt_path):
            raise VoiceError("whisper-cli did not produce output text")
        with open(txt_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        return text
    finally:
        for p in (in_path, wav_path, out_prefix + ".txt"):
            if os.path.exists(p):
                os.remove(p)


def _run_piper(text: str, out_path: str) -> None:
    result = subprocess.run(
        [config.PIPER_EXE, "-m", config.PIPER_VOICE, "-f", out_path],
        input=text.encode("utf-8"),
        capture_output=True,
    )
    if result.returncode != 0 or not os.path.exists(out_path):
        raise VoiceError(f"piper failed: {result.stderr.decode(errors='ignore')}")


async def synthesize(text: str) -> bytes:
    """Run Piper over text and return WAV audio bytes."""
    if not os.path.exists(config.PIPER_EXE):
        raise VoiceError(f"piper.exe not found at {config.PIPER_EXE}")
    if not os.path.exists(config.PIPER_VOICE):
        raise VoiceError(f"piper voice model not found at {config.PIPER_VOICE}")

    tmp_dir = tempfile.gettempdir()
    out_path = os.path.join(tmp_dir, f"nexus-voice-{uuid.uuid4().hex}.wav")

    try:
        await asyncio.to_thread(_run_piper, text, out_path)
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(out_path):
            os.remove(out_path)
