# Career Copilot AI — Performance Analysis & Optimization Plan

**Date:** 2026-06-08  
**Stack:** FastAPI · LangGraph · Azure AI Foundry · Qdrant · PostgreSQL · FastMCP · Docker

---

## Executive Summary

The application was slow because **latency is dominated by sequential Azure LLM + embedding round-trips**, not by FastAPI or PostgreSQL. A single onboarding run previously executed **4–5 LLM calls**, **5+ embedding calls**, and **6 web searches** in series, plus a **1–2 minute resume LLM parse before analysis even started**.

**Estimated latency (before optimizations):** 180–600 seconds  
**Estimated latency (after Phase 1 optimizations implemented):** 45–120 seconds  
**Target latency (Phase 2–3 architecture):** see SLA table below

---

## Request Path Timing Breakdown

### 1. Onboarding (`POST /profiles/resume` → `POST /goals` → `POST /analysis/run`)

| Step | File / Function | Before | After Phase 1 | Bottleneck |
|------|---------------|--------|---------------|------------|
| Resume upload | `profiles.upload_resume` → `extract_resume_fast` | 30–120s (structured LLM) | **<1s** (PDF only) | Removed LLM on upload |
| Create goal | `goals.create_goal` → `MemoryStore.store_chunk` | 5–30s | 5–30s | 1 embedding + Qdrant upsert |
| Analysis job | `analysis._run_analysis_job` | 120–480s | 40–90s | See subgraph |
| ↳ seed_resume | `profile.seed_resume_node` | 30–90s | **<0.1s** | Reuses parsed text |
| ↳ parallel_fetch | `profile.parallel_fetch_node` | 60–180s seq | 30–90s parallel | GitHub HTTP + optional DDG |
| ↳ analyze_github | `profile.analyze_github_node` | 30–90s LLM | **0s** (fast mode) | Skipped LLM summarization |
| ↳ research_role | `profile.research_role_node` | 5–25s | **<0.1s** (fast mode) | Skipped DuckDuckGo |
| ↳ detect_gaps | `profile.detect_gaps_node` | 30–120s | 20–60s | 1 structured LLM |
| ↳ store_memory | `profile.store_profile_memory_node` | 15–60s | **0s** critical path | Deferred to background |
| ↳ generate_roadmap | `RoadmapService.generate_initial` | 60–180s | 30–90s | 1 structured LLM; RAG skipped if <4 chunks |
| ↳ persist_roadmap | `RoadmapService.persist_roadmap` | 10–30s | 5–15s | DB only; memory deferred |

**Instrumentation:** `[TIMING]` logs on every LangGraph node via `@timed_node` in `agents/nodes/profile.py`, plus `TimingReport` in `api/routes/analysis.py`.

---

### 2. Coach (`POST /memory/ask`)

| Step | File | Before | After |
|------|------|--------|-------|
| RAG embed + search | `build_rag_hits` | 200–800ms | 200–800ms |
| Progress summary | `get_progress_summary` | 50–150ms | 50–150ms (parallel) |
| Weak areas query | `memory.ask` | 20–50ms | 20–50ms (parallel) |
| LLM reply | `MemoryService.ask` | 1–4s | 1–4s |

**Before:** sequential (~2–5s). **After:** `asyncio.gather` on RAG + progress + weak areas (~1.5–4s).

---

### 3. Interview (`POST /interviews` + turns)

| Step | LLM | Embeddings | Notes |
|------|-----|------------|-------|
| Start session | 1 | 1 | RAG + question |
| Per turn (×4) | 2–3 | 4–8 | evaluate + next Q + memory chunks |
| Final turn | 2 | 3+ | summary + recalc optional |
| **Full 5-turn** | **11–12** | **25–35** | Dominant cost |

**Fix (Phase 2):** batch memory writes per turn; stream question via SSE; skip per-improvement embedding during interview.

---

### 4. Roadmap recalc (`POST /roadmaps/{id}/recalculate`)

| Step | LLM | Embeddings | Qdrant |
|------|-----|------------|--------|
| Load state | 0 | 0 | 0 |
| RAG (limit 15) | 0 | 1 | 1 search |
| Recalc LLM | 1 | 0 | 0 |
| Persist + memory | 0 | 1 | 1 upsert |

**Typical:** 30–90s. **Phase 2:** diff-only recalc for unchanged milestones.

---

### 5. Progress dashboard (`GET /progress/me`)

