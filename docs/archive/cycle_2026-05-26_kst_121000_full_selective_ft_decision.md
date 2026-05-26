# Cycle 기록 - full/selective fine-tuning 방법 결정

- 시각: 2026-05-26 12:10 KST
- 브랜치: `cycle3/training-methods-20260526-kst`
- 목적: 12GB 제출 제한을 고려해 LoRA-only 외 대안을 검증한다.

## 결론

- 새 비교 학습은 `max_seq_len=4096`으로 고정한다.
- 현재 실행 중일 가능성이 있는 4B LoRA r64 `2048` run은 baseline 평가용으로만 유지한다.
- 다음 GPU 실험 우선순위는 `4B last-n-layers selective FT` → `0.8B/0.9B급 full FT` → `4B LoRA 4096 재학습`이다.
- DoRA/QLoRA는 논리적으로 후보지만 현재 repo에 실행 경로가 없으므로 코드 구현 전에는 no-go다.
- 서버 SSH가 회복되어 기존 baseline PID/checkpoint/final 상태가 확인되기 전에는 새 GPU 학습을 시작하지 않는다.

## 내부 증거

[Original Text/Data] v3 manifest full/selective dry-run에서 `max_seq_len=2048`은 tokenized `470`, skipped `321`, ratio `0.594`였다. `max_seq_len=4096`은 tokenized `791`, skipped `0`, ratio `1.0`이었다.
→ [Exact Interpretation] 2048 기반 신규 비교 학습은 long trajectory input을 상당수 버리므로 no-go다.
→ [Detailed Explanation/Example] 현재 LoRA r64 2048 run은 이미 시작된 baseline으로 평가까지만 유지하고, 다음 방법 비교는 4096으로 통일한다.

[Original Text/Data] 4B all-linear LoRA r64는 `bs4/ga2`에서 OOM, `bs2/ga4`에서 약 31.9GB VRAM 사용과 1epoch checkpoint가 확인됐다.
→ [Exact Interpretation] 48GB GPU에서 4B 계열은 batch/sequence 선택이 핵심 제약이다.
→ [Detailed Explanation/Example] 4B full FT보다 last-n-layers selective FT가 먼저다. short-run에서 OOM이 나면 last-n-layers 수를 줄인다.

[Original Text/Data] 이전 4B merged 제출 package는 directory `7.9G`, archive `6363.38 MB`로 12GB 제한 아래였다.
→ [Exact Interpretation] 4B artifact size 자체는 제출 제한 안에 들어갈 수 있다.
→ [Detailed Explanation/Example] 병목은 size보다 VRAM, calibration/hidden metric, offline smoke, 서버 availability다.

## 외부 근거

[EXTERNAL KNOWLEDGE] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). LoRA: Low-Rank Adaptation of Large Language Models. International Conference on Learning Representations. https://openreview.net/forum?id=nZeVKeeFYf9
→ [Exact Interpretation] LoRA adapter가 작은 것은 설계상 정상이다.
→ [Detailed Explanation/Example] 제출 용량을 적게 쓰는 사실만으로 LoRA를 버릴 수는 없고, 같은 data/metric에서 capacity 부족이 확인되어야 한다.

[EXTERNAL KNOWLEDGE] Dettmers, T., Pagnoni, A., Holtzman, A., & Zettlemoyer, L. (2023). QLoRA: Efficient Finetuning of Quantized LLMs. Advances in Neural Information Processing Systems. https://proceedings.neurips.cc/paper_files/paper/2023/hash/1feb87871436031bdc0f2beaa62a049b-Abstract.html
→ [Exact Interpretation] 4-bit quantized fine-tuning은 큰 모델 memory를 줄이는 후보가 된다.
→ [Detailed Explanation/Example] 현재 repo trainer에는 QLoRA 경로가 없으므로, 지금 당장 실행할 실험은 아니다.

[EXTERNAL KNOWLEDGE] Liu, S.-Y., Wang, C.-Y., Yin, H., Molchanov, P., Wang, Y.-C. F., Cheng, K.-T., & Chen, M.-H. (2024). DoRA: Weight-Decomposed Low-Rank Adaptation. arXiv. https://arxiv.org/abs/2402.09353
→ [Exact Interpretation] DoRA는 LoRA와 full FT 사이 capacity 후보가 된다.
→ [Detailed Explanation/Example] 현재 repo에는 DoRA CLI가 없으므로 구현 cycle을 따로 잡아야 한다.

