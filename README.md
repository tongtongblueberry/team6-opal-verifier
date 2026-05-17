<!-- Changed: document the executable approach and data boundaries for repository users. -->
<!-- Why: leaderboard work must not mix public labels with private leaderboard/test data. -->
# Team 6 Opal Verifier

This repository contains a deterministic verifier for SSD TCG/Opal command-response trajectories.

The main submission entry point is `src/solver.py::predict(dataset)`, which returns lowercase
`pass` or `fail` for each testcase. The solver does not load an LLM at runtime. It converts each
trajectory into canonical events, tracks protocol state, and checks whether the final response is
consistent with the preceding command history.

Heavy pretrained models such as Qwen must not be downloaded into this local repository or committed
to GitHub. If an auxiliary LLM experiment is needed, it should run only on the course server using
the shared model cache documented by the project.

## Data Boundary

No dataset files are committed here.

- Public labeled files under `/dl2026/dataset` are treated as train/dev only.
- Leaderboard feedback must be treated as a separate validation signal, not training labels.
- Private test data is never inspected and must only be used by the official evaluator.

## Project State

See `TODO.md` for the current handoff state, recent leaderboard result, and next actions. See
`docs/rule_coverage_research_ko.md` for the rule-coverage expansion plan.

## Commands

```bash
bash setup.sh
python3 -m compileall src
```

On the course server, copy or clone this repository into the submission workspace and run the
official `evaluate.py` and `submit` commands from that environment.
