# 🎓 StudyBot — Interactive Chatbot with Video Summarization for Students

> An AI-powered web app that summarizes YouTube videos and lets students have a full conversation with a chatbot that knows the video inside out.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔐 User Accounts | Register/login with email & password — fully private per-user data |
| 🎥 YouTube Summarizer | Paste any YouTube URL with captions to get an instant summary |
| 7 Summary Modes | Quick, Detailed, Bullet Points, Key Concepts, Exam Notes, Timeline, Mind Map |
| 💬 AI Chatbot | Chat with Claude AI about the video — full transcript context |
| 🧠 Chat Memory | All Q&A history is saved per video per user |
| 📚 History Sidebar | Quickly switch between all your past videos |
| 📋 Copy to Clipboard | Export any summary with one click |
| 🌙 Dark Mode UI | Clean, modern, student-friendly dark theme |

---

## 🚀 Quick Start

### 1. Clone / Download the project folder

```
studybot/
├── app.py              ← Flask backend (main server)
├── run.py              ← Easy launcher script
├── requirements.txt    ← Python dependencies
├── database/           ← Auto-created SQLite DB
└── templates/
    ├── index.html      ← Login / Register page
    └── dashboard.html  ← Main app UI
```

### 2. Install ffmpeg (required for audio processing)

| OS | Command |
|---|---|
| Mac | `brew install ffmpeg` |
| Linux | `sudo apt install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH |

### 3. Install Python dependencies

```bash
pip install flask yt-dlp openai-whisper anthropic
```

> **Note:** `openai-whisper` will download the Whisper model (~75 MB for `base`) on first transcription run. This is cached locally for future use.

### 3. Get your Anthropic API key

1. Go to [https://console.anthropic.com](https://console.anthropic.com)
2. Create an account and go to **API Keys**
3. Create a new key and copy it

### 4. Set your API key

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

**Windows CMD:**
```cmd
set ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Windows PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

### 5. Run the app

```bash
python run.py
```

Then open your browser at: **http://localhost:5000**

---

## 🎯 How to Use

1. **Create an account** — your data is private and saved to your profile
2. **Paste a YouTube URL** — any video with auto-generated or manual captions
3. **Choose a summary mode** — pick what kind of notes you need
4. **Chat with the AI tutor** — ask questions, get explanations, quiz yourself
5. **Switch between videos** — all your history is saved in the sidebar

---

## 📋 Summary Modes Explained

| Mode | Best For |
|---|---|
| ⚡ Quick | Fast 5-sentence overview |
| 📋 Detailed | Comprehensive notes covering everything |
| • Bullet Points | Skimmable key points |
| 🧠 Key Concepts | Definitions and explanations of main ideas |
| 📚 Exam Notes | Definitions + potential questions + quick revision |
| ⏱ Timeline | Chronological outline of the content |
| 🗺 Mind Map | Visual text-based topic map |

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 + Flask |
| Database | SQLite (via Python `sqlite3`) |
| AI | Anthropic Claude (claude-sonnet-4) |
| Transcripts | `yt-dlp` (download audio) + `openai-whisper` (transcribe locally) |
| Frontend | HTML5 + CSS3 + Vanilla JavaScript |
| Markdown | `marked.js` (CDN) |
| Fonts | Google Fonts (Syne + DM Sans) |

---

## 📁 Project Architecture

```
User Request
     ↓
Flask Router (app.py)
     ↓
Auth Check (session-based)
     ↓
YouTube Transcript API → transcript text
     ↓
Anthropic Claude API → summary / chat response
     ↓
SQLite DB (store summaries, chat history)
     ↓
JSON Response → Browser renders with JS
```

---

## ⚠️ Notes

- **YouTube videos must have captions** (auto-generated or manual). Videos without captions cannot be transcribed.
- The app uses **session-based authentication** — sessions persist for 7 days.
- All data is stored locally in `database/studybot.db` — no external database needed.
- Chat history is stored per video per user — switch videos anytime without losing context.

---

## 🔧 Troubleshooting

**"Could not fetch transcript" / yt-dlp error**
→ Make sure `ffmpeg` is installed and on your PATH. Run `ffmpeg -version` to verify.

**Transcription is slow**
→ Whisper `base` model takes ~1 min per 10 min of video on CPU. Set `WHISPER_MODEL=tiny` for faster (less accurate) results, or `WHISPER_MODEL=small` / `medium` for better accuracy.

```bash
export WHISPER_MODEL=tiny   # fastest
export WHISPER_MODEL=small  # good balance
```

**"ANTHROPIC_API_KEY not set"**
→ Set your API key as shown in step 4 above.

**Port already in use**
→ Run with: `PORT=5001 python run.py`

---

## 🎓 For Students

This app was built as a student project demonstrating:
- Full-stack Python web development (Flask)
- RESTful API design
- SQLite database with user auth
- Integration with LLM APIs (Anthropic Claude)
- YouTube transcript processing
- Modern responsive UI design

---

*Built with ❤️ for students, by students.*
