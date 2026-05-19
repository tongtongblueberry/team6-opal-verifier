<!-- Changed: update README to reflect rule engine + LoRA override architecture. -->
<!-- Why: RAG hybrid is no longer used. Current approach is rule engine (71.50 base) + LoRA fine-tuned override for false positives. -->
# Team 6 Opal Verifier

A **rule engine + LoRA override** solver for SSD TCG/Opal command-response trajectory pass/fail
classification.

## Architecture

The entry point is `src/solver.py::Solver.predict(dataset)`, which returns `{id: "pass"/"fail"}`.

```
Trajectory --> Rule Engine (StatefulOpalVerifier) --> prediction + rule_id
                                                         |
                        SPECIFIC RULE FIRED <------------+
                        (high confidence)                |
                             |               UNEXPECTED_ERROR_STATUS
                             |               (aggressive: unexplained error = fail)
                             |                           |
                             |               LoRA Override (Qwen3.5-4B + LoRA adapter)
                             |               "Is this really a fail, or a false positive?"
                             |                           |
                             |               LoRA says pass --> override to pass
                             |               LoRA says fail --> keep fail
                             |                           |
                             +---------- final prediction <--------+
```

- **High confidence cases** (~70%): deterministic rule engine, no LLM needed
- **UNEXPECTED_ERROR_STATUS cases** (~30%): rule engine says "fail" (all unexplained errors),
  LoRA fine-tuned model reviews to rescue false positives

The rule engine handles all protocol-specific checks (session tracking, authentication, field
semantics, payload validation). The key to 71.50 is `UNEXPECTED_ERROR_STATUS` -- an aggressive
rule that flags any unexplained error status as "fail". The LoRA adapter corrects false positives
where the error was actually valid.

### Key Discovery

The 71.50 score comes from the aggressive `UNEXPECTED_ERROR_STATUS` approach: any error status
that the rule engine cannot explain is classified as "fail". This is correct for most hidden test
cases. Post-71.50 attempts to soften this (changing to `DEFAULT_PASS`) caused a regression to 68.00.

### LoRA Fine-Tuning (4B v2)

- **Base model**: Qwen/Qwen3.5-4B
- **Method**: LoRA (Hu et al., ICLR 2022) on attention projections (q, k, v, o)
- **Training data**: 2163 cases (rule-engine-generated metamorphic + synthetic + public)
- **Format**: Rich format with full trajectory (table/column/UID/payload)
- **Label masking**: Loss computed only on answer tokens ("pass" / "fail")
- **Best result**: fail precision 100%, fail recall 46.9%, accuracy 89.7% on synthetic test set

[EXTERNAL KNOWLEDGE] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR 2022. https://arxiv.org/abs/2106.09685

## Key Files

| File | Purpose |
|------|---------|
| `src/solver.py` | Entry point. Rule engine (best-71.50 base) + LoRA override for UNEXPECTED_ERROR_STATUS |
| `src/lora_solver.py` | LoRA adapter loading and prediction |
| `src/rag.py` | BM25 retrieval + LLM judge (legacy, not used in submission) |
| `tools/finetune_lora_v2.py` | LoRA training with rich format + label masking |
| `tools/sweep_lora.py` | Hyperparameter sweep script |
| `tools/eval_lora.py` | LoRA evaluation on synthetic test set |
| `tools/intermediate_eval.py` | Public train/dev evaluation |
| `tools/mutation_eval.py` | Mutation testing adequacy framework |
| `artifacts/lora_adapter_v2/` | Trained 4B LoRA adapter (~32MB) |

## Data Boundary

No dataset files are committed here.

- Public labeled files under `/dl2026/dataset` are treated as train/dev only.
- Leaderboard feedback must be treated as a separate validation signal, not training labels.
- Private test data is never inspected and must only be used by the official evaluator.
- Heavy pretrained models (Qwen etc.) are not committed. They are downloaded on the server only.
- LoRA adapters are committed in `artifacts/` (< 12GB total).

## Commands

Local (no GPU needed -- pure rule engine):
```bash
bash setup.sh
python3 -m compileall src tools
```

Server setup (first time):
```bash
bash setup.sh   # includes peft installation
```

Server evaluation:
```bash
python3 tools/intermediate_eval.py --dataset-root /dl2026/dataset
```

LoRA hyperparameter sweep:
```bash
nohup python3 tools/sweep_lora.py > /workspace/team6/sweep.log 2>&1 &
```

LoRA main training (after sweep):
```bash
nohup python3 tools/sweep_lora.py --main > /workspace/team6/main_train.log 2>&1 &
```

## Project State

See `TODO.md` for the current handoff state, recent leaderboard result, and next actions.
