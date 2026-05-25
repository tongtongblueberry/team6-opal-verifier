# 2026-05-26 KST 04:50 - Full Fine-Tuning feasibility agent 기록

## 구조 Skeleton

- branch: `cycle3/training-methods-20260526-kst`
- agent 역할: full fine-tuning feasibility 검토
- 기준 코드:
  - `tools/training/train_manifest_lora.py`
  - `tools/training/run_manifest_lora_sweep.py`
  - `tools/eval/eval_manifest_adapter.py`
- 기준 조건:
  - GPU: L40S 48GB
  - base model: `Qwen/Qwen3.5-4B`
  - train examples: `337`
  - max sequence length: `2048`
  - 현재 실행 중인 방법: r16/r32/r64 LoRA sweep

## 결론

[Original Text/Data] → r16 LoRA 기록은 `trainable_params=3145728`, `trainable_ratio=0.0007473996`을 기록했다.

[Exact Interpretation] → 전체 parameter 수는 대략 `4.209B`이며, full fine-tuning은 LoRA 대비 trainable parameter가 약 `1338x` 늘어난다.

[Detailed Explanation/Example] → adapter-only LoRA가 약 3M trainable parameter인 반면, full FT는 base model 대부분 또는 전체 weight에 gradient와 optimizer state를 붙인다. 따라서 “12GB 제출 용량을 쓰기 위해 full FT를 한다”는 판단은 package size만 보고 내릴 수 없고, 학습 중 memory gate를 먼저 통과해야 한다.

## Memory 판단

[EXTERNAL KNOWLEDGE] PyTorch Contributors. (2026). *Adam*. PyTorch documentation. https://docs.pytorch.org/docs/2.12/generated/torch.optim.Adam.html

[Original Text/Data] → PyTorch Adam은 first moment와 second moment optimizer state를 유지한다.

[Exact Interpretation] → 4.209B parameter full FT에서 fp16 weight와 gradient, Adam fp32 moment state를 합치면 activation을 제외해도 48GB 한계에 매우 가깝다.

[Detailed Explanation/Example] → fp16 weight 약 `7.84GiB`, fp16 gradient 약 `7.84GiB`, Adam fp32 moment 2개 약 `31.36GiB`로 합계가 약 `47.0GiB`다. fp32 master weight, activation, CUDA reserve, foreach intermediate가 추가되면 48GB L40S에서 naive AdamW는 OOM 위험이 높다.

[EXTERNAL KNOWLEDGE] PyTorch Contributors. (2026). *CUDA semantics: Memory management*. PyTorch documentation. https://docs.pytorch.org/docs/2.12/notes/cuda.html

[Original Text/Data] → PyTorch CUDA memory는 allocated와 reserved가 다르게 관측될 수 있다.

[Exact Interpretation] → full FT pilot은 `nvidia-smi`만으로 판단하면 안 되고 `torch.cuda.max_memory_allocated()`와 `torch.cuda.max_memory_reserved()`를 step 후 기록해야 한다.

[Detailed Explanation/Example] → 현재 LoRA sweep r16/r32도 약 30.4GB를 사용한다. full FT에서는 optimizer state가 추가되므로, memory dry-run 없이 본학습을 시작하면 중간 checkpoint 전 OOM으로 시간을 잃을 수 있다.

## 결정

[Original Text/Data] → Step 4 method decision은 full FT를 적극 고려하되, memory dry-run, checkpoint/resume, package `<12GB`, 1 epoch 개선 신호를 gate로 두라고 기록했다.

[Exact Interpretation] → full FT는 금지하지 않는다. 다만 현재 r16/r32/r64 충분 학습 비교가 끝나기 전에는 본학습 대상으로 올리지 않는다.

[Detailed Explanation/Example] → 먼저 high-rank LoRA 결과로 현재 data/threshold 병목을 확인한다. 그 뒤에도 capacity 병목이 남으면 full FT 또는 partial FT pilot을 gate 방식으로 실행한다.

## 다음 실행 Gate

1. r32/r64 sweep 완료 후 threshold-aware selector를 다시 실행한다.
2. full FT memory dry-run:
   - `batch_size=1`
   - `max_seq_len=2048`
   - `gradient_checkpointing=True`
   - `use_cache=False`
   - full `requires_grad=True`
   - AdamW `foreach=False`
   - `loss.backward()`와 `optimizer.step()`까지 실행
   - PASS 기준: OOM/NaN 없음, `max_memory_reserved <= 44GB`
3. checkpoint/resume smoke:
   - `max_steps=2`
   - `save_steps=1`
   - `save_total_limit=2`
   - `resume_from_checkpoint=checkpoint-1` 확인
4. 1 epoch pilot:
   - `lr=5e-6` 또는 `1e-5`
   - `batch_size=1`
   - `grad_accum=8`
   - train loss 폭주 없음
5. metric/package gate:
   - hidden-like 비열화 없음, 가능하면 r16/r32/r64 best 대비 `+3pp`
   - fail precision `>=0.90`
   - fail recall `>=0.80`
   - ECE `<=0.12`
   - package `<12GB`
   - offline first-forward PASS

## 중간 결정

- 현 시점에는 naive AdamW full FT 본학습을 시작하지 않는다.
- r32/r64 결과가 high-rank LoRA에서 충분히 개선되면 best adapter merge/package가 우선이다.
- high-rank LoRA가 병목을 해결하지 못하면 full FT는 memory dry-run부터 실행한다.
- direct full-model eval wrapper가 아직 없으므로, full FT pilot을 하려면 eval wrapper 또는 merged-model eval 경로를 먼저 구현해야 한다.
