"""
StudyBot - Interactive Chatbot with Video Summarization for Students
Backend: Flask + SQLite + Anthropic Claude API + YouTube Transcript API
"""

import os
import json
import sqlite3
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from functools import wraps

# Load .env file if it exists (no python-dotenv needed)
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

from flask import Flask, request, jsonify, session, render_template, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "studybot.db")

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            email       TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS videos (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            url          TEXT NOT NULL,
            title        TEXT,
            transcript   TEXT,
            created_at   TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS summaries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            type        TEXT NOT NULL,
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (video_id) REFERENCES videos(id),
            FOREIGN KEY (user_id)  REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS chats (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            role        TEXT NOT NULL,
            message     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (video_id) REFERENCES videos(id),
            FOREIGN KEY (user_id)  REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hashed
    except Exception:
        return False


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# YOUTUBE / TRANSCRIPT HELPERS  (Whisper-based)
# ─────────────────────────────────────────────

def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_video_title(video_id: str) -> str:
    """Fetch video title via YouTube oEmbed (no API key needed)."""
    import urllib.request
    try:
        oembed_url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        with urllib.request.urlopen(oembed_url, timeout=8) as resp:
            data = json.loads(resp.read())
            return data.get("title", f"YouTube Video ({video_id})")
    except Exception:
        return f"YouTube Video ({video_id})"


def fetch_transcript(video_id: str) -> tuple[str, str]:
    """
    Strategy:
      1. Try YouTube captions via youtube-transcript-api  → instant (~1s)
      2. If no captions exist, fall back to Whisper       → slow  (1-3 min)

    Returns (title, transcript_text). Raises RuntimeError on total failure.
    """
    title = get_video_title(video_id)

    # ── FAST PATH: YouTube captions ───────────────────────────────────────────
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt_api = YouTubeTranscriptApi()
        fetched  = ytt_api.fetch(video_id)

        # New API returns objects with .text attribute
        parts = []
        for e in fetched:
            if isinstance(e, dict):
                parts.append(e.get("text", ""))
            else:
                parts.append(getattr(e, "text", ""))
        text = " ".join(parts).strip()

        if text:
            print(f"[transcript] ✅ captions fetched instantly for {video_id}")
            return title, text

    except Exception as caption_err:
        print(f"[transcript] ⚠️ caption fetch failed: {type(caption_err).__name__}: {caption_err}")
        print(f"[transcript] falling back to Whisper…")

    # ── SLOW PATH: Whisper (audio download + local transcription) ─────────────
    import tempfile, shutil

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "No captions found and ffmpeg is not installed (needed for Whisper fallback). "
            "Install ffmpeg: brew install ffmpeg  /  sudo apt install ffmpeg"
        )

    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError(
            "No captions found and yt-dlp is not installed (needed for Whisper fallback). "
            "Run: pip install yt-dlp"
        )

    try:
        import whisper
    except ImportError:
        raise RuntimeError(
            "No captions found and openai-whisper is not installed (needed for Whisper fallback). "
            "Run: pip install openai-whisper"
        )

    url = f"https://www.youtube.com/watch?v={video_id}"

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "64",
            }],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            raise RuntimeError(f"yt-dlp audio download failed: {e}")

        mp3_path = audio_path + ".mp3"
        if not os.path.exists(mp3_path):
            raise RuntimeError("Audio file not found after download. Check ffmpeg installation.")

        model_name = os.environ.get("WHISPER_MODEL", "base")
        print(f"[transcript] running Whisper ({model_name}) on {mp3_path}")
        try:
            model  = whisper.load_model(model_name)
            result = model.transcribe(mp3_path, fp16=False)
            text   = result["text"].strip()
        except Exception as e:
            raise RuntimeError(f"Whisper transcription failed: {e}")

    if not text:
        raise RuntimeError("Whisper returned an empty transcript.")

    print(f"[transcript] Whisper done for {video_id}")
    return title, text


# ─────────────────────────────────────────────
# GROQ
# ─────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.1-8b-instant"  # Higher free quota, faster responses


def get_api_key() -> str:
    """Return Groq API key: prefer X-API-Key header, fall back to env var."""
    try:
        header_key = request.headers.get("X-API-Key", "").strip()
        if header_key:
            return header_key
    except RuntimeError:
        pass
    return GROQ_API_KEY


