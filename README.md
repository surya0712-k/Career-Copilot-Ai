# Career Copilot AI

An **agentic career coach with memory** — not a chatbot. Tell it *"I want a Google internship"* and it analyzes your resume and GitHub, identifies skill gaps, builds a personalized roadmap, conducts mock interviews, and tracks your progress over time.

## Features

- **Resume Analysis** — PDF parsing with GPT-4o structured output
- **GitHub Analysis** — Repo quality, languages, project relevance
- **Gap Detection** — Compares your profile vs. target role (MCP-powered research)
- **Personalized Roadmap** — Week-by-week learning plan with tasks
- **Mock Interviews** — AI interviewer with adaptive Q&A and feedback
- **Long-term Memory** — Qdrant stores vector embeddings; PostgreSQL stores chunk metadata
- **Progress Tracking** — Improvement over time across sessions

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, Tailwind CSS |
| Backend | FastAPI, Python 3.12 |
| Agents | LangGraph, LangChain |
| LLM | OpenAI GPT-4o |
| Vector DB | Qdrant (open source) |
| Relational DB | PostgreSQL |
| MCP | Web search, company research tools |
| Auth | GitHub OAuth + JWT |
| Containers | Docker Compose |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key
- GitHub OAuth App ([create one here](https://github.com/settings/developers))

### Setup

1. Clone and configure environment:

```bash
cp .env.example .env
# Edit .env with your keys:
#   OPENAI_API_KEY=sk-...
#   GITHUB_CLIENT_ID=...
#   GITHUB_CLIENT_SECRET=...
#   NEXT_PUBLIC_GITHUB_CLIENT_ID=... (same as GITHUB_CLIENT_ID)
```

2. Start all services:

```bash
docker compose up --build
```

3. Open the app:

- Frontend: http://localhost:3001
- Backend API: http://localhost:8002
- API Docs: http://localhost:8002/docs

### Local Development (without Docker)

**Backend:**

```bash
cd backend
pip install -e .
# Start PostgreSQL and Qdrant locally, then:
uvicorn app.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

**MCP Server:**

```bash
cd backend
python -m app.mcp.server
```

## User Journey

1. Sign in with GitHub
2. Upload resume (PDF)
3. Set career goal (e.g., "Google Software Engineer Internship")
4. System runs profile analysis → gap detection → roadmap generation
5. View dashboard with gaps, strengths, and roadmap
6. Start mock interview — AI asks adaptive questions and gives feedback
7. Track progress over time via vector memory

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/github` | GitHub OAuth callback |
| POST | `/profiles/resume` | Upload resume PDF |
| POST | `/goals` | Set career goal |
| POST | `/analysis/run` | Run full analysis pipeline |
| GET | `/roadmaps/{id}` | Get roadmap |
| POST | `/interviews` | Start mock interview |
| POST | `/interviews/{id}/turn` | Submit answer (SSE stream) |
| GET | `/progress/me` | Progress summary |

## Architecture

```
User → Next.js → FastAPI → LangGraph Orchestrator
                              ├── Profile Analysis Graph
                              ├── Roadmap Graph
                              ├── Interview Graph
                              └── MCP Research Tools
                                    ↓
                              PostgreSQL (relational)
                                    +
                              Qdrant (vectors)
```

## Phase 2 Roadmap

- Weekly task generation
- Project recommendations
- LLM evaluation harness
- Voice interviews (WebRTC + Whisper)
- AWS deployment (ECS + RDS + S3)

## License

MIT
