import { useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [hello, setHello] = useState("connecting to Nexus Core...");
  const [error, setError] = useState(null);

  const [prompt, setPrompt] = useState("");
  const [tier, setTier] = useState("general");
  const [reply, setReply] = useState(null);
  const [loading, setLoading] = useState(false);

  const [recording, setRecording] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [speakReply, setSpeakReply] = useState(true);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioRef = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/api/hello`)
      .then((res) => res.json())
      .then((data) => setHello(data.message))
      .catch(() => setError("Could not reach the backend. Is it running on :8000?"));
  }, []);

  async function sendChat(e, promptOverride) {
    if (e) e.preventDefault();
    const text = promptOverride ?? prompt;
    if (!text.trim()) return;
    setLoading(true);
    setReply(null);
    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: text, tier }),
      });
      const data = await res.json();
      setReply(data);
      if (speakReply && data.text) {
        await playReply(data.text);
      }
    } catch (err) {
      setReply({ text: "Request failed. Is the backend running?" });
    } finally {
      setLoading(false);
    }
  }

  async function playReply(text) {
    try {
      const res = await fetch(`${API_URL}/api/voice/speak`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
      }
    } catch {
      // voice is best-effort; chat text still shows either way
    }
  }

  async function toggleRecording() {
    if (recording) {
      mediaRecorderRef.current?.stop();
      setRecording(false);
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setVoiceStatus("transcribing...");
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const form = new FormData();
        form.append("audio", blob, "recording.webm");
        try {
          const res = await fetch(`${API_URL}/api/voice/transcribe`, {
            method: "POST",
            body: form,
          });
          const data = await res.json();
          setVoiceStatus("");
          if (data.text) {
            setPrompt(data.text);
            sendChat(null, data.text);
          }
        } catch {
          setVoiceStatus("transcription failed");
        }
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch {
      setVoiceStatus("microphone access denied");
    }
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "4rem", maxWidth: 640 }}>
      <h1>Bharat AI Nexus</h1>
      <p style={{ opacity: 0.7 }}>One Intelligence. Every Device. Infinite Possibilities.</p>
      <p>{error ? `⚠ ${error}` : hello}</p>

      <hr style={{ margin: "2rem 0" }} />

      <h2>Chat (routed: local Ollama, cloud Groq fallback)</h2>
      <form onSubmit={sendChat} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask Nexus something, or use the mic..."
          rows={3}
          style={{ padding: "0.5rem", fontSize: "1rem" }}
        />
        <select value={tier} onChange={(e) => setTier(e.target.value)} style={{ padding: "0.5rem" }}>
          <option value="fast">fast</option>
          <option value="general">general</option>
          <option value="coding">coding</option>
          <option value="reasoning">reasoning (cloud-preferred)</option>
        </select>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button type="submit" disabled={loading} style={{ padding: "0.5rem 1rem", cursor: "pointer" }}>
            {loading ? "Thinking..." : "Send"}
          </button>
          <button
            type="button"
            onClick={toggleRecording}
            style={{
              padding: "0.5rem 1rem",
              cursor: "pointer",
              background: recording ? "#e33" : "#eee",
              color: recording ? "white" : "black",
            }}
          >
            {recording ? "⏹ Stop" : "🎙 Speak"}
          </button>
          <label style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <input type="checkbox" checked={speakReply} onChange={(e) => setSpeakReply(e.target.checked)} />
            speak replies
          </label>
          {voiceStatus && <span style={{ fontSize: "0.85rem", opacity: 0.7 }}>{voiceStatus}</span>}
        </div>
      </form>

      <audio ref={audioRef} style={{ display: "none" }} />

      {reply && (
        <div style={{ marginTop: "1.5rem", padding: "1rem", background: "#f4f4f4", borderRadius: 8 }}>
          <p style={{ whiteSpace: "pre-wrap", color: "#111" }}>{reply.text}</p>
          {reply.provider && (
            <p style={{ fontSize: "0.8rem", opacity: 0.6, color: "#111" }}>
              provider: {reply.provider} · model: {reply.model} · {reply.latency_ms}ms
              {reply.fallback_from ? ` · fell back from ${reply.fallback_from}` : ""}
            </p>
          )}
        </div>
      )}
    </main>
  );
}
