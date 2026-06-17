---
title: repo-assistant
sdk: docker
app_port: 7860
pinned: false
---

# repo-assistant: ask questions about any GitHub repo

Point it at any public GitHub repository and ask questions in plain English. It
clones the repo, retrieves the relevant code, and answers with citations to the
exact files and line ranges. It stays grounded in what it retrieved, so it says
"I can't find that" instead of making things up.

**Live demo:** https://sahilrw-repo-assistant.hf.space

---

## What it does

- **Any public repo:** paste a GitHub URL (or pick an example), and it clones and indexes the repo on the fly.
- **Grounded answers with citations:** every claim points to `path:line-range`, and if the context doesn't contain the answer, it says so.
- **Semantic + reranked retrieval:** dense search over code and docs, then a cross-encoder re-ranks the candidates.
- **Streaming everything:** live ingest progress (`clone, chunk, embed, index`) and token-by-token answers.
- **Repo-aware suggestions:** proposes real questions about the indexed repo to get you started.
- **Custom UI:** terminal-inspired frontend with light and dark themes, no framework, served straight from FastAPI.

## How it works

**Ingest** (one-time per repo):

```
clone (shallow) -> walk source files -> chunk (500 chars / 80 overlap)
  -> embed (all-MiniLM-L6-v2) -> store in Chroma + BM25 index
     (each chunk keeps {path, start_line, end_line} for citations)
```

**Query** (per question):

```
question -> semantic search (top 20) -> cross-encoder rerank (top 5)
  -> grounded prompt -> Claude Opus 4.8 -> streamed answer with [path:line] citations
```

## Retrieval, measured

The interesting part isn't "I added reranking", it's measuring whether it
actually helped. Using `evals/test_set.py` (10 question-to-file pairs over
`psf/requests`, scored by `recall@3`):

| Retrieval config | recall@3 | Finding |
|---|---|---|
| Semantic only (baseline) | **80%** | dense search already puts the right file in the top 10 every time (recall@10 = 100%) |
| + Hybrid (BM25 + RRF) | **70%** | hurt: natural-language queries feed BM25 stopword noise, and with no recall headroom fusion just demotes the right chunk |
| + Cross-encoder rerank | **80%** | net wash on this eval, but ships because it sharpens top-3 ordering at no recall cost |

**Takeaway:** on a small, well-structured repo, semantic retrieval is already
near the ceiling, and bolting on "best practices" without measuring would have
made it worse. The shipped pipeline is semantic plus rerank; the hybrid path
stays in the code as a measured experiment.

## Tech stack

- **LLM:** Claude (Opus 4.8) via the Anthropic SDK
- **Embeddings:** `sentence-transformers` (`all-MiniLM-L6-v2`)
- **Reranker:** cross-encoder (`ms-marco-MiniLM-L-6-v2`)
- **Vector store:** Chroma (persistent) plus `rank-bm25`
- **Chunking:** `langchain-text-splitters`
- **Backend:** FastAPI and Uvicorn (streaming responses)
- **Frontend:** hand-written HTML, CSS, and JS, no build step

## Run it locally

```bash
python -m venv .venv
source .venv/Scripts/activate        # Windows
# source .venv/bin/activate          # macOS/Linux

pip install -r requirements.txt

cp .env.example .env                  # then add your ANTHROPIC_API_KEY

python -m uvicorn src.server:app --port 7860
```

Open http://127.0.0.1:7860, paste a repo URL (or click an example), let it
index, then ask. First run downloads the embedding and reranker models
(about 100 MB, one-time).

## Project layout

```
src/
  llm.py       # Anthropic SDK wrapper (ask / stream)
  store.py     # Chroma + BM25 + reranker; add / search / hybrid_search / rerank
  ingest.py    # clone, chunk, embed, index (streams progress)
  rag.py       # retrieve, grounded answer with citations, question suggestions
  server.py    # FastAPI app + static frontend
static/        # custom UI (index.html, styles.css, app.js)
evals/         # recall@k retrieval eval
```