| Issue | Detail |
|-------|--------|
| Duplicate RAG | Two searches with different queries (limit 15 + limit 5) |
| Extra LLM | Summary generation on every page load |

**Phase 2:** single RAG call; cache summary 5 min.

---

## Bottleneck Table

| Component | Current Behavior | Problem | Recommended Fix | Expected Speedup |
|-----------|------------------|---------|-----------------|------------------|
| Resume upload | Structured LLM parse on every PDF upload | Blocks UI 30–120s before analysis | `extract_resume_fast` — PDF text only (`resume_parser.py`) | **30–120s → <1s** |
| Analysis graph | 5 nodes sequential | 4+ LLM calls in series | Fast mode: 2 LLM calls (gaps + roadmap) | **2–3×** |
| GitHub node | LLM summarizes GitHub JSON | Duplicate with gap analysis | Pass raw JSON to `detect_gaps_node` when `FAST_ONBOARDING=true` | **30–90s saved** |
| Web research | DuckDuckGo HTML scrape | 5–25s, often low value on first run | Skip when `FAST_ONBOARDING=true` | **5–25s saved** |
| Memory store (onboarding) | 3 sequential embed + Qdrant | 15–60s on critical path | `DEFER_MEMORY_WRITES=true` + `store_chunks_parallel` | **15–60s off critical path** |
| Roadmap RAG | Always embed+search | Useless when <4 chunks exist | `count_user_chunks` gate in `RoadmapService.generate_initial` | **1–3s saved** |
| Roadmap prompt | Unlimited milestones/tasks | Large structured JSON output | Max 4 milestones × 3 tasks (`ROADMAP_PROMPT`) | **30–60s saved** |
| Embeddings | No cache, one API call per chunk | N× latency for interviews | `embed_text` / `embed_texts` LRU cache (`memory/store.py`) | **2–5× on repeated text** |
| LLM client | No timeout | Jobs hang forever | `LLM_TIMEOUT_SECONDS=90` (`services/llm.py`) | Fail fast vs infinite hang |
| Uvicorn reload | `--reload` in Docker | Kills background jobs | Removed from `docker-compose.yml` | Prevents infinite "running" |
| Coach ask | Sequential DB + RAG + LLM | Adds 200–500ms overhead | `asyncio.gather` in `MemoryService.ask` | **200–500ms** |
| Interview turns | 1 embed per improvement/strength | 25–35 embeds per session | Batch at end of session (Phase 2) | **60–70% interview time** |
| Progress `/me` | 2 RAG + 1 LLM | 3–8s page load | Single RAG + cached summary (Phase 2) | **2–4s** |
| Goal creation | Immediate embedding | Blocks before analysis | Defer embed to background (Phase 2) | **5–30s** |
| `ensure_collection` | Every analysis run | Redundant Qdrant call | Call once at startup only (Phase 2) | **100–300ms** |
| Job step updates | 4 separate DB commits | Connection churn | Batch in single session (Phase 2) | **50–200ms** |

---

## Implemented Optimizations (Phase 1)

| File | Change |
|------|--------|
| `app/observability/timing.py` | `@timed_node`, `TimingReport`, `timed_step` |
| `app/agents/nodes/profile.py` | Timing on all nodes; fast GitHub; skip web research; defer memory |
| `app/services/resume_parser.py` | `extract_resume_fast()` — no LLM on upload |
| `app/api/routes/profiles.py` | Uses fast extract |
| `app/memory/store.py` | Embedding cache; `store_chunks_parallel`; `embed_text`/`embed_texts` |
| `app/services/career/roadmap.py` | Skip RAG if ≤3 chunks; `write_memory` flag |
| `app/api/routes/analysis.py` | `TimingReport`; deferred memory via `asyncio.create_task` |
| `app/services/career/memory.py` | Parallel coach context fetch |
| `app/services/llm.py` | `timeout` + `max_tokens` |
| `app/config.py` | `FAST_ONBOARDING`, `DEFER_MEMORY_WRITES`, etc. |
| `docker-compose.yml` | No `--reload` on backend |

### Enable in `.env`

```env
FAST_ONBOARDING=true
DEFER_MEMORY_WRITES=true
LLM_TIMEOUT_SECONDS=90
LLM_MAX_TOKENS=2048
```

---

