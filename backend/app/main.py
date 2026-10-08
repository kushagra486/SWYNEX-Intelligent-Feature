import logging

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from . import actions, memory, voice
from .db import init_db, close_db
from .router import route_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nexus.main")

app = FastAPI(title="Bharat AI Nexus - Core API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    await init_db()
    logger.info("database ready (pgvector schema ensured)")


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()


class ChatRequest(BaseModel):
    prompt: str
    tier: str = "general"  # fast | general | coding | reasoning | vision
    session_id: int | None = None


@app.get("/health")
def health():
    return {"status": "ok", "service": "nexus-core"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from Nexus Core"}


@app.post("/api/sessions")
async def create_session():
    session_id = await memory.create_session()
    return {"session_id": session_id}


@app.get("/api/sessions/{session_id}/history")
async def get_history(session_id: int):
    if not await memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"messages": await memory.recent_history(session_id)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id
    if session_id is None:
        session_id = await memory.create_session(title=req.prompt[:60])
    elif not await memory.session_exists(session_id):
        raise HTTPException(status_code=404, detail="session not found")

    context_msgs = await memory.retrieve_context(session_id, req.prompt)
    if context_msgs:
        context_block = "\n".join(f"{m['role']}: {m['content']}" for m in context_msgs)
        augmented_prompt = (
            "Relevant memory from earlier in this conversation:\n"
            f"{context_block}\n\n"
            f"Current message:\n{req.prompt}"
        )
    else:
        augmented_prompt = req.prompt

    try:
        result = await route_chat(augmented_prompt, req.tier)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"All providers failed: {exc}")

    await memory.save_message(session_id, "user", req.prompt)
    await memory.save_message(session_id, "assistant", result["text"])

    result["session_id"] = session_id
    result["memory_hits"] = len(context_msgs)
    return result


class ToolCallRequest(BaseModel):
    tool: str
    params: dict = {}


@app.post("/api/tools/call")
async def call_tool(req: ToolCallRequest):
    try:
        return await actions.request_action(req.tool, req.params)
    except actions.UnknownTool as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/api/actions/pending")
async def pending_actions():
    return {"pending": await actions.list_pending()}


@app.post("/api/actions/{action_id}/approve")
async def approve(action_id: int):
    return await actions.approve_action(action_id)


@app.post("/api/actions/{action_id}/reject")
async def reject(action_id: int):
    return await actions.reject_action(action_id)


@app.post("/api/voice/transcribe")
async def voice_transcribe(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()
    suffix = "." + audio.filename.rsplit(".", 1)[-1] if "." in (audio.filename or "") else ".wav"
    try:
        text = await voice.transcribe(audio_bytes, suffix=suffix)
    except voice.VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"text": text}


class SpeakRequest(BaseModel):
    text: str


@app.post("/api/voice/speak")
async def voice_speak(req: SpeakRequest):
    try:
        wav_bytes = await voice.synthesize(req.text)
    except voice.VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return Response(content=wav_bytes, media_type="audio/wav")
