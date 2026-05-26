<!-- Changed: document the official TRL-based public20 SFT adapter. -->
<!-- Why: public20 SFT results from this path must be distinguished from prior custom-wrapper results. -->
# public20 TRL SFT Adapter 기록

- 작성일: 2026-05-26 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 학습 core: Hugging Face TRL `SFTTrainer`
- 데이터 형식: standard prompt-completion JSONL
- public20 사용 범위: `train`/`validation`만 사용. public20 `test` split은 만들지 않는다.

## 구현 구분

이 adapter는 `tools/training/prepare_public20_sft_dataset.py`가 public20 split JSONL을
`prompt`/`completion` JSONL로 변환하고, `tools/training/run_trl_sft_public20.py`가
공식 TRL `SFTTrainer`를 호출하는 thin wrapper다.

기존 `tools/training/train_manifest_full.py` 결과와 다르다. 기존 결과는 custom
Transformers `Trainer` wrapper 기반 preliminary 결과로 기록하고, 이 adapter 결과는
공식 TRL SFTTrainer 기반 public20 SFT 결과로 별도 기록한다.

## Loss 근거

`prompt`에는 full trajectory input을 넣고, `completion`에는 정답 문자열 `pass` 또는
`fail`만 넣는다. TRL 문서의 prompt-completion SFT 경로는
`SFTConfig(completion_only_loss=True)`에서 prompt token을 loss에서 제외하고 completion
token에 대해서만 loss를 계산하는 경로다. 이 repository의 launcher는 custom collator나
custom training loop를 넘기지 않고 `SFTTrainer` 내부 처리에 맡긴다.

## Eval 구분

`SFTTrainer.evaluate()`의 `eval_loss`는 official trainer metric으로 둔다. pass/fail
generation accuracy, macro-F1, recall 등 task metric은
`tools/eval/eval_trl_sft_public20_generation.py`에서 별도 adapter로 계산한다. 이 metric
adapter는 rule engine이나 runtime verifier를 호출하지 않는다.

## Official TRL Full FT 3-seed 결과

<!-- Changed: add the completed full fine-tuning seed11/29/47 results. -->
<!-- Why: the research note should distinguish official TRL full FT evidence from LoRA adapter evidence and custom-wrapper results. -->

아래 결과는 official TRL lane에서 PEFT/LoRA를 끈 full fine-tuning 결과다. 모든 full FT seed의 trainable check는
trainable `852,985,920`, total `852,985,920`, frozen `0`, PEFT/LoRA disabled다.

| seed | acc | macro-F1 | fail recall | pass recall | TP | TN | FP | FN | INVALID |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 11 | `0.5` | `0.6667` | `1.0` | `0.0` | `2` | `0` | `2` | `0` | `0` |
| 29 | `1.0` | `1.0` | `1.0` | `1.0` | `2` | `2` | `0` | `0` | `0` |
| 47 | `0.75` | `0.7333` | `0.5` | `1.0` | `1` | `2` | `0` | `1` | `0` |

해석: seed29 `1.0`은 의미 있는 긍정 신호지만 public20 `val`이 split별 4개라 variance가 높다.
따라서 leaderboard 제출 판단은 no-go로 유지한다. LoRA seed 결과는 lower/unstable 보조 evidence로만 둔다.

다음 결정 기준:

1. official TRL full FT logprob evaluator 결과를 generation metric과 대조한다.
2. retrieved-context seed11 결과를 plain seed11 full FT와 비교한다.
3. 필요 시 seed29 full FT artifact inspect/calibration과 threshold 결정을 수행한다.
4. package `<12GB`, `tools/eval/check_submit_package.py`, `tools/eval/runtime_smoke_submit_package.py --offline --first-forward` gate를 확인한다.

## 서버 실행 command 초안

```bash
python3 tools/training/prepare_public20_sft_dataset.py \
  --split-dir runs/model_validation/public20_splits/split_seed_11 \
  --output-dir runs/model_validation/public20_trl_sft/seed11_dataset \
  --overwrite
```

```bash
python3 tools/training/run_trl_sft_public20.py \
  --dataset-dir runs/model_validation/public20_trl_sft/seed11_dataset \
  --model-name-or-path Qwen/Qwen2.5-0.5B-Instruct \
  --output-dir runs/model_validation/public20_trl_sft/seed11_adapter \
  --use-peft \
  --lora-r 16 \
  --lora-alpha 32 \
  --lora-dropout 0.05 \
  --num-train-epochs 5 \
  --learning-rate 1e-4 \
  --per-device-train-batch-size 1 \
  --gradient-accumulation-steps 8 \
  --eval-strategy epoch \
  --bf16 \
  --check-dependencies
```

```bash
python3 tools/eval/eval_trl_sft_public20_generation.py \
  --dataset-jsonl runs/model_validation/public20_trl_sft/seed11_dataset/validation.jsonl \
  --model-name-or-path runs/model_validation/public20_trl_sft/seed11_adapter \
  --output-json runs/model_validation/public20_trl_sft/seed11_generation_metrics.json \
  --output-md runs/model_validation/public20_trl_sft/seed11_generation_metrics.md
```