def call_groq(system_prompt: str, messages: list, max_tokens: int = 2000) -> str:
    """Call Groq API using the official SDK (free tier — no billing needed, very fast)."""
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "No API key found. Click the 'API Key' button in the top bar to add your free Groq key."
        )

    print(f"[groq] using key: {api_key[:8]}...{api_key[-4:]} (len={len(api_key)})")

    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=api_key)

    groq_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        groq_messages.append({"role": m["role"], "content": m["content"]})

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=groq_messages,
            max_tokens=max_tokens,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(str(e))


SUMMARY_PROMPTS = {
    "short": "Provide a concise 3-5 sentence summary of the video transcript below. Focus on the core message.",
    "detailed": "Provide a comprehensive detailed summary of the video transcript. Cover all major points, examples, and conclusions.",
    "bullet": "Summarize the video transcript as clear bullet points. Each bullet should capture one key idea. Use sub-bullets where helpful.",
    "key_concepts": "Extract and explain the KEY CONCEPTS from this video transcript. For each concept: give its name, a clear definition, and why it matters.",
    "exam_notes": """Create EXAM-ORIENTED STUDY NOTES from this transcript. Include:
1. 📌 Key Definitions
2. 🔑 Important Concepts
3. ❓ Potential Exam Questions with Answers
4. 💡 Quick Revision Points
Format clearly for a student preparing for an exam.""",
    "timeline": "Create a CHRONOLOGICAL OUTLINE of the video content. Show how the topic progresses from start to finish with timestamps/sections if possible.",
    "mind_map": """Create a TEXT-BASED MIND MAP of the video content.
Central Topic → Main Branches → Sub-branches
Use indentation and ASCII art (→, •, └─) to show relationships.""",
}


CHUNK_SIZE     = 8000   # chars per chunk (~2000 tokens)
CHUNK_OVERLAP  = 200    # overlap to avoid cutting mid-sentence
MAX_CHUNKS     = 6      # max chunks to process (covers ~3 hrs of content)


def chunk_transcript(transcript: str) -> list[str]:
    """Split transcript into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(transcript):
        end = start + CHUNK_SIZE
        chunk = transcript[start:end]
        # Try to end at a sentence boundary
        if end < len(transcript):
            last_period = max(chunk.rfind('. '), chunk.rfind('? '), chunk.rfind('! '))
            if last_period > CHUNK_SIZE * 0.6:
                chunk = chunk[:last_period + 1]
        chunks.append(chunk.strip())
        start += len(chunk) - CHUNK_OVERLAP
        if len(chunks) >= MAX_CHUNKS:
            break
    return [c for c in chunks if c]


def generate_summary(transcript: str, summary_type: str, custom_query: str | None = None) -> str:
    """
    Smart summarization:
    - Short transcripts (<8000 chars): single call, instant
    - Long transcripts: chunk → summarize each → merge into final summary
    """
    prompt = SUMMARY_PROMPTS.get(summary_type, SUMMARY_PROMPTS["short"])

    # ── SHORT VIDEO: single call ──────────────────────────────────────────────
    if len(transcript) <= CHUNK_SIZE:
        if custom_query:
            system = """You are StudyBot, an expert AI tutor.
A student has given you a specific requirement for how they want this video summarized.
Fulfil their request precisely. Use markdown formatting."""
            user_content = f"STUDENT'S REQUEST: {custom_query}\n\nTRANSCRIPT:\n{transcript}"
        else:
            system = f"You are StudyBot, an expert AI tutor.\n{prompt}\nUse markdown formatting."
            user_content = f"TRANSCRIPT:\n{transcript}"
        return call_groq(system, [{"role": "user", "content": user_content}], max_tokens=2000)

    # ── LONG VIDEO: chunk → summarize each chunk → merge ─────────────────────
    chunks = chunk_transcript(transcript)
    total  = len(chunks)
    print(f"[summary] long transcript ({len(transcript):,} chars) → {total} chunks")

    # Step 1: Summarize each chunk briefly
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        print(f"[summary] chunk {i+1}/{total}…")
        sys = "You are a helpful assistant. Summarize the key points from this portion of a video transcript in 3-5 sentences. Be concise and factual."
        result = call_groq(sys, [{"role": "user", "content": f"TRANSCRIPT PORTION {i+1}/{total}:\n{chunk}"}], max_tokens=400)
        chunk_summaries.append(f"**Part {i+1}:** {result.strip()}")

    combined = "\n\n".join(chunk_summaries)

    # Step 2: Final merge pass with the requested format
    if custom_query:
        system = f"""You are StudyBot, an expert AI tutor.