[EXTERNAL KNOWLEDGE] Biderman, D., Portes, J., Gonzalez Ortiz, J. J., Paul, M., Greengard, P., Jennings, C., King, D., Havens, S., Chiley, V., Frankle, J., Blakeney, C., & Cunningham, J. P. (2024). LoRA Learns Less and Forgets Less. Transactions on Machine Learning Research. https://arxiv.org/abs/2405.09673
→ [Exact Interpretation] LoRA가 full FT보다 덜 배우는 상황이 있을 수 있다.
→ [Detailed Explanation/Example] full/selective FT 검증은 타당하지만, small-data overfit과 calibration 악화를 같이 gate해야 한다.

## 우선순위

1. P0: 기존 4B all-linear LoRA r64 상태 확인 및 calibration/hidden 평가
2. P1: 4B `last-n-layers=4`, `max_seq_len=4096`, short-run
3. P2: 0.8B/0.9B급 full FT, `max_seq_len=4096`
4. P3: 4B LoRA 4096 재학습
5. P4: DoRA/QLoRA 구현 검토

## 서버 회복 후 첫 확인

```bash
ssh -o BatchMode=yes -o ControlMaster=no -o ControlPath=none -o ConnectTimeout=20 -o ConnectionAttempts=1 -o ServerAliveInterval=5 -o ServerAliveCountMax=3 team6 '
cd /workspace/sinjeongmin_opal_verifier/repo &&
git status --short &&
ps -p 101814 -o pid,etime,cmd || true &&
find /workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1051_KST_train_v3_alllinear_lora_r64_bs2 -maxdepth 5 \( -name "adapter_model.safetensors" -o -name "checkpoint-*" \) -print | tail -50 &&
nvidia-smi
'
```

## 4B selective FT short-run 초안

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python3 tools/training/train_manifest_full.py \
  --manifest /workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1045_KST_manifest_v3_long_shape_enriched/manifests/manifest_v3_long_shape_enriched.jsonl \
  --run-root /workspace/sinjeongmin_opal_verifier/ops/runs/20260526_selective_ft_4b_4096_last4 \
  --model-name qwen35_4b_last4_4096_ep1 \
  --base-model Qwen/Qwen3.5-4B \
  --train-mode last-n-layers \
  --last-n-layers 4 \
  --max-seq-len 4096 \
  --batch-size 1 \
  --grad-accum 8 \
  --epochs 1 \
  --lr 2e-5 \
  --weight-decay 0.01 \
  --label-smoothing 0.05 \
  --warmup-ratio 0.03 \
  --torch-dtype float16 \
  --min-tokenized-ratio 0.95 \
  --save-strategy steps \
  --save-steps 50 \
  --save-total-limit 3
```

## 0.8B/0.9B급 full FT 초안

```bash
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True python3 tools/training/train_manifest_full.py \
  --manifest /workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1045_KST_manifest_v3_long_shape_enriched/manifests/manifest_v3_long_shape_enriched.jsonl \
  --run-root /workspace/sinjeongmin_opal_verifier/ops/runs/20260526_full_ft_0p8b_4096_ep1 \
  --model-name qwen35_0p8b_full_4096_ep1 \
  --base-model Qwen/Qwen3.5-0.8B \
  --train-mode full \
  --max-seq-len 4096 \
  --batch-size 1 \
  --grad-accum 8 \
  --epochs 1 \
  --lr 1e-5 \
  --weight-decay 0.01 \
  --label-smoothing 0.05 \
  --torch-dtype float16 \
  --min-tokenized-ratio 0.95 \
  --save-strategy steps \
  --save-steps 50 \
  --save-total-limit 3
```

## Go/No-Go Gate

- GO:
  - 서버 SSH 회복 및 기존 baseline 상태 확인 완료
  - `max_seq_len=4096` tokenized ratio `>=0.95`
  - OOM 없음, checkpoint 생성, resume 가능
  - calibration-first threshold 선택 후 hidden no-peek 평가
  - calibration fail precision `>=0.90`, fail recall `>=0.80`
  - hidden accuracy baseline 대비 `+3pp` 또는 macro-F1 `+0.03`
  - ECE `<=0.08` 또는 기존 후보 대비 명확한 개선
  - final artifact 또는 merged package `<12GB`
  - offline load 및 first-forward smoke 통과
- NO-GO:
  - 서버 SSH timeout 지속 또는 baseline run 상태 미확정
  - 2048 기반 신규 비교 학습
  - 4B selective/full OOM 또는 checkpoint/resume 실패
  - package `<12GB` 또는 offline smoke 실패
  - calibration만 개선되고 hidden 성능/ECE가 악화
  - DoRA/QLoRA 실행 지원 없이 바로 실험 시도
