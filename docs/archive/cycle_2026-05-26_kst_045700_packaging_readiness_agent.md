# 2026-05-26 KST 04:57 - Packaging readiness agent 기록

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- agent 역할: best adapter merged package 및 leaderboard gate 검토
- 기준 코드:
  - `tools/eval/select_manifest_sweep_candidate.py`
  - `tools/eval/prepare_submit.sh`
  - `tools/eval/export_merged_model.py`
  - `tools/eval/check_submit_package.py`
  - `tools/eval/runtime_smoke_submit_package.py`
  - `src/solver.py`
  - `setup.sh`

## 핵심 판정

[Original Text/Data] → `cycle_2026-05-26_kst_044320_step6_threshold_aware_selector.md`는 전체 sweep 완료 후 selector를 다시 실행하라고 기록했다.

[Exact Interpretation] → r32/r64 결과가 나오기 전에는 최종 best adapter를 확정하면 안 된다.

[Detailed Explanation/Example] → 현재 3개 r16 결과 기준 threshold-aware best는 `r16_lr5e4_do10_ep5@0.70`이지만, r32/r64가 완료되면 `threshold_aware_candidate_final.json`을 새로 생성해 `best.adapter_final`과 `best.threshold`를 다시 확인해야 한다.

## 패키징 명령 순서

[Original Text/Data] → `export_merged_model.py`는 `PeftModel.merge_and_unload()` 후 safetensors/tokenizer/manifest를 `artifacts/merged_model`에 저장한다.

[Exact Interpretation] → 최종 후보는 LoRA adapter-only가 아니라 merged artifact package로 만들어야 한다.

[Detailed Explanation/Example] → 사용자 지적처럼 12GB 제한에서 3MB adapter만 제출하는 것은 package capacity를 거의 쓰지 않는다. 최종 best adapter는 `artifacts/merged_model`로 export하고, package size `<12GB`, static gate, offline first-forward를 통과해야 한다.

서버 실행 순서:

```bash
cd /workspace/team6/team6-opal-verifier

RUN_ROOT=/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep
SWEEP_JSON=$RUN_ROOT/artifacts/manifest_lora_sweep_results.json
CAND_JSON=$RUN_ROOT/artifacts/threshold_aware_candidate_final.json
CAND_MD=$RUN_ROOT/artifacts/threshold_aware_candidate_final.md

python3 tools/eval/select_manifest_sweep_candidate.py \
  --sweep-json "$SWEEP_JSON" \
  --output-json "$CAND_JSON" \
  --output-md "$CAND_MD" \
  --format markdown

BEST_ADAPTER=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["best"]["adapter_final"])' "$CAND_JSON")
BEST_THRESHOLD=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["best"]["threshold"])' "$CAND_JSON")

test -n "$BEST_ADAPTER"
test -f "$BEST_ADAPTER/adapter_config.json"

bash tools/eval/prepare_submit.sh "$BEST_ADAPTER" --name "cycle3-best-merged-th${BEST_THRESHOLD}"

SUBMIT_DIR=$(python3 -c 'import os,re,sys; p=sys.argv[1]; b=os.path.basename(p); gp=os.path.basename(os.path.dirname(os.path.dirname(p))); name=gp if b.startswith("checkpoint-") else b; print("/workspace/team6/submit-"+re.sub(r"[^a-zA-Z0-9_-]","-",name))' "$BEST_ADAPTER")

python3 tools/eval/export_merged_model.py \
  --base-model Qwen/Qwen3.5-4B \
  --adapter-dir "$BEST_ADAPTER" \
  --output-dir "$SUBMIT_DIR/artifacts/merged_model" \
  --max-shard-size 4GB \
  --torch-dtype float16 \
  --device-map auto \
  --overwrite

python3 tools/eval/check_submit_package.py "$SUBMIT_DIR"

OPAL_THRESHOLD="$BEST_THRESHOLD" \
python3 tools/eval/runtime_smoke_submit_package.py \
  --package-dir "$SUBMIT_DIR" \
  --offline \
  --first-forward

du -sh "$SUBMIT_DIR"
```

## Threshold Lock

[Original Text/Data] → `src/solver.py`는 `OPAL_THRESHOLD`가 없으면 기본 threshold `0.70`을 사용한다.

[Exact Interpretation] → 최종 best threshold가 `0.70`이면 현재 package runtime 기본값과 일치한다. 최종 best threshold가 `0.70`이 아니면 package 자체가 그 threshold를 보장하지 못한다.

[Detailed Explanation/Example] → runtime smoke에서 `OPAL_THRESHOLD="$BEST_THRESHOLD"`를 넣어 검증할 수는 있지만, 제출 evaluator가 같은 env를 보장하지 않으면 실제 제출 threshold는 기본값 `0.70`이 된다. 따라서 `BEST_THRESHOLD != 0.70`이면 제출 전 package-level lock 구현이 필요하다.

## Leaderboard Gate

GO 조건:

- r32/r64 포함 전체 sweep 완료.
- `threshold_aware_candidate_final.json`의 `best`가 존재.
- fail precision/recall 제약 통과.
- threshold가 `0.70`이거나 package-level threshold lock 검증 완료.
- merged package size `<12GB`.
- `check_submit_package.py` PASS.
- `runtime_smoke_submit_package.py --offline --first-forward` PASS.
- server availability reject 해소 근거 존재.
- 제출 전 기존 시도 대비 무엇이 달라졌는지 archive에 기록.

NO-GO 조건:

- r32/r64 결과 누락.
- `BEST_THRESHOLD != 0.70`인데 package-level threshold lock 없음.
- static/runtime gate 실패.
- server issue reject 상태에서 동일 package 반복 제출.

## 중간 결정

- r32/r64 완료 전에는 package를 확정하지 않는다.
- 최종 best가 `0.70`이면 현재 solver 기본값으로 threshold lock이 충족된다.
- 최종 best가 `0.70`이 아니면 package threshold lock 구현이 선행되어야 한다.
- leaderboard 제출은 아직 NO-GO다.
