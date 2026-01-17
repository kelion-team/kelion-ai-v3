<<<<<<< HEAD
# Kelion AI (K1) – Full WebGL Interface + Backend (AI + Web Search + STT + TTS + Persistent Memory + Admin Audit)

This package is a single deployable app:
- WebGL hologram UI (Three.js CDN, 100% online)
- Backend API implementing the functional structure described in KELION_STRUCTURE_COMPLETE.md:
  - /api/login
  - /api/chat
  - /api/contact_submit
  - /api/dashboard
  - /api/pricing
  - /api/plans
  - /api/subscribe
- Voice:
  - STT: /api/stt (microphone -> transcription)
  - TTS: backend generates MP3 and the UI plays it
- Persistent memory + audit (SQLite)
  - Admin-only: /admin/audit , /admin/messages

## Required environment variables
- OPENAI_API_KEY
- K1_ADMIN_TOKEN

Optional:
- K1_API_TOKEN (protect /api/chat and /api/stt with X-API-Token)
- OPENAI_MODEL (default gpt-5)
- OPENAI_REASONING_EFFORT (default low)
- OPENAI_TTS_MODEL (default gpt-4o-mini-tts)
- OPENAI_TTS_VOICE (default onyx)
- OPENAI_STT_MODEL (default gpt-4o-mini-transcribe)

## Run locally (Docker)
```bash
docker build -t kelion-k1 .
docker run -p 8080:8080   -e OPENAI_API_KEY=...   -e K1_ADMIN_TOKEN=...   kelion-k1
```
Open: http://localhost:8080/

## Deploy (Railway)
Deploy as a Docker service. Railway will detect Dockerfile. Set env vars in Railway.


## Railway Deploy (optional)
Set env vars: RAILWAY_TOKEN, RAILWAY_SERVICE_ID, RAILWAY_PROJECT_ID, RAILWAY_DOMAIN.
Optional protection: DEPLOY_API_KEY.
Endpoints: /api/railway/health , /api/railway/config , /api/railway/info , POST /api/railway/deploy.


## Cinematic lip-sync (timestamps)
Backend generates TTS audio, then transcribes that audio with verbose_json + word timestamps, and returns a viseme timeline to the UI.
Best results if the GLB includes viseme morph targets (names containing 'viseme'); otherwise it falls back to amplitude-based jaw/mouth movement.


# FINAL PRESENCE UI (READ/WRITE)
This build uses a minimal presence-based UI:
- No landing pages or marketing CTAs
- Two tabs only: READ (output) and WRITE (input)
- Hologram is the main visual element; background is subtle and business-friendly
- Version + local date/time are displayed in the top bar

## Deploy (Railway / any PaaS)
1) Required environment variables:
   - OPENAI_API_KEY
   - K1_ADMIN_TOKEN
2) Recommended:
   - K1_API_TOKEN (protect /api/chat and /api/stt; client sends header X-API-Token)
   - K1_SOURCE_ALLOWLIST (comma-separated domains; restrict web-search sources)
   - DEPLOY_API_KEY (protect /api/railway/deploy endpoint)
3) Start command:
   - gunicorn app:app --bind 0.0.0.0:$PORT
4) Health checks:
   - GET /health
   - GET /api/railway/health (if Railway vars set)

## Admin / Compliance Notes
- Users cannot delete history or memory from the UI.
- Audit logs are stored server-side; access is admin-only (X-Admin-Token).
- Any deletion requests must be processed manually by admin/legal authority.

=======
# kelion-ai-v3
KELION AI v3.0.0 - WebGL Hologram Neural Assistant
>>>>>>> 895721eae6220917da2b50278c62911f2e018246
