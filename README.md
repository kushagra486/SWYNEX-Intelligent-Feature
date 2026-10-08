# Bharat AI Nexus

One Intelligence. Every Device. Infinite Possibilities.

Local-first, model-agnostic Personal AI Operating System. See `Bharat_AI_Nexus_Project_Report.pdf` (architecture) and `Bharat_AI_Nexus_Build_Plan.docx` (hardware-aware build plan) in the parent folder for full context.

## Status

- **Phase 0** — folder structure, Postgres+pgvector / Redis via Docker Compose, FastAPI backend, Next.js frontend.
- **Phase 1** — model router (`app/router.py`): local Ollama first, Groq cloud fallback, two-way failover. `/api/chat`.
- **Phase 2** — memory (`app/memory.py`, `app/db.py`): pgvector-backed conversation history with cosine-similarity retrieval injected into every prompt. `/api/sessions`, `/api/sessions/{id}/history`.
- **Phase 3** — permissions + tools (`app/permissions.py`, `app/tools.py`, `app/actions.py`): 5-tier permission model (Project Report §19). Level 0-1 tools run automatically; level 2+ create a pending action that must be approved. First tool: `web_search` (level 0, needs a free Tavily key). Every call is logged. `/api/tools/call`, `/api/actions/pending`, `/api/actions/{id}/approve|reject`.
- **Phase 4** — voice (`app/voice.py`): local STT/TTS, fully offline. whisper.cpp (CPU) transcribes, Piper (CPU) speaks — both prebuilt Windows binaries under `voice/bin/`, model weights under `voice/models/` (gitignored, ~350MB total, see download links below). Browser audio (WebM/Opus) is transcoded to 16kHz mono WAV via ffmpeg before whisper.cpp, since it can't decode WebM directly. `/api/voice/transcribe`, `/api/voice/speak`. The chat UI has a mic button and speaks replies back.
- **Phase 5** — coding agent (`app/sandbox.py`, `app/coding_agent.py`): generate → run in an ephemeral, network-isolated (`--network none`), resource-capped (256MB/1 CPU) Docker container → if it fails, feed the error back to the model and retry (2 retries by default) → give up and report all attempts if still failing. Registered as the `coding_task` tool (Level 1, automatic) — call it via `/api/tools/call`.
- **Phase 6** — first full demo (`app/webagent.py`, `app/playwright_check_script.py`): the flagship loop from the Project Report (design → code → build → test → fix → verify). Generates a self-contained HTML page, loads it in headless Chromium with all network blocked, checks for JS/console errors, retries with the error fed back if it fails. Registered as the `build_webpage` tool (Level 1, automatic). Verification also runs a structural HTML lint (`app/htmllint.py`: stray `<`, mismatched/unclosed tags, missing doctype/title) because browsers silently repair bad markup — an early run passed a page with a stray `<` that only a lint pass catches. Lint and browser errors share one retry loop.

## Running it

1. Copy `.env.example` to `.env` and adjust if needed (add `GROQ_API_KEY` / `TAVILY_API_KEY` to activate cloud fallback and live search — both optional, everything else works without them). Groq model defaults to `openai/gpt-oss-120b`; override with `GROQ_MODEL` if Groq retires it. Local models expected: `qwen3:8b` (all local tiers) and `nomic-embed-text` (embeddings for memory).
2. Start the data layer:
   ```
   docker compose up -d
   ```
3. Make sure Ollama is running locally with at least one model pulled (`ollama list`).
4. Start the backend (on Windows, use `run.py`, not `uvicorn` directly — it sets the event loop policy psycopg's async mode needs):
   ```
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python run.py
   ```
5. Start the frontend:
   ```
   cd ui
   npm install
   npm run dev
   ```
6. Open http://localhost:3000 and use the chat box — it routes through the model router, remembers context across turns via pgvector, and logs every tool call it makes.

### Voice setup (Phase 4)

The binaries are already in `voice/bin/` (whisper.cpp CPU build, Piper). Model weights aren't committed (too large for git) — download them once:

```
mkdir voice\models\piper
curl -L -o voice\models\ggml-base.en.bin https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
curl -L -o voice\models\piper\en_US-lessac-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
curl -L -o voice\models\piper\en_US-lessac-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

Also needs `ffmpeg` on PATH (or set `FFMPEG_EXE` in `.env`) — browsers record WebM/Opus, which whisper.cpp can't read directly, so it's transcoded to WAV first.

## Structure

- `core/` — orchestrator, planner, model router, permissions, context manager
- `memory/` — working/session/episodic/semantic/project memory
- `models/` — llm, vision, speech, embeddings adapters
- `agents/` — research, coding, browser, vision, design, automation
- `devices/` — device gateway (phones, desktop agents, Home Assistant)
- `integrations/` — external services (Groq, NVIDIA NIM, GitHub, search API)
- `ui/` — Next.js dashboard
- `backend/` — FastAPI core API
- `workers/` — scheduled/background jobs
- `security/` — permission engine, secrets handling
- `monitoring/` — health checks, metrics, logs

**V0.1 scope (Phases 0-6) is now complete** — this is the boundary the build plan draws for your current hardware. Phases 7+ (vision, image/video generation, multi-device, smart home, 3D) are deliberately deferred; none of them are needed to demonstrate the core architecture working end to end.