## Redesigned Production Architecture (Phase 2–3)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Next.js   │────▶│  FastAPI (sync)  │────▶│  Redis job queue │
│  SSE stream │     │  return job_id   │     │  (Celery/ARQ)    │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────────┐
                        ▼                               ▼                               ▼
               ┌────────────────┐              ┌─────────────────┐              ┌──────────────────┐
               │ Worker: profile │              │ Worker: roadmap  │              │ Worker: memory   │
               │ 2 LLM parallel  │              │ 1 LLM structured │              │ batch embed      │
               └────────────────┘              └─────────────────┘              └──────────────────┘
                        │                               │                               │
                        └───────────────────────────────┴───────────────────────────────┘
                                                        ▼
                                              ┌─────────────────┐
                                              │ Qdrant + Postgres│
                                              └─────────────────┘
```

### Key architectural changes

1. **Split onboarding into 2 jobs:** profile analysis (return gaps in ~3s with streaming partial JSON) → roadmap generation (background, push via SSE).
2. **Redis embedding cache** shared across workers (replace in-process LRU).
3. **Dedicated worker pool** for LLM calls — API never blocks on Azure.
4. **SSE streaming** for coach + interview questions (`llm.astream`).
5. **Incremental roadmap recalc** — only regenerate weeks with incomplete tasks.
6. **Connection pooling** — single `AsyncSession` per job, not per step update.

---

## SLA Targets vs Reality

| Flow | Target | Phase 1 (now) | Phase 2 (planned) |
|------|--------|---------------|-------------------|
| Profile analysis | <3s | 20–60s | 2–4s (streaming partial) |
| Memory retrieval | <500ms | 200–800ms | 150–400ms (cache) |
| Interview question | <2s | 2–5s | 1–2s (stream first token) |
| Coach response | <4s | 2–5s | 2–4s |
| Roadmap generation | <8s | 30–90s | 6–10s (smaller model / split job) |

**Note:** Sub-3s full profile analysis with gap detection + GitHub requires either a much faster model, aggressive caching, or returning partial results while background work completes.

---

## Top 10 Highest-Impact Optimizations

| Rank | Optimization | Impact | Status |
|------|-------------|--------|--------|
| 1 | Remove LLM from resume upload | 30–120s | ✅ Done |
| 2 | Skip GitHub LLM + web research in fast onboarding | 35–115s | ✅ Done |
| 3 | Defer memory embeddings off critical path | 15–60s | ✅ Done |
| 4 | Remove uvicorn `--reload` in Docker | Prevents hung jobs | ✅ Done |
| 5 | Batch parallel embeddings (`aembed_documents`) | 2–3× embed phase | ✅ Done |
| 6 | Skip RAG on first roadmap (no memories yet) | 1–3s | ✅ Done |
| 7 | Shrink roadmap structured output (4×3 max) | 30–60s | ✅ Done |
| 8 | LLM timeout (fail vs hang forever) | Reliability | ✅ Done |
| 9 | Interview: batch memory writes per session | 60–70% interview time | Phase 2 |
| 10 | Split onboarding: return gaps first, roadmap async | Perceived <3s | Phase 2 |

---

## Implementation Order

1. ✅ Timing instrumentation + fast onboarding flags
2. ✅ Resume fast extract + deferred memory
3. ✅ Embedding cache + batch parallel store
4. ✅ Coach parallel fetch
5. **Next:** Interview batch memory (`InterviewService.evaluate_answer`)
6. **Next:** SSE streaming for coach + interview (`astream`)
7. **Next:** Redis job queue (replace `BackgroundTasks`)
8. **Next:** Incremental roadmap recalc
9. **Next:** Progress dashboard RAG dedup + summary cache
10. **Next:** Dedicated smaller/faster model for structured outputs

---

## Estimated Total Latency

| Scenario | Before | After Phase 1 | After Phase 2 |
|----------|--------|---------------|---------------|
| Full onboarding (upload → dashboard) | **5–10 min** | **1–2 min** | **30–60s perceived** |
| Coach question | 3–6s | 2–5s | 2–4s |
| Interview start | 3–6s | 3–5s | 1–2s |
| Roadmap recalc | 45–120s | 30–90s | 8–15s |
| 5-turn interview | 8–15 min | 8–15 min | 3–5 min |

---

## How to Read Timing Logs

After restart, grep backend logs:

```bash
docker compose logs backend | grep TIMING
```

Example output:

```
[TIMING] node.seed_resume 12ms
[TIMING] node.analyze_github 1842ms
[TIMING] node.detect_gaps 34210ms
[TIMING] analysis_job:... total=87432ms | ensure_collection=120ms | run_full_onboarding=85000ms | persist_roadmap=1200ms
```

Use this to identify which node dominates for your Azure deployment.
