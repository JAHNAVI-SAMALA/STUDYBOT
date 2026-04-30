#!/usr/bin/env python3
"""
StudyBot — Interactive Chatbot with Video Summarization for Students
Setup & Run Script
"""

import os
import sys
import subprocess

BANNER = """
╔══════════════════════════════════════════════════════════╗
║         🎓 StudyBot — AI Video Learning Assistant        ║
║         Built with Flask + Groq AI + YouTube API         ║
╚══════════════════════════════════════════════════════════╝
"""

# Required packages: (pip_name, import_name)
REQUIRED = [
    ("flask",                   "flask"),
    ("youtube-transcript-api",  "youtube_transcript_api"),
    ("groq",                    "groq"),
    ("yt-dlp",                  "yt_dlp"),
    ("openai-whisper",          "whisper"),
]

def check_and_install():
    print("Checking dependencies...")

    # Check ffmpeg
    import shutil
    if shutil.which("ffmpeg"):
        print("   ffmpeg found")
    else:
        print("   WARNING: ffmpeg NOT found on PATH!")
        print("      Mac:   brew install ffmpeg")
        print("      Linux: sudo apt install ffmpeg")
        print("      Win:   https://ffmpeg.org/download.html")
        print("      (Only needed for videos without captions)\n")

    # Only install truly missing packages
    missing = []
    for pkg, import_name in REQUIRED:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"   Installing missing: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install"] + missing + ["--quiet"]
        )
        print("   Done installing")
    else:
        print("   All dependencies already installed")


def check_api_key():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        print("\nWARNING: GROQ_API_KEY not set!")
        print("   Get your FREE key at: https://console.groq.com/keys")
        key = input("   Paste your Groq API key (or Enter to skip): ").strip()
        if key:
            os.environ["GROQ_API_KEY"] = key
            print("   Key set for this session")
        else:
            print("   No key set -- you can add it via the API Key button in the app")
    else:
        print(f"   GROQ_API_KEY found (gsk_...{key[-6:]})")


def run():
    print(BANNER)
    check_and_install()
    check_api_key()

    sys.path.insert(0, os.path.dirname(__file__))
    from app import app, init_db
    init_db()
    print("\n   Database ready")

    port = int(os.environ.get("PORT", 5000))
    print(f"\nStudyBot running at: http://localhost:{port}")
    print("   Press Ctrl+C to stop\n")

    app.run(debug=False, port=port, host="0.0.0.0")


if __name__ == "__main__":
    run()

#https://youtu.be/TEJpeRI_NEo?si=bxskiQ2bcsg6wmV2
#https://youtu.be/IrQKDdptiw8?si=6kNmNN9lK8YZLbJW