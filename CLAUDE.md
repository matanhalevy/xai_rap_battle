# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gradio + FastAPI application with UUID-based session logging. Currently a minimal foundation for the larger Grok DJ Rap Battle project—an AI-powered rap battle video generator using xAI APIs.

## Development Commands

### Local Development (Virtual Environment)

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
python -m pip install pip --upgrade
python -m pip install -r requirements.txt

# Run (port 7860)
uvicorn app_gradio_fastapi.main:app --host 127.0.0.1 --port 7860 --reload
```

**Troubleshooting:** If uvicorn isn't found, ensure `venv/bin` is in `$PATH` or use `./venv/bin/uvicorn`.

### Docker

```bash
# Build and run
docker build . --tag app_gradio_fastapi --progress=plain
docker run -d --name app_gradio_fastapi -p 7860:7860 app_gradio_fastapi
docker logs -f app_gradio_fastapi

# Cleanup
docker stop $(docker ps -a -q) && docker rm $(docker ps -a -q)
docker rmi $(docker images -q) -f
```

### Testing Endpoints

```bash
curl http://localhost:7860/health  # Returns {"msg":"ok"}
```

## Architecture

### Current Implementation

```
app_gradio_fastapi/
├── main.py              # FastAPI app + Gradio mount at "/"
├── routes.py            # Health check endpoint (/health)
└── helpers/
    ├── formatters.py    # Request handler with UUID logging decorator
    └── session_logger.py # UUID context tracking via contextvars
```

**Key Pattern:** UUID session logging using Python `contextvars` for request tracing across distributed systems. Every request gets a unique UUID that appears in all log messages.

### Planned Full Architecture (from docs/)

The project aims to build an end-to-end AI rap battle generator:

1. **Beat Generation** → Original instrumental tracks with BPM/bar metadata
2. **Lyric Generation** → Grok API for contextual battle lyrics
3. **Voice Synthesis** → Grok Voice API (primary) / ElevenLabs (fallback)
4. **Audio Mixing** → Combine vocals + beat with proper timing
5. **Video Generation** → Grok Video API for lip-synced battle scenes

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI (Python 3.12+) |
| Frontend | Gradio |
| Server | Uvicorn |
| Container | Docker (python:3.12-bookworm) |
| AI APIs | Grok API (text, voice, video), ElevenLabs (fallback) |
| Audio | pydub, librosa (planned) |
| Video | moviepy, ffmpeg (planned) |

## API Keys (for full implementation)

Required in `.env`:
- `GROK_API_KEY` - xAI Grok API
- `ELEVENLABS_API_KEY` - Fallback voice synthesis (optional)
