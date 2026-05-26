<!-- Changed: mark this directory as mock-only parser/judge fixture storage. -->
<!-- Why: raw fixture checks must not be mistaken for accepted synthetic data or Gate artifacts. -->

# Self-Instruct Gate Wiring Fixtures

These files are mock fixtures for unit tests only.

- `mock_raw_outputs.jsonl` is a parser-compatible raw LLM output wrapper with a
  spec-grounded candidate inside `raw_output`.
- `mock_judge_results_required_booleans.jsonl` is a judge response fixture that
  keeps `decision` at `accept` while flipping each required boolean once.

They are not accepted synthetic data, are not stored under `runs/`, and do not
declare Gate A/B/C pass.
