<!-- Changed: archive the public20 10/10 TRL SFT dataset generation worker output. -->
<!-- Why: GPU training workers need exact dataset paths, commands, counts, and no-test-split/non-synthetic boundaries. -->

# public20 10/10 TRL SFT dataset generation

- 작성 시각: 2026-05-27 05:35:57 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 입력 split root: `runs/model_validation/public20_10_10_splits`
- 출력 root: `runs/model_validation/public20_trl_sft_10_10/datasets`
- 목적: public20-only model validation용 TRL prompt/completion dataset 생성.
- synthetic-data 여부: 아님. 이 산출물은 public20 model validation only이며 Self-Instruct generated synthetic data가 아니다.
- public20 test split: 생성하지 않음. `train`/`validation`만 생성했다.
- 기존 16/4 dataset: 삭제/이동하지 않음.

## Generation Commands

```bash
for seed in 11 29 47; do
  python3 tools/training/prepare_public20_sft_dataset.py \
    --split-dir "runs/model_validation/public20_10_10_splits/split_seed_${seed}" \
    --output-dir "runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_${seed}"

  python3 tools/training/prepare_public20_sft_dataset.py \
    --split-dir "runs/model_validation/public20_10_10_splits/split_seed_${seed}" \
    --output-dir "runs/model_validation/public20_trl_sft_10_10/datasets/retrieved_seed_${seed}" \
    --retrieved-spec-rules-md docs/legacy_spec_rules.md \
    --retrieved-spec-top-k 3 \
    --retrieved-spec-max-context-chars 1200
done
```

## Output Paths

- `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_11`
- `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_29`
- `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_47`
- `runs/model_validation/public20_trl_sft_10_10/datasets/retrieved_seed_11`
- `runs/model_validation/public20_trl_sft_10_10/datasets/retrieved_seed_29`
- `runs/model_validation/public20_trl_sft_10_10/datasets/retrieved_seed_47`

각 directory는 `train.jsonl`, `validation.jsonl`, `public20_trl_sft_dataset_report.json`,
`public20_trl_sft_dataset_report.md`를 포함한다.

## Row Counts

| dataset | train rows | train fail | train pass | validation rows | validation fail | validation pass | retrieved context |
|---|---:|---:|---:|---:|---:|---:|---|
| plain_seed_11 | 10 | 5 | 5 | 10 | 5 | 5 | no |
| plain_seed_29 | 10 | 5 | 5 | 10 | 5 | 5 | no |
| plain_seed_47 | 10 | 5 | 5 | 10 | 5 | 5 | no |
| retrieved_seed_11 | 10 | 5 | 5 | 10 | 5 | 5 | yes |
| retrieved_seed_29 | 10 | 5 | 5 | 10 | 5 | 5 | yes |
| retrieved_seed_47 | 10 | 5 | 5 | 10 | 5 | 5 | yes |

## Retrieval / Leakage Boundary

- Plain datasets were generated without `--retrieved-spec-top-k`.
- Retrieved datasets used `docs/legacy_spec_rules.md` with `--retrieved-spec-top-k 3` and
  `--retrieved-spec-max-context-chars 1200`.
- Reported retrieval flags:
  - `label_used_for_retrieval=false`
  - `runtime_rule_engine=false`
  - `source_path=docs/legacy_spec_rules.md`
- Retrieved row metadata source spans all start with `docs/legacy_spec_rules.md:`.
- The retrieval method is deterministic lexical overlap over prompt input text only; it does not read public labels.

## Verification Commands

```bash
for d in runs/model_validation/public20_trl_sft_10_10/datasets/*_seed_*; do
  jq -s '{path: input_filename, rows:length, completions:(map(.completion)|group_by(.)|map({(.[0]):length})|add), source_splits:(map(.source_split)|group_by(.)|map({(.[0]):length})|add), retrieved_rows:(map(has("retrieved_spec_context"))|group_by(.)|map({(.[0]|tostring):length})|add)}' "$d/train.jsonl"
  jq -s '{path: input_filename, rows:length, completions:(map(.completion)|group_by(.)|map({(.[0]):length})|add), source_splits:(map(.source_split)|group_by(.)|map({(.[0]):length})|add), retrieved_rows:(map(has("retrieved_spec_context"))|group_by(.)|map({(.[0]|tostring):length})|add)}' "$d/validation.jsonl"
done

jq -r '[.output_dir, (.outputs[] | [.output_split,.row_count,.label_counts.fail,.label_counts.pass,.source_path] | @tsv), "test_split=" + (.public20_test_split_created|tostring), "retrieved=" + (.retrieved_spec_context.enabled|tostring), "retrieval_source=" + (.retrieved_spec_context.source_path|tostring), "label_used_for_retrieval=" + (.retrieved_spec_context.label_used_for_retrieval|tostring), "runtime_rule_engine=" + (.retrieved_spec_context.runtime_rule_engine|tostring)] | .[]' \
  runs/model_validation/public20_trl_sft_10_10/datasets/*_seed_*/public20_trl_sft_dataset_report.json

rg -n 'runs/model_validation/public20_10_10_splits/split_seed_(11|29|47)' \
  runs/model_validation/public20_trl_sft_10_10/datasets/*_seed_*/public20_trl_sft_dataset_report.json

jq -s '{rows:length, bad_source_span:[.[] | select(has("retrieved_spec_context")) | .retrieved_spec_context[] | select((.source_span|startswith("docs/legacy_spec_rules.md:"))|not)]|length, missing_retrieved:[.[] | select(has("retrieved_spec_context")|not)]|length}' \
  runs/model_validation/public20_trl_sft_10_10/datasets/retrieved_seed_*/train.jsonl \
  runs/model_validation/public20_trl_sft_10_10/datasets/retrieved_seed_*/validation.jsonl

jq -s '{rows:length, unexpected_retrieved:[.[] | select(has("retrieved_spec_context"))]|length}' \
  runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_*/train.jsonl \
  runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_*/validation.jsonl

git diff --check
```

## Verification Result

- Dataset generation commands: pass.
- `jq` counts: pass. Every dataset has `train=10`, `validation=10`, and each split has `fail=5`, `pass=5`.
- Source split path grep: pass. Reports point to `runs/model_validation/public20_10_10_splits/split_seed_{11,29,47}`.
- Retrieved context source span check: pass. Retrieved rows `60`, `bad_source_span=0`, `missing_retrieved=0`.
- Plain retrieval absence check: pass. Plain rows `60`, `unexpected_retrieved=0`.
- No public20 test split: pass. All reports have `public20_test_split_created=false`.
- Synthetic data boundary: pass. These are public20 model validation artifacts only, not accepted/generated synthetic data.
- `git diff --check`: pass.
