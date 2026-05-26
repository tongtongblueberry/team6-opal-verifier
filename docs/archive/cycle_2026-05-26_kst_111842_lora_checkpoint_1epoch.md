# Cycle 기록 - v3 r64 all-linear LoRA 1epoch checkpoint

- 시각: 2026-05-26 11:18:42 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 기준 커밋: `981a2d8`
- 서버 런타임 루트: `/workspace/sinjeongmin_opal_verifier`

## 결론

- `bs2/ga4` 재시작 run은 OOM 없이 1epoch checkpoint를 생성했다.
- 현재 checkpoint는 resume 가능한 상태이므로, 중간 중단 리스크는 낮아졌다.
- leaderboard 제출은 하지 않는다. 아직 final adapter 학습 완료와 calibration/hidden 평가, package `<12GB` smoke가 없다.

## 학습 run

- run root: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2`
- adapter: `qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4`
- manifest: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1045_KST_manifest_v3_long_shape_enriched/manifests/manifest_v3_long_shape_enriched.jsonl`
- base model: `Qwen/Qwen3.5-4B`
- hyperparameter:
  - epochs: `10`
  - batch-size: `2`
  - grad-accum: `4`
  - effective batch: `8`
  - lr: `2e-4`
  - label smoothing: `0.05`
  - max seq len: `2048`
  - LoRA: `r64`, `alpha128`, `dropout0.05`
  - target modules: `q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`

## checkpoint

- checkpoint path: `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2/adapters/qwen35_4b_v3_alllinear_r64_lr2e4_e10_bs2ga4/checkpoints/checkpoint-59`
- size: `973M`
- trainer state:
  - global_step: `59`
  - epoch: `1.0`
  - best_metric: `None`
  - total_flos: `2.110886428803072e+16`
- checkpoint files:
  - `adapter_model.safetensors`: `339772792` bytes
  - `optimizer.pt`: `679693515` bytes
  - `trainer_state.json`: present
  - `scheduler.pt`, `scaler.pt`, `rng_state.pth`, `training_args.bin`: present

## loss/lr 관찰

- step `45`: loss `3.8885986328125`, lr `0.00019998583795552083`, grad_norm `3.42736554145813`
- step `50`: loss `4.344449234008789`, lr `0.00019989930665413147`, grad_norm `6.871744155883789`
- step `55`: loss `3.873085784912109`, lr `0.00019973417984956403`, grad_norm `4.483099460601807`

## 실행 상태

- 2026-05-26 11:18:24 KST 기준:
  - 진행률: `82/590`
  - GPU: L40S `31945/46068MiB` 사용
  - GPU util: `100%`
  - OOM: 없음

## 해석

- 첫 `bs4/ga2` run은 label smoothing log-softmax에서 OOM이 났지만, `bs2/ga4`는 effective batch를 유지하면서 micro-batch 메모리만 줄여 안정화했다.
- checkpoint가 생성됐으므로 이후 장애가 생기면 동일 command에 `--resume`을 붙여 재시작한다.
- 다만 이 baseline은 `max_seq_len=2048`이라 v3 train row의 긴 trajectory 일부가 label truncation으로 손실될 수 있다. 따라서 다음 비교 학습은 `max_seq_len=4096` gate를 우선한다.

## 다음 단계

- 현재 LoRA baseline은 final adapter까지 계속 학습한다.
- 학습 완료 후 calibration/hidden 평가와 threshold sweep을 실행한다.
- 평가 후 merged standalone package size와 offline smoke를 검증한다.
