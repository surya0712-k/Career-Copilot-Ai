# Career Copilot AI

An **agentic career coach with memory** — not a chatbot. Set a goal like *Google Software Engineer Internship*, upload your resume, and the system analyzes your profile, detects skill gaps, builds a personalized weekly roadmap, runs mock interviews (text and voice), and tracks progress over time using vector memory.

---

## Features

### Profile & analysis
- **Resume parsing** — PDF upload with structured skill/experience extraction
- **GitHub analysis** — Repo quality, languages, stars, and relevance to your target role
- **Gap detection** — Compares your profile vs. target role with evidence-based readiness scoring
- **Async onboarding** — Gap analysis completes first; roadmap builds in the background so you reach the dashboard faster

### Roadmap
- **Weekly milestones** — Up to 4 weeks, 3 tasks each, sequenced as Week 1, 2, 3…
- **Practice vs. project tasks** — LeetCode/DSA drills stay as normal tasks; real-world builds appear as **Project 1**, **Project 2**, etc.
- **Task completion** — Toggle tasks complete/incomplete; progress syncs to the dashboard
- **DSA language preference** — Python, Java, C++, JavaScript, or Go (saved to profile + memory)
- **Recalculate roadmap** — Regenerate remaining weeks based on progress and interview feedback

### Interviews
- **Text mock interviews** — Streaming Q&A with per-answer feedback and session summary
- **Voice mock interviews (LiveKit)** — Real-time STT/TTS with Azure LLM; milestone-aware context from your roadmap
- **Custom practice projects** — Add up to 2 projects for voice mocks (not added to resume)

### Memory & coaching
- **Long-term memory** — Qdrant vector store + PostgreSQL metadata for RAG across sessions
- **Career Coach** — Ask questions grounded in your memory, gaps, and progress
- **Progress tracking** — Readiness score, study hours, weak areas, and completion percentage

---

## User journey

```
Sign in with GitHub
       ↓
   Dashboard  ←── landing page for new and returning users
       ↓
  Add a Goal  (if no active goal)
       ↓
 Upload resume + set target (company, role, level)
       ↓
 Start Analysis  →  gaps appear on dashboard, roadmap builds async
       ↓
 View roadmap  →  complete tasks, set DSA language, add custom projects
       ↓
 Mock interviews  (text or LiveKit voice)  →  feedback stored in memory
       ↓
 Recalculate roadmap / ask Coach as you improve
```

Returning users skip resume upload if one is already on file.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React, Tailwind CSS, livekit-client |
| Backend | FastAPI, Python 3.12, SQLAlchemy (async), Alembic |
| Agents | LangGraph, LangChain, structured LLM outputs |
| LLM & embeddings | Azure AI Foundry (OpenAI-compatible API) |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL 16 |
| Voice | LiveKit Cloud (STT/TTS) + livekit-agents worker |
| MCP | Company/role research tools (optional web search) |
| Auth | GitHub OAuth 2.0 + JWT |
| Containers | Docker Compose |

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│  Next.js    │────▶│   FastAPI    │────▶│  LangGraph onboarding       │
│  :3001      │     │   :8002      │     │  profile → gaps → roadmap   │
└─────────────┘     └──────┬───────┘     └──────────────┬──────────────┘
                           │                            │
              ┌────────────┼────────────┐               │
              ▼            ▼            ▼               ▼
        PostgreSQL     Qdrant      MCP Server    Azure AI Foundry
        (relational)   (vectors)    :8080         (chat + embeddings)
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
        livekit-agent              Career Coach RAG
        (voice interviewer)        (/memory/ask)
