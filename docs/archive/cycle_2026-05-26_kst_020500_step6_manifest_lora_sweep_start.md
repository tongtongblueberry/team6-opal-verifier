# 2026-05-26 KST 02:05 - Cycle 3 Step 6 manifest-only LoRA sweep 실행 시작

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- 구현 commit:
  - `f6dafa7 add manifest lora sweep knobs and metrics`
  - `763a259 add manifest lora sweep runner`
  - `6e5c8b7 harden manifest sweep resume checks`
- 서버 run root: `/workspace/team6/ops/runs/20260526_0200_KST_manifest_lora_sweep`
- manifest: `/workspace/team6/ops/runs/20260522_164328_KST/manifests/canonical_supervised_manifest.jsonl`
- 실행 PID: `78836`
- 실행 방식: `nohup`, `--resume`, `--limit-configs 5`

## 실행 근거

[Original Text/Data] → Step 4 최종 방법 결정은 `train_manifest_lora.py` LoRA CLI 확장, manifest-only sweep runner, `eval_manifest_adapter.py` metric 확장, r16 baseline 재학습, r32/r64 high-rank LoRA 실행을 Step 5/6 우선 작업으로 결정했다.

[Exact Interpretation] → 기존 rule 의존 sweep은 사용하지 않고, DCv2 manifest만 사용하는 학습/평가 경로로 충분 학습 비교를 시작해야 한다.

[Detailed Explanation/Example] → 이번 sweep은 `r16_lr1e3_do10_ep5`, `r16_lr5e4_do10_ep5`, `r16_lr1e3_do05_ep5`, `r32_lr1e3_do10_ep5`, `r64_lr1e3_do05_ep5`를 같은 manifest와 같은 evaluator로 비교한다.

## 실행 계획

- train/eval path:
  - training: `/workspace/team6/team6-opal-verifier/tools/training/train_manifest_lora.py`
  - eval: `/workspace/team6/team6-opal-verifier/tools/eval/eval_manifest_adapter.py`
  - runner: `/workspace/team6/team6-opal-verifier/tools/training/run_manifest_lora_sweep.py`
- threshold sweep:
  - `0.30,0.35,0.40,0.45,0.50,0.55,0.60,0.65,0.70`
- best selection:
  - primary: `metrics.by_split.hidden.accuracy`
  - constraints: hidden fail precision `>=0.90`, hidden fail recall `>=0.80`
- 재시작성:
  - trainer `--resume`
  - runner는 `eval_json`만으로 skip하지 않고, train report hyperparameter와 eval arguments가 현재 config와 일치할 때만 skip한다.

## 초기 모니터링

[Original Text/Data] → KST `2026-05-26 02:05:25`, GPU memory `30393 MiB used / 15066 MiB free`, utilization `100%`.

[Exact Interpretation] → r16 baseline은 OOM 없이 학습에 진입했고, L40S 48GB 중 약 30GB를 사용한다.

[Detailed Explanation/Example] → `batch=2`, `grad_accum=4`, `max_seq_len=2048`, `LoRA r=16` 기준으로 약 15GB 여유가 있어 r32/r64 진행 가능성이 있다.

[Original Text/Data] → KST `2026-05-26 02:11:29`, `r16_lr1e3_do10_ep5.train.log` raw tail 기준 `29/215` step 진행, 약 `12.9초/step`.

[Exact Interpretation] → 학습 loop가 정상 진행 중이다.

[Detailed Explanation/Example] → 현재 로그에서 `CUDA`, `OOM`, `NaN`, `RuntimeError`, `Traceback` alert는 확인되지 않았다. loss/grad_norm 출력은 아직 파일에서 탐지되지 않아 이후 trainer log와 final train report로 확인한다.

## 현재 결정

- leaderboard 제출: NO-GO. 현재 서버 availability reject 상태이며 이번 단계는 학습 실험이다.
- full fine-tuning: 보류가 아니라 pilot-gated. high-rank LoRA/metric sweep 결과로 capacity 병목이 확인되면 memory dry-run과 1 epoch full/partial FT pilot로 넘어간다.
- 다음 확인:
  - r16 첫 config 완료 여부
  - train report 생성 여부
  - eval report의 hidden accuracy/precision/recall/ECE
  - r32/r64 시작 시 GPU memory peak와 OOM 여부
