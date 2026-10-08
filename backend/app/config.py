import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Local model tiers, mapped to what's already pulled via `ollama list`.
LOCAL_MODELS = {
    "fast": "qwen3:4b",
    "general": "qwen3:8b",
    "coding": "qwen3:8b",
}

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIMS = 768

# Cloud model used when a task is escalated or local is unavailable/busy.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://nexus:nexus_dev_password@localhost:5432/nexus"
)

MEMORY_RETRIEVAL_K = int(os.getenv("MEMORY_RETRIEVAL_K", "5"))

# Research agent's first tool (Level 0 - automatic).
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Voice pipeline (Phase 4) - prebuilt CPU binaries + local model weights.
_VOICE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "voice")
WHISPER_CLI = os.getenv(
    "WHISPER_CLI", os.path.join(_VOICE_DIR, "bin", "whisper", "Release", "whisper-cli.exe")
)
WHISPER_MODEL = os.getenv(
    "WHISPER_MODEL", os.path.join(_VOICE_DIR, "models", "ggml-base.en.bin")
)
PIPER_EXE = os.getenv("PIPER_EXE", os.path.join(_VOICE_DIR, "bin", "piper", "piper", "piper.exe"))
PIPER_VOICE = os.getenv(
    "PIPER_VOICE", os.path.join(_VOICE_DIR, "models", "piper", "en_US-lessac-medium.onnx")
)
FFMPEG_EXE = os.getenv(
    "FFMPEG_EXE",
    r"C:\Users\kusha\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe",
)