```

**Data split**
- **PostgreSQL** — users, goals, profiles, roadmaps, milestones, interviews, progress, analysis jobs
- **Qdrant** — embedding chunks (resume insights, gaps, roadmap updates, interview summaries, DSA preference)

---

## Project structure

```
Career Copilot AI/
├── frontend/           # Next.js app (pages, API client)
├── backend/
│   ├── app/
│   │   ├── agents/     # LangGraph nodes & prompts
│   │   ├── api/routes/ # REST endpoints
│   │   ├── memory/     # Qdrant store & retriever
│   │   ├── services/   # Roadmap, interview, readiness, resume parser
│   │   └── mcp/        # MCP server & client
│   └── alembic/        # DB migrations
├── livekit-agent/      # Voice interviewer worker (career-interviewer)
├── docker-compose.yml
└── .env.example
```

---

## Quick start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker + Compose)
- [GitHub OAuth App](https://github.com/settings/developers) — callback URL: `http://localhost:3001/auth/callback`
- [Azure AI Foundry](https://ai.azure.com) — deploy a chat model and an embedding model
- [LiveKit Cloud](https://cloud.livekit.io) — for voice interviews (optional but recommended)

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with at minimum:

| Variable | Description |
|----------|-------------|
| `AZURE_FOUNDRY_ENDPOINT` | OpenAI-compatible endpoint URL |
| `AZURE_FOUNDRY_API_KEY` | Foundry API key |
| `LLM_MODEL` | Chat deployment name |
| `EMBEDDING_MODEL` | Embedding deployment name |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | OAuth credentials |
| `JWT_SECRET` | Random secret string |
| `NEXT_PUBLIC_GITHUB_CLIENT_ID` | Same as `GITHUB_CLIENT_ID` |
| `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit Cloud credentials |

### 2. Start services

```bash
docker compose up --build
```

Migrations run automatically on backend startup (`alembic upgrade head`).

### 3. Open the app

| Service | URL |
|---------|-----|
| **App (frontend)** | http://localhost:3001 |
| **API** | http://localhost:8002 |
| **API docs (Swagger)** | http://localhost:8002/docs |
| **Qdrant dashboard** | http://localhost:6333/dashboard |
| **MCP server** | http://localhost:8080 |

### 4. First run

1. Click **Sign in with GitHub** → you land on the **Dashboard**
2. Click **Add a Goal**
3. Upload your resume (PDF) and set company, role, and level
4. Click **Start Analysis** — gaps appear on the dashboard; the roadmap loads when ready
5. Open **View Full Roadmap** to work through tasks and start voice mocks

---

## Docker services

| Service | Port | Purpose |
|---------|------|---------|
| `frontend` | 3001 | Next.js dev server |
| `backend` | 8002 → 8001 | FastAPI API |
| `postgres` | 5432 | PostgreSQL |
| `qdrant` | 6333 | Vector database |
| `mcp-server` | 8080 | MCP research tools |
| `livekit-agent` | — | Voice interviewer worker (connects to LiveKit Cloud) |

Restart the voice agent after code changes:

```bash
docker compose restart livekit-agent
```

---

## Environment variables

See [`.env.example`](.env.example) for the full list. Highlights:

**Performance tuning** (recommended for faster onboarding):

```env
FAST_ONBOARDING=true
DEFER_MEMORY_WRITES=true
SPLIT_ONBOARDING_PHASES=true
LLM_ONBOARDING_MAX_TOKENS=1024
```

| Flag | Effect |
|------|--------|
| `FAST_ONBOARDING` | Skips extra LLM pass on GitHub data |
| `DEFER_MEMORY_WRITES` | Writes Qdrant chunks after dashboard redirect |
| `SPLIT_ONBOARDING_PHASES` | Returns gaps early; roadmap continues async |
| `SKIP_WEB_RESEARCH` | Skips MCP web search during role research |

**LiveKit voice models** (defaults work on LiveKit Cloud):

```env
LIVEKIT_STT_MODEL=deepgram/nova-3
LIVEKIT_TTS_MODEL=cartesia/sonic-2
```

---

## API reference

All protected routes require `Authorization: Bearer <token>` from GitHub sign-in.

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/github` | Exchange OAuth code for JWT |
| GET | `/auth/me` | Current user |

### Profile & goals
| Method | Path | Description |
|--------|------|-------------|
| GET | `/profiles/me` | Profile + gap analysis |
| POST | `/profiles/resume` | Upload resume PDF |
| PATCH | `/profiles/me/preferences` | DSA language preference |
| POST | `/goals` | Create goal (deactivates prior goals) |
| GET | `/goals/active` | Active goal |
| GET/PUT | `/goals/{id}/practice-projects` | Custom mock-interview projects (max 2) |

### Analysis
| Method | Path | Description |
|--------|------|-------------|
| POST | `/analysis/run` | Start analysis job `{ goal_id }` |
| GET | `/analysis/jobs/{id}` | Poll job status / phase |
| GET | `/analysis/me` | Profile with latest gap analysis |

### Roadmaps
| Method | Path | Description |
|--------|------|-------------|
| GET | `/roadmaps/{id}` | Roadmap with milestones & tasks |
| GET | `/roadmaps/goal/{goal_id}/latest` | Latest roadmap for a goal |
| PATCH | `/roadmaps/{id}/tasks/{milestone_id}/{task_index}` | Toggle task completion |
| POST | `/roadmaps/{id}/recalculate` | Regenerate remaining weeks |

### Interviews
| Method | Path | Description |
|--------|------|-------------|
| POST | `/interviews` | Start text interview session |
| POST | `/interviews/{id}/turn` | Submit answer (SSE stream) |
| POST | `/interviews/voice/summary` | Save voice session summary |
| GET | `/interviews/{id}` | Session with turns |

### LiveKit
| Method | Path | Description |
|--------|------|-------------|
| POST | `/livekit/token` | Room token + agent dispatch (optional `goal_id`, `roadmap_id`, `milestone_id`) |

### Progress & memory
| Method | Path | Description |
|--------|------|-------------|
| GET | `/progress/me` | Progress summary, weak areas, readiness |
| POST | `/progress/study-session` | Log study time |
| POST | `/memory/ask` | Career Coach (RAG) |
| GET | `/memory/search` | Search memory chunks |

---

## Local development (without Docker)

**PostgreSQL & Qdrant** must be running locally (or use Docker only for those two).

```bash
# Backend
cd backend
pip install -e .
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# MCP server (separate terminal)
python -m app.mcp.server

# LiveKit agent (separate terminal)
cd livekit-agent
pip install -r requirements.txt
python agent.py start

# Frontend
cd frontend
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL=http://localhost:8001` if running the backend on 8001 directly.

---

## Frontend routes

| Route | Description |
|-------|-------------|
| `/` | Landing / sign in |
| `/dashboard` | Gaps, roadmap preview, progress, actions |
| `/onboarding` | Resume upload + goal setup + analysis |
| `/roadmap/[id]` | Full roadmap, tasks, DSA language, custom projects |
| `/interview/new` | Text mock interview |
| `/interview/voice` | LiveKit voice mock (supports `?roadmapId=&milestoneId=&goalId=`) |
| `/coach` | Career Coach chat |

---

## Troubleshooting

**Analysis job returns 404 when polling**  
Ensure the backend committed the job before returning from `POST /analysis/run`. Restart backend if a stale `running` job exists (marked failed on startup).

**CORS errors on 500 responses**  
The API attaches CORS headers on error responses; check backend logs for the underlying exception.

**Voice interview: two voices / double hello**  
Disconnect fully before reconnecting. Restart `livekit-agent` after updates. Do not open multiple voice interview tabs.

**Readiness score unchanged across profiles**  
Re-run analysis via **Update Goal → Start Analysis** after backend updates; scores are computed per analysis run.

**Returning user forced to re-upload resume**  
Use **Add a Goal** from the dashboard; skip upload if a resume is already on file.

**GitHub OAuth redirect mismatch**  
Callback must exactly match: `http://localhost:3001/auth/callback` in both GitHub App settings and `.env`.

---

## License

MIT