A student has given you a specific requirement: {custom_query}
Below are summaries of each part of a long video. Combine them into a final response that fulfils the student's request.
Use markdown formatting."""
    else:
        system = f"""You are StudyBot, an expert AI tutor.
{prompt}
Below are summaries of each part of a long video. Combine them into one cohesive, well-structured final output.
Use markdown formatting. Be student-friendly."""

    user_content = f"PART-BY-PART SUMMARIES:\n\n{combined}"
    print(f"[summary] merging {total} chunk summaries into final output…")
    return call_groq(system, [{"role": "user", "content": user_content}], max_tokens=2500)


def answer_question(transcript: str, chat_history: list, question: str) -> str:
    system = f"""You are StudyBot, an expert AI tutor. A student is asking questions about a video they just watched.

VIDEO TRANSCRIPT (for reference):
{transcript[:10000]}

Your job:
- Answer questions accurately based on the transcript
- If the answer isn't in the transcript, say so but still try to help with general knowledge
- Be concise, clear, and encouraging
- Use examples and analogies when helpful
- Format with markdown for readability"""

    messages = []
    for h in chat_history[-10:]:  # Last 10 messages for context
        messages.append({"role": h["role"], "content": h["message"]})
    messages.append({"role": "user", "content": question})

    return call_groq(system, messages, max_tokens=1500)


@app.route("/api/validate-key", methods=["POST"])
@login_required
def validate_key():
    import urllib.request, urllib.error
    data = request.get_json()
    key = (data.get("api_key") or "").strip()
    if not key:
        return jsonify({"valid": False, "error": "No key provided"})

    print(f"[validate-key] testing Groq key: {key[:8]}...{key[-4:]} (len={len(key)})")

    try:
        from groq import Groq
        client = Groq(api_key=key)
        client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        print("[validate-key] Groq key is valid ✓")
        return jsonify({"valid": True})
    except Exception as e:
        msg = str(e)
        print(f"[validate-key] error: {msg}")
        return jsonify({"valid": False, "error": msg})




@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("index"))
    return render_template("dashboard.html")


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"error": "Invalid email address"}), 400

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            (username, email, hash_password(password)),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        session.permanent = True
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        return jsonify({"success": True, "username": username})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Username or email already exists"}), 409
    finally:
        conn.close()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()

    if not user or not verify_password(password, user["password"]):
        return jsonify({"error": "Invalid email or password"}), 401

    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return jsonify({"success": True, "username": user["username"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "username": session["username"], "user_id": session["user_id"]})


# ─────────────────────────────────────────────
# ROUTES — VIDEO
# ─────────────────────────────────────────────

@app.route("/api/video/load", methods=["POST"])
@login_required
def load_video():
    data = request.get_json()
    url = (data.get("url") or "").strip()

    if not url:
        return jsonify({"error": "URL is required"}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL"}), 400

    user_id = session["user_id"]
    conn = get_db()

    # Check if already loaded by this user
    existing = conn.execute(
        "SELECT * FROM videos WHERE user_id=? AND url LIKE ?",
        (user_id, f"%{video_id}%"),
    ).fetchone()

    if existing:
        conn.close()
        return jsonify({
            "success": True,
            "video_id": existing["id"],
            "title": existing["title"],
            "cached": True,
        })

    try:
        title, transcript = fetch_transcript(video_id)
        cur = conn.execute(
            "INSERT INTO videos (user_id, url, title, transcript) VALUES (?, ?, ?, ?)",
            (user_id, url, title, transcript),
        )
        conn.commit()
        new_id = cur.lastrowid
        conn.close()
        return jsonify({"success": True, "video_id": new_id, "title": title, "cached": False})
    except RuntimeError as e:
        conn.close()
        return jsonify({"error": str(e)}), 422


@app.route("/api/video/<int:video_id>/summarize", methods=["POST"])
@login_required
def summarize(video_id):
    data = request.get_json()
    summary_type  = data.get("type", "short")
    custom_query  = (data.get("custom_query") or "").strip()
    user_id = session["user_id"]

    if summary_type not in SUMMARY_PROMPTS:
        return jsonify({"error": "Invalid summary type"}), 400

    conn = get_db()
    video = conn.execute(
        "SELECT * FROM videos WHERE id=? AND user_id=?", (video_id, user_id)
    ).fetchone()
    if not video:
        conn.close()
        return jsonify({"error": "Video not found"}), 404

    # Custom queries bypass cache (they're unique per request)
    if not custom_query:
        cached = conn.execute(
            "SELECT * FROM summaries WHERE video_id=? AND user_id=? AND type=?",
            (video_id, user_id, summary_type),
        ).fetchone()
        if cached:
            conn.close()
            return jsonify({"success": True, "summary": cached["content"], "cached": True})

    try:
        summary = generate_summary(video["transcript"], summary_type, custom_query or None)

        # Only cache standard (non-custom) summaries
        if not custom_query:
            conn.execute(
                "INSERT INTO summaries (video_id, user_id, type, content) VALUES (?, ?, ?, ?)",
                (video_id, user_id, summary_type, summary),
            )
            conn.commit()
        conn.close()
        return jsonify({"success": True, "summary": summary, "cached": False})
    except RuntimeError as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@app.route("/api/video/<int:video_id>/chat", methods=["POST"])
@login_required
def chat(video_id):
    data = request.get_json()
    question = (data.get("message") or "").strip()
    user_id = session["user_id"]

    if not question:
        return jsonify({"error": "Message is required"}), 400

    conn = get_db()
    video = conn.execute(
        "SELECT * FROM videos WHERE id=? AND user_id=?", (video_id, user_id)
    ).fetchone()
    if not video:
        conn.close()
        return jsonify({"error": "Video not found"}), 404

    history = conn.execute(
        "SELECT role, message FROM chats WHERE video_id=? AND user_id=? ORDER BY created_at ASC",
        (video_id, user_id),
    ).fetchall()

    try:
        answer = answer_question(video["transcript"], [dict(h) for h in history], question)

        # Store both user question and assistant answer
        conn.execute(
            "INSERT INTO chats (video_id, user_id, role, message) VALUES (?, ?, ?, ?)",
            (video_id, user_id, "user", question),
        )
        conn.execute(
            "INSERT INTO chats (video_id, user_id, role, message) VALUES (?, ?, ?, ?)",
            (video_id, user_id, "assistant", answer),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "answer": answer})
    except RuntimeError as e:
        conn.close()
        return jsonify({"error": str(e)}), 500


@app.route("/api/video/<int:video_id>/history")
@login_required
def chat_history(video_id):
    user_id = session["user_id"]
    conn = get_db()
    history = conn.execute(
        "SELECT role, message, created_at FROM chats WHERE video_id=? AND user_id=? ORDER BY created_at ASC",
        (video_id, user_id),
    ).fetchall()
    conn.close()
    return jsonify({"history": [dict(h) for h in history]})


@app.route("/api/videos")
@login_required
def list_videos():
    user_id = session["user_id"]
    conn = get_db()
    videos = conn.execute(
        "SELECT id, url, title, created_at FROM videos WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (user_id,),
    ).fetchall()
    conn.close()
    return jsonify({"videos": [dict(v) for v in videos]})


@app.route("/api/video/<int:video_id>/clear-chat", methods=["POST"])
@login_required
def clear_chat(video_id):
    user_id = session["user_id"]
    conn = get_db()
    conn.execute("DELETE FROM chats WHERE video_id=? AND user_id=?", (video_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/tts", methods=["POST"])
@login_required
def text_to_speech():
    """Convert summary text to MP3 using gTTS and return it for browser playback."""
    import tempfile
    data = request.get_json()
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    # Truncate to ~3000 words to keep audio reasonable length
    words = text.split()
    if len(words) > 3000:
        text = " ".join(words[:3000]) + "..."

    try:
        from gtts import gTTS
    except ImportError:
        return jsonify({"error": "gTTS not installed. Run: pip install gTTS"}), 500

    try:
        tts = gTTS(text=text, lang="en", slow=False)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        tmp.close()

        from flask import send_file
        return send_file(
            tmp.name,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="summary.mp3"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n✅ StudyBot running at http://localhost:{port}")
    print(f"   Set GROQ_API_KEY in .env before starting!\n")
    app.run(debug=True, port=port)