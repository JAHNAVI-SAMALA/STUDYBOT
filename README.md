🚀 StudyBot
🎓 AI-Powered Video Learning Assistant

Transform long YouTube lectures into structured notes, interactive Q&A, and audio summaries — all in one place.

🌐 Demo

📽️ Demo Video:
👉 https://your-video-link.com

🚀 Live App: (Coming Soon)

🧠 Problem It Solves

Students spend hours:

Watching long lectures
Replaying videos for notes
Switching between tools

StudyBot compresses this entire process into a single AI pipeline.

⚡ Core System Pipeline
YouTube Video
   ↓
Transcript Extraction (yt-dlp / Whisper)
   ↓
AI Summarization (Claude API)
   ↓
Context-Aware Chatbot
   ↓
Audio Generation (gTTS)

👉 Designed as an end-to-end AI learning system, not just a summarizer.

✨ Key Features
🎥 Smart Video Processing
Handles videos with/without captions
Uses Whisper fallback for robustness
🧾 Advanced Summarization Modes
Quick Summary
Detailed Notes
Bullet Points
Key Concepts
Exam Notes
Timeline View
Mind Map
💬 Context-Aware AI Chatbot
Ask questions based on video content
Maintains contextual understanding
🔊 Audio Learning Mode
Converts summaries into speech
Enables passive learning
🔐 User System
Authentication & session handling
Personalized history
📚 Learning History
Stores videos, summaries, and queries
Useful for revision
🛠️ Tech Stack
Layer	Technology
Backend	Flask (Python)
Frontend	HTML, CSS, JavaScript
Database	SQLite
AI Engine	Claude (Anthropic API)
Transcription	Whisper + yt-dlp
Audio	gTTS
🏗️ System Design Highlights
Handles missing transcripts using Whisper fallback
Maintains context-aware conversations per video
Optimized for modular AI pipeline processing
Separation of concerns across:
API layer
Processing pipeline
Storage layer
📁 Project Structure
studybot/
├── app.py
├── run.py
├── templates/
├── static/
├── database/
⚠️ Limitations
Performance drops for very long videos
No visual (diagram/image) understanding yet
API-dependent system
🔮 Future Improvements
Multi-language summarization
Visual content understanding (charts/diagrams)
Faster processing pipeline
Mobile application
👩‍💻 Contributors
Samala Jahnavi
Mahveen Zaakia
Katakam Akshitha
📜 License

MIT License

💡 Why This Project Matters

This project demonstrates:

✅ Full-stack development
✅ Real-world AI integration
✅ End-to-end system design
✅ Practical EdTech solution

*Built with ❤️ for students, by students.*
