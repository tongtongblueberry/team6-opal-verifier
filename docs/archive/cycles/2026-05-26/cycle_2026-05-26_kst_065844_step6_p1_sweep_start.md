# 2026-05-26 KST 06:58:44 - Step6 P1 calibration-first LoRA sweep 시작

## 구조 Skeleton
- 목적
- 실행 정보
- config
- GPU/OOM monitor
- 학습 monitor 상태
- 다음 확인

## 목적
- P0 calibration-first 재판정에서 기존 sweep 후보가 fail precision/recall constraint를 만족하지 못했다.
- Step4 결정에 따라 P1 보수적 LoRA sweep을 시작했다.
- 목표는 rank 확대가 아니라 calibration-first gate를 통과하는 low/mid-rank regularized 후보를 찾는 것이다.

## 실행 정보
- 서버 repo: `/workspace/team6/team6-opal-verifier`
- manifest: `/workspace/team6/ops/runs/20260522_164328_KST/manifests/canonical_supervised_manifest.jsonl`
- run root: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep`
- PID: `84697`
- 실제 GPU child PID: `84699`
- stdout/stderr: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep/logs/p1_sweep_stdout.log`
- config JSON: `/workspace/team6/ops/runs/20260526_0655_KST_p1_calibration_lora_sweep/artifacts/p1_calibration_sweep_config.json`
- 실행 command 요지:
  - `python3 tools/training/run_manifest_lora_sweep.py`
  - `--config-json .../p1_calibration_sweep_config.json`
  - `--resume`

## config
- `p1_r4_lr5e4_do20_ep5`
  - lr `0.0005`, dropout `0.20`, r `4`, alpha `8`, epochs `5.0`, batch_size `2`, grad_accum `4`
- `p1_r8_lr5e4_do20_ep5`
  - lr `0.0005`, dropout `0.20`, r `8`, alpha `16`, epochs `5.0`, batch_size `2`, grad_accum `4`
- `p1_r16_lr2e4_do20_ep5`
  - lr `0.0002`, dropout `0.20`, r `16`, alpha `32`, epochs `5.0`, batch_size `2`, grad_accum `4`
- `p1_r16_lr5e4_do20_wd10_ep5`
  - lr `0.0005`, dropout `0.20`, weight_decay `0.10`, r `16`, alpha `32`, epochs `5.0`, batch_size `2`, grad_accum `4`
- `p1_r8_lr2e4_do10_ls15_ep5`
  - lr `0.0002`, dropout `0.10`, label_smoothing `0.15`, r `8`, alpha `16`, epochs `5.0`, batch_size `2`, grad_accum `4`

## GPU/OOM monitor
[Original Text/Data] GPU는 NVIDIA L40S, total `46068 MiB`, used 약 `30375~30381 MiB`, free 약 `15078 MiB`, util `57~100%`로 관측됐다.

[Exact Interpretation] 현재 초기 학습 기준 `batch_size=2`, `grad_accum=4`는 48GB급 GPU에 적절하다.

[Detailed Explanation/Example] r4 첫 config가 학습 중이며 OOM 관련 로그는 발견되지 않았다. 기존 r64 sweep도 같은 batch 설정으로 완료됐으므로 r4/r8/r16 P1 sweep은 초기 자원 관점에서 안전한 편이다.

## 학습 monitor 상태
- 첫 config `p1_r4_lr5e4_do20_ep5`가 학습 중이다.
- train log가 생성됐다.
- launcher stdout log는 아직 비어 있다.
- 학습 구조 monitor agent가 별도 확인 중이다.

## 다음 확인
- train log에서 epoch/loss 진행을 확인한다.
- 첫 config completion 후 eval JSON에 calibration-first metric과 risk coverage summary가 포함되는지 확인한다.
- OOM 또는 eval failure가 있으면 batch size를 낮추고 `--resume`으로 재개한다.
- 완료 후보는 calibration precision `>=0.90`, recall `>=0.80`, hidden no-peek 검증을 모두 통과해야 한다.
