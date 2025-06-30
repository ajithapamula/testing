# 🎥 AI-Powered Video Meeting Processing & Documentation Generator

This project is a full-stack AI-powered video processing API built with **FastAPI**, **MongoDB**, **SQL Server**, and **OpenAI GPT-4**. It enables uploading meeting videos, compressing and denoising them, transcribing the audio, generating rich implementation guides, technical documentation, mind maps, and storing results securely in databases.

> 🧠 **Core Feature**: Converts raw meeting recordings into structured implementation guides, transcripts, and mind map visuals using `Whisper`, `GPT-4`, and `Graphviz`.

---

## 🚀 Features

- 📁 Upload video recordings via API
- 🗜️ Compress and denoise video/audio (using `ffmpeg`)
- 🔊 Split audio into 5-minute FLAC chunks
- 🤖 Transcribe using OpenAI Whisper
- 📄 Auto-generate implementation guides using GPT-4
- 🌐 Enhance documentation with real-world web context (via DuckDuckGo)
- 🧠 Generate mind map visualizations from GPT output (`graphviz`)
- 🧾 Save transcript and documentation in `.docx` format
- 💾 Store data in **MongoDB** and validate in **SQL Server**
- 🌐 API endpoints for upload, health check, and logging

---

## 🧱 Tech Stack

| Component         | Technology                              |
|------------------|------------------------------------------|
| Backend API       | FastAPI                                 |
| Transcription     | OpenAI Whisper                          |
| Summarization     | GPT-4 via OpenAI API                    |
| Audio/Video Tools | FFmpeg                                  |
| Documentation     | `python-docx`, Graphviz                 |
| Database (NoSQL)  | MongoDB                                 |
| Database (SQL)    | SQL Server (ODBC Driver 17)             |
| Search Context    | DuckDuckGo Search + BeautifulSoup       |

---

## 📂 Folder Structure

