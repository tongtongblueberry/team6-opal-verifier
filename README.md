<!-- Changed: update README to reflect RAG+LLM hybrid solver architecture. -->
<!-- Why: the solver now uses confidence-gated hybrid: rule engine + RAG/LLM fallback. -->
# Team 6 Opal Verifier

A **confidence-gated hybrid solver** for SSD TCG/Opal command-response trajectory pass/fail
classification.

## Architecture

The entry point is `src/solver.py::Solver.predict(dataset)`, which returns `{id: "pass"/"fail"}`.

```
Trajectory → Rule Engine (StatefulOpalVerifier) → prediction + confidence
                                                         │
                             HIGH confidence ←───────────┤
                             (specific rule fired)        │
                                  │                  LOW confidence
                                  │                  (DEFAULT_PASS)
                                  │                       │
                                  │         Query extraction + BM25 retrieval
                                  │         over TCG/Opal spec documents
                                  │                       │
                                  │         LLM judgment (Qwen3.5-27B-FP8)
                                  │                       │
                                  └──────── final prediction ◄──────┘
```

- **High confidence cases** (~70%): deterministic rule engine, no LLM needed
- **Low confidence cases** (~30%): RAG retrieves relevant spec passages, LLM judges pass/fail

The rule engine handles all protocol-specific checks (session tracking, authentication, field
semantics, payload validation). The LLM handles unmodeled error statuses that the rule engine
cannot explain.

Reference: Lewis et al. (2020), *Retrieval-Augmented Generation for Knowledge-Intensive Language
Tasks*, NeurIPS 2020.

## Key Files

| File | Purpose |
|------|---------|
| `src/solver.py` | Entry point. Confidence-gated hybrid: rule engine + RAG/LLM |
| `src/rag.py` | BM25 retrieval over spec chunks + Qwen3.5-27B-FP8 LLM judge |
| `tools/download_model.py` | Pre-download LLM on server (run once) |
| `tools/intermediate_eval.py` | Public train/dev evaluation |
| `tools/build_spec_index.py` | Guidebook chunk index builder |
| `tools/mutation_eval.py` | Mutation testing adequacy framework |

## Data Boundary

No dataset files are committed here.

- Public labeled files under `/dl2026/dataset` are treated as train/dev only.
- Leaderboard feedback must be treated as a separate validation signal, not training labels.
- Private test data is never inspected and must only be used by the official evaluator.
- Heavy pretrained models (Qwen etc.) are not committed. They are downloaded on the server only.

## Commands

Local (no GPU needed — RAG disabled, pure rule engine):
```bash
bash setup.sh
python3 -m compileall src tools
```

Server setup (first time):
```bash
python3 tools/download_model.py --model Qwen/Qwen3.5-27B-FP8
```

Server evaluation:
```bash
python3 tools/intermediate_eval.py --dataset-root /dl2026/dataset
```

## Project State

See `TODO.md` for the current handoff state, recent leaderboard result, and next actions.
