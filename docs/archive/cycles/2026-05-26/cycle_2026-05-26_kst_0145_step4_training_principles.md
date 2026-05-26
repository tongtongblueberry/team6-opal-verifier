<!-- 변경: Cycle 2 Step 4의 AI 학습 기본 원리/Sweep/normalization/data 분포 개선 조사 문서를 신규 작성. 이유: 다음 방법 결정에서 LLM-only 학습 sweep과 GPU/OOM 운영 기준을 근거 기반으로 확정하기 위함. -->
# Cycle 2 Step 4 - AI 학습 기본 원리 및 Sweep/Data 분포 개선 제안

작성 시각: 2026-05-26 01:45 KST  
작성 범위: Sweep, learning rate, batch/gradient accumulation, normalization/regularization, class imbalance, data distribution shift, calibration, checkpoint/resume, OOM monitoring  
원칙: architecture에는 rule engine을 포함하지 않는다. 모든 제안은 LLM-only trainer/eval/package gate 기준이다.

## 구조 Skeleton

1. 입력 근거와 금지 사항
2. 외부 자료 조사
3. 로컬 repo/server 기록 해석
4. Sweep 우선순위 결정
5. 48GB GPU batch/seq/rank 조정 기준
6. monitoring/checkpoint/resume 기준
7. 최종 제안

## 입력 근거와 금지 사항

- 현재 신뢰 가능한 주 학습 경로는 `tools/training/train_manifest_lora.py`이다.
- 기존 `tools/training/sweep_lora.py`는 `src.solver.StatefulOpalVerifier`를 import하므로 현재 LLM-only branch에서 그대로 사용하지 않는다.
- 평가는 `tools/eval/eval_manifest_adapter.py` 계열의 manifest-only calibration/hidden split 기준으로 수행한다.
- package 후보는 `check_submit_package.py`, offline `runtime_smoke_submit_package.py --first-forward`, package size `<12GB`, no-rule executable scan을 통과해야 한다.
- leaderboard는 server availability reject가 해소됐다는 증거가 없으면 NO-GO다.

## 외부 자료 조사

1. [EXTERNAL KNOWLEDGE] Bergstra, J., & Bengio, Y. (2012). Random search for hyper-parameter optimization. *Journal of Machine Learning Research, 13*, 281-305. https://jmlr.org/beta/papers/v13/bergstra12a.html  
   - 핵심: grid search보다 random search가 중요한 hyperparameter 축을 더 효율적으로 탐색할 수 있다.
   - 적용: 지금은 full factorial sweep이 아니라 `lr`, `rank`, `dropout`, `effective batch`, `max_seq_len`의 제한된 random/sequential sweep이 맞다.

2. [EXTERNAL KNOWLEDGE] Li, L., Jamieson, K., DeSalvo, G., Rostamizadeh, A., & Talwalkar, A. (2018). Hyperband: A novel bandit-based approach to hyperparameter optimization. *Journal of Machine Learning Research, 18*(185), 1-52. https://www.jmlr.org/beta/papers/v18/16-558.html  
   - 핵심: early-stopping과 resource allocation으로 많은 후보를 짧게 보고, 유망 후보에 더 많은 epoch를 배정한다.
   - 적용: 각 후보를 최소 1-2 epoch pilot으로 OOM/loss/metric을 확인하고, 유망 후보만 5 epoch 이상 충분 학습한다.

3. [EXTERNAL KNOWLEDGE] Goyal, P., Dollar, P., Girshick, R., Noordhuis, P., Wesolowski, L., Kyrola, A., Tulloch, A., Jia, Y., & He, K. (2017). Accurate, large minibatch SGD: Training ImageNet in 1 hour. arXiv. https://arxiv.org/abs/1706.02677  
   - 핵심: batch size를 키울 때 learning rate scaling과 warmup이 중요하다.
   - 적용: `batch_size`를 올릴 때 `lr`을 고정하지 말고 warmup과 threshold/calibration drift를 함께 본다.

4. [EXTERNAL KNOWLEDGE] Smith, S. L., Kindermans, P.-J., Ying, C., & Le, Q. V. (2018). Don't decay the learning rate, increase the batch size. International Conference on Learning Representations. https://openreview.net/forum?id=B1Yy1BxCZ  
   - 핵심: learning rate schedule과 batch size schedule은 gradient noise 관점에서 연결된다.
   - 적용: small data에서 무작정 effective batch를 키우면 gradient noise가 줄어 일반화가 나빠질 수 있으므로, GPU 활용률만 보고 batch를 키우지 않는다.

5. [EXTERNAL KNOWLEDGE] Keskar, N. S., Mudigere, D., Nocedal, J., Smelyanskiy, M., & Tang, P. T. P. (2017). On large-batch training for deep learning: Generalization gap and sharp minima. International Conference on Learning Representations. https://arxiv.org/abs/1609.04836  
   - 핵심: large-batch training은 sharp minima와 generalization gap을 유발할 수 있다.
   - 적용: 480개 selected manifest 수준에서는 `batch_size`를 48GB 한도까지 무작정 키우기보다 `bs=1-4`, `grad_accum=4-16` 범위에서 metric 중심으로 고른다.

6. [EXTERNAL KNOWLEDGE] Hoffer, E., Hubara, I., & Soudry, D. (2017). Train longer, generalize better: Closing the generalization gap in large batch training of neural networks. Advances in Neural Information Processing Systems. https://arxiv.org/abs/1705.08741  
   - 핵심: batch 자체보다 update 수와 normalization 방식이 generalization gap에 중요할 수 있다.
   - 적용: 같은 epoch라도 effective batch가 커지면 optimizer update 수가 줄어든다. 후보 비교는 epoch뿐 아니라 update/token budget을 같이 기록한다.

7. [EXTERNAL KNOWLEDGE] Loshchilov, I., & Hutter, F. (2019). Decoupled weight decay regularization. International Conference on Learning Representations. https://arxiv.org/abs/1711.05101  
   - 핵심: Adam 계열에서는 weight decay를 gradient update와 decouple하는 AdamW가 일반화에 유리하다.
   - 적용: 현재 `adamw_torch`와 `weight_decay=0.05`는 유지하되, `weight_decay`는 `lr`과 독립 축으로 `0.01/0.03/0.05` 소규모만 확인한다.

8. [EXTERNAL KNOWLEDGE] Loshchilov, I., & Hutter, F. (2017). SGDR: Stochastic gradient descent with warm restarts. International Conference on Learning Representations. https://arxiv.org/abs/1608.03983  
   - 핵심: cosine/restart 계열 LR schedule은 anytime performance와 optimization 안정성을 개선할 수 있다.
   - 적용: 현재 cosine scheduler는 유지하되, small-data에서는 restart보다 checkpoint별 threshold/eval을 우선한다.

9. [EXTERNAL KNOWLEDGE] Srivastava, N., Hinton, G., Krizhevsky, A., Sutskever, I., & Salakhutdinov, R. (2014). Dropout: A simple way to prevent neural networks from overfitting. *Journal of Machine Learning Research, 15*, 1929-1958. https://www.jmlr.org/papers/v15/srivastava14a.html  
   - 핵심: dropout은 co-adaptation을 줄여 overfitting을 완화한다.
   - 적용: Cycle 8에서 dropout 0.0이 과적합을 가속했다는 로컬 기록이 있으므로 `dropout=0.05/0.10`을 우선 비교한다.

10. [EXTERNAL KNOWLEDGE] Cui, Y., Jia, M., Lin, T.-Y., Song, Y., & Belongie, S. (2019). Class-balanced loss based on effective number of samples. Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition. https://arxiv.org/abs/1901.05555  
    - 핵심: class imbalance는 단순 inverse frequency가 아니라 effective number 기반 reweighting으로 완화할 수 있다.
    - 적용: fail oversampling은 금지하고, 필요하면 class weight 또는 sample weight를 별도 실험으로 분리한다.

11. [EXTERNAL KNOWLEDGE] Lin, T.-Y., Goyal, P., Girshick, R., He, K., & Dollar, P. (2017). Focal loss for dense object detection. Proceedings of the IEEE International Conference on Computer Vision. https://openaccess.thecvf.com/content_iccv_2017/html/Lin_Focal_Loss_for_ICCV_2017_paper.html  
    - 핵심: easy example이 loss를 지배할 때 hard example에 더 많은 weight를 줄 수 있다.
    - 적용: pass/fail prior를 깨는 oversampling 대신 hard-case weighting 후보를 고려하되, calibration 악화가 있으면 채택하지 않는다.

12. [EXTERNAL KNOWLEDGE] Guo, C., Pleiss, G., Sun, Y., & Weinberger, K. Q. (2017). On calibration of modern neural networks. Proceedings of the 34th International Conference on Machine Learning, 1321-1330. https://proceedings.mlr.press/v70/guo17a.html  
    - 핵심: accuracy가 높아도 confidence calibration은 나쁠 수 있고 temperature scaling이 실용적이다.
    - 적용: threshold sweep만 기록하지 말고 ECE, Brier score, calibration-selected threshold의 hidden transfer를 본다.

13. [EXTERNAL KNOWLEDGE] Kumar, A., Liang, P., & Ma, T. (2019). Verified uncertainty calibration. Advances in Neural Information Processing Systems. https://papers.nips.cc/paper/8635-verified-uncertainty-calibration  
    - 핵심: calibration 평가는 finite sample 불확실성과 검증 가능성을 고려해야 한다.
    - 적용: calibration split에서 threshold를 고르고 hidden-like split은 no-peek 검증으로만 사용한다.

14. [EXTERNAL KNOWLEDGE] Sugiyama, M., Krauledat, M., & Muller, K.-R. (2007). Covariate shift adaptation by importance weighted cross validation. *Journal of Machine Learning Research, 8*, 985-1005. https://www.jmlr.org/beta/papers/v8/sugiyama07a.html  
    - 핵심: train/test input distribution이 다르면 일반 cross-validation이 편향될 수 있다.
    - 적용: length/source/template 분포 차이가 있으므로 random split 평균이 아니라 length/source group metric과 weighted validation을 본다.

15. [EXTERNAL KNOWLEDGE] Sagawa, S., Koh, P. W., Hashimoto, T. B., & Liang, P. (2020). Distributionally robust neural networks for group shifts: On the importance of regularization for worst-case generalization. International Conference on Learning Representations. https://arxiv.org/abs/1911.08731  
    - 핵심: group shift에서는 worst-group 성능과 regularization이 중요하다.
    - 적용: 평균 hidden-like accuracy가 좋아도 long/source worst bucket이 낮으면 채택하지 않는다.

16. [EXTERNAL KNOWLEDGE] Koh, P. W., Sagawa, S., Marklund, H., Xie, S. M., Zhang, M., Balsubramani, A., Hu, W., Yasunaga, M., Phillips, R. L., Gao, I., David, E., Stavness, I., Guo, W., Earnshaw, B., Haque, I., Beery, S. M., Leskovec, J., Kundaje, A., Pierson, E., ... Liang, P. (2021). WILDS: A benchmark of in-the-wild distribution shifts. Proceedings of the 38th International Conference on Machine Learning. https://proceedings.mlr.press/v139/koh21a.html  
    - 핵심: real-world shift에서는 domain/subpopulation별 성능을 별도로 관리해야 한다.
    - 적용: source/template family, length bucket, confidence bucket별 리포트를 sweep 결과에 포함한다.

17. [EXTERNAL KNOWLEDGE] Micikevicius, P., Narang, S., Alben, J., Diamos, G., Elsen, E., Garcia, D., Ginsburg, B., Houston, M., Kuchaiev, O., Venkatesh, G., & Wu, H. (2018). Mixed precision training. International Conference on Learning Representations. https://arxiv.org/abs/1710.03740  
    - 핵심: FP16 mixed precision은 memory/compute 효율을 높이지만 loss scaling과 안정성 관리가 필요하다.
    - 적용: 48GB GPU 활용은 fp16/bf16, gradient checkpointing, max memory logging으로 관리한다.

18. [EXTERNAL KNOWLEDGE] PyTorch Contributors. (2025). Understanding CUDA memory usage. *PyTorch Documentation*. https://docs.pytorch.org/docs/stable/torch_cuda_memory.html  
    - 핵심: PyTorch allocator와 non-PyTorch CUDA allocation을 분리해 memory snapshot/stat를 봐야 한다.
    - 적용: OOM 시 `nvidia-smi`만 보지 말고 `torch.cuda.max_memory_allocated/reserved`와 step별 peak를 기록한다.

19. [EXTERNAL KNOWLEDGE] Hugging Face. (2026). Trainer. *Transformers Documentation*. https://huggingface.co/docs/transformers/v5.0.0/trainer  
    - 핵심: `Trainer.train(resume_from_checkpoint=...)`는 checkpoint에서 학습을 재개하고 RNG state 복원을 시도한다.
    - 적용: 모든 sweep run은 `save_strategy=epoch`, checkpoint 보존, `--resume` 재개 검증을 필수로 둔다.

## 로컬 repo/server 기록 해석

1. [Original Text/Data] `cycle_2026-05-26_kst_0140_step3_goal_decision.md`는 1차 목표를 hidden-like `>=0.9146`, 20-case `>=16/20`, fail precision `>=90%`, fail recall `>=80%`, ECE `<=0.12`, package `<12GB`, offline first-forward PASS로 정했다.  
   -> [Exact Interpretation] 다음 sweep은 training loss 최적화가 아니라 이 gate를 통과하는 후보 선별이다.  
   -> [Detailed Explanation/Example] loss가 낮아도 fail precision/recall 또는 ECE가 나빠지면 후보가 아니다. checkpoint별 hidden-like/eval metric을 같이 기록해야 한다.

2. [Original Text/Data] `cycle_2026-05-26_kst_0130_step2_problem_decision.md`는 병목을 길이/trajectory 구조 분포 불일치, source/template 다양성 부족, label prior/calibration 불안정, 학습 capacity/infra 미성숙 순으로 판정했다.  
   -> [Exact Interpretation] sweep은 `lr/rank/batch`만 돌리는 것이 아니라 data distribution metric을 고정 관찰해야 한다.  
   -> [Detailed Explanation/Example] high-rank LoRA가 전체 accuracy를 올려도 long trajectory bucket이 낮거나 threshold drift가 커지면 병목을 해결한 것이 아니다.

3. [Original Text/Data] `cycle_2026-05-22_kst_data_contract_v2_pass.md`는 selected records `480`, length JSD `0.006999`, public/eval holdout metadata hits `0`, rule-context metadata/input hits `0`을 기록했다.  
   -> [Exact Interpretation] 현재 학습 데이터의 hard gate는 통과했지만, selected set 규모가 작아 overfit과 sampling variance 위험이 크다.  
   -> [Detailed Explanation/Example] 480개에서는 full factorial sweep보다 seed 고정, 작은 후보 수, calibration/hidden split no-peek, group metric이 중요하다.

4. [Original Text/Data] `cycle_8_step6_results.md`는 데이터 210건에서 694건으로 늘렸지만 fail 65%, dropout 0.0, threshold 0.40 이동, public 15/20 하락을 기록했다.  
   -> [Exact Interpretation] 데이터 양 증가 자체보다 label prior와 regularization이 더 중요했다.  
   -> [Detailed Explanation/Example] fail oversampling은 당장 금지한다. 불균형 대응은 class weight/focal loss/threshold calibration을 별도 ablation으로 분리한다.

5. [Original Text/Data] `cycle_8_step6_results.md`는 epoch 2 이후 train/eval loss는 계속 낮아졌지만 public accuracy가 하락했다고 기록했다.  
   -> [Exact Interpretation] eval loss 기준 best model selection은 이 task에서 불충분하다.  
   -> [Detailed Explanation/Example] `load_best_model_at_end`를 쓰더라도 metric은 manifest eval의 fail precision/recall/macro-F1/ECE 또는 calibration-selected threshold 기준이어야 한다.

6. [Original Text/Data] `train_manifest_lora.py`는 기본 `epochs=5`, `batch_size=1`, `grad_accum=8`, `lr=1e-3`, `weight_decay=0.05`, `label_smoothing=0.1`, `max_seq_len=2048`, `warmup_ratio=0.05`이고, LoRA는 코드상 `r=16`, `alpha=32`, `dropout=0.1`로 고정되어 있다.  
   -> [Exact Interpretation] 현재 주 trainer는 LoRA r16 기준선 재학습에는 충분하지만 high-rank/DoRA/QLoRA/partial FT sweep에는 인자화가 부족하다.  
   -> [Detailed Explanation/Example] Step 5 구현 전에는 `train_manifest_lora.py`를 확장해 `--lora-r`, `--lora-alpha`, `--lora-dropout`, `--target-modules`, `--dtype` 등을 CLI로 받아야 한다.

7. [Original Text/Data] `sweep_lora.py`는 `from src.solver import StatefulOpalVerifier`를 사용한다.  
   -> [Exact Interpretation] 이 script는 rule dependency 때문에 현재 branch에서 사용 금지다.  
   -> [Detailed Explanation/Example] 새 sweep runner는 manifest-only trainer/evaluator를 호출해야 하며, public dataset path와 solver/verifier import를 하지 않아야 한다.

8. [Original Text/Data] merged artifact 후보는 `7.9G`, static/runtime gate와 first-forward를 통과했지만 submit은 server issue reject로 job ID가 없었다.  
   -> [Exact Interpretation] 12GB 용량 활용을 위한 packaging infra는 일단 확보됐고, 다음 개선은 학습 방법/데이터 분포/metric 기반 sweep이다.  
   -> [Detailed Explanation/Example] 새 후보는 학습 후 adapter를 merge해 standalone `artifacts/merged_model`로 package gate를 다시 통과해야 한다.

## Sweep 우선순위 결정

### 0순위: sweep infra 보강

- 기존 `sweep_lora.py` 사용 금지.
- 새 runner는 아래 순서만 수행한다.
  - `train_manifest_lora.py` 또는 그 LLM-only 확장 trainer 실행
  - `eval_manifest_adapter.py`로 calibration split 평가
  - calibration split에서 threshold/temperature 선택
  - hidden-like split no-peek 평가
  - checkpoint별 metric, GPU peak, package/export 가능성 기록
- Step 5 구현 전 필수 확장:
  - LoRA rank/alpha/dropout CLI 인자화
  - checkpoint별 manifest eval hook 또는 후처리 script
  - train log에 `lr`, `loss`, `grad_norm`, `torch.cuda.max_memory_allocated`, `max_memory_reserved`, `effective_batch`, `tokens/sec` 기록
  - `--resume` 실제 재개 smoke

### 1순위: r16 LoRA 충분 학습 baseline 재현

- 목적: 현재 기준선을 잃지 않고 비교 기준을 고정한다.
- 후보:
  - A1: `r=16`, `alpha=32`, `dropout=0.1`, `lr=1e-3`, `bs=2`, `grad_accum=4`, `epochs=5`, `max_seq_len=2048`
  - A2: `r=16`, `alpha=32`, `dropout=0.1`, `lr=5e-4`, `bs=2`, `grad_accum=4`, `epochs=5`, `max_seq_len=2048`
  - A3: `r=16`, `alpha=32`, `dropout=0.05`, `lr=1e-3`, `bs=2`, `grad_accum=4`, `epochs=5`, `max_seq_len=2048`
- 선택 기준:
  - hidden-like `>=0.9146`
  - fail precision `>=90%`
  - fail recall `>=80%`
  - ECE `<=0.12`
  - checkpoint별 threshold drift `<=0.10`

### 2순위: high-rank LoRA capacity sweep

- 목적: adapter-only capacity 부족 가능성을 검증하되, full FT보다 먼저 OOM/overfit 위험이 낮은 확장부터 확인한다.
- 후보:
  - B1: `r=32`, `alpha=64`, `dropout=0.1`, `lr=5e-4`, `bs=1-2`, `grad_accum=4-8`, `epochs=5`
  - B2: `r=64`, `alpha=128`, `dropout=0.1`, `lr=2e-4`, `bs=1`, `grad_accum=8`, `epochs=5`
  - B3: best B 후보 10 epoch 확장, 단 metric이 epoch 2-5 이후 악화하면 중단
- 선택 기준:
  - r16 baseline 대비 hidden-like `+3pp` 또는 macro-F1 `+0.03`
  - long/source worst bucket 개선
  - package merge 후 `<12GB`, first-forward PASS

### 3순위: data distribution/calibration ablation

- 목적: Cycle 8 실패 원인인 label prior/calibration 흔들림을 분리한다.
- 후보:
  - C1: fail oversampling 없이 원본 prior 유지
  - C2: pass/fail prior `40:60`-`60:40` 범위로만 sampling
  - C3: class-balanced weight 또는 focal loss pilot, oversampling 금지
  - C4: threshold-only calibration과 temperature scaling 비교
- 선택 기준:
  - fail precision/recall 균형
  - ECE/Brier 개선
  - threshold drift 감소
  - hidden-like no-regress

### 4순위: DoRA/QLoRA/partial FT pilot

- 목적: full FT로 바로 넘어가기 전에 48GB에서 재시작 가능한 capacity 확장 후보를 검증한다.
- 후보:
  - DoRA: LoRA와 같은 rank grid에서 `use_dora=True`를 trainer에 추가한 뒤 r16/r32 pilot
  - QLoRA: 4-bit base + LoRA/DoRA로 VRAM 절감, 단 최종 package는 merge/export 가능성 확인
  - partial FT: 상위 transformer block 일부 또는 classification-relevant projection만 unfreeze
- 선택 기준:
  - OOM 없음
  - resume 가능
  - r16 baseline 대비 `+3pp`
  - merged/full artifact `<12GB`

### 5순위: full fine-tuning

- 목적: 사용자가 지적한 12GB 용량 미활용 문제를 근본적으로 검증한다.
- 현재 판정:
  - 즉시 전면 full FT는 위험하다. 4B FP16/BF16 optimizer state까지 고려하면 48GB에서 batch/seq 제한이 크고, small data overfit 위험도 높다.
  - partial FT 또는 memory-efficient optimizer/QLoRA pilot에서 이득이 확인된 뒤 full FT를 실행한다.
- 실행 조건:
  - memory dry-run 통과
  - checkpoint/resume 통과
  - max_seq_len 2048에서 최소 1 epoch OOM 없음
  - calibration/hidden-like metric이 r16 LoRA보다 좋을 가능성이 pilot에서 확인됨

## 48GB GPU batch/seq/rank 조정 기준

1. 시작점
   - Qwen3.5-4B, fp16/bf16, gradient checkpointing enabled.
   - `max_seq_len=2048`, `bs=2`, `grad_accum=4`를 r16 LoRA 시작점으로 둔다.
   - high-rank는 `bs=1`, `grad_accum=8`부터 시작한다.

2. VRAM target
   - 안정 target: peak allocated/reserved가 48GB의 `70-85%` 범위.
   - 확장 target: 안정 1 epoch 후 `85-92%`까지 올릴 수 있다.
   - 중단 target: reserved가 `>44GB`이거나 fragmentation/OOM 경고가 있으면 즉시 batch 또는 seq를 낮춘다.

3. 조정 순서
   - OOM 발생 시: `batch_size` 절반 -> `max_seq_len` 2048에서 1536 또는 1024 -> rank 감소 -> gradient checkpointing/flash attention 확인.
   - VRAM이 많이 남을 때: `batch_size` 1 증가 -> `max_seq_len` 3072 pilot -> rank 증가 순으로만 올린다.
   - `grad_accum`은 VRAM을 직접 늘리지 않으므로 GPU 활용률 개선 수단이 아니라 effective batch/optimization 조정 수단으로 본다.

4. small-data 일반화 기준
   - selected 480개 수준에서는 effective batch가 너무 크면 update 수가 줄고 generalization이 나빠질 수 있다.
   - 1차 sweep에서 effective batch는 `8` 또는 `16`을 넘기지 않는다.
   - GPU를 100% 채우기 위해 batch를 키우는 것보다, checkpoint별 metric과 long/source bucket 성능을 우선한다.

5. rank/seq interaction
   - rank를 키우면 trainable parameter와 optimizer state가 증가하므로, `r=64` 이상은 `bs=1`로 시작한다.
   - `max_seq_len`을 키우면 activation memory가 크게 증가하므로, long trajectory 개선 목적이 명확할 때만 3072/4096 pilot을 한다.
   - long trajectory 병목은 먼저 데이터 분포와 truncation rate를 확인하고, 그 다음 seq length를 올린다.

## monitoring/checkpoint/resume 기준

### 학습 중 항상 기록

- KST run dir
- git branch/commit
- manifest hash와 split counts
- hyperparameters: rank, alpha, dropout, lr, weight_decay, batch, grad_accum, max_seq_len, warmup, scheduler, seed
- epoch/step별 train loss, learning rate, grad norm
- checkpoint별 calibration/hidden-like metric
- threshold sweep 결과와 calibration-selected threshold
- ECE, Brier score, macro-F1, fail precision, fail recall
- length/source/worst bucket metric
- GPU peak allocated/reserved, `nvidia-smi` snapshot, OOM 여부
- checkpoint path, resume test 결과

### 중단/재개 기준

- 모든 run은 `save_strategy=epoch`, `save_total_limit>=3`, `--resume` 가능 상태로 둔다.
- pilot run도 최소 1개 checkpoint를 만든 뒤 resume smoke를 실행한다.
- OOM이 발생하면 같은 run dir에 OOM 시각, batch/seq/rank, peak memory, 조정 내용을 기록하고 재시작한다.

### early stop 기준

- 아래 중 하나가 발생하면 해당 후보는 중단한다.
  - NaN/Inf loss
  - epoch 2 이후 train loss만 급락하고 fail precision/recall 또는 ECE 악화
  - calibration threshold가 epoch마다 `>0.15` 흔들림
  - hidden-like no-regress 기준 `0.9146`보다 명확히 낮음
  - long/source worst bucket이 baseline보다 악화

## 최종 제안

1. 먼저 새 LLM-only sweep runner를 구현한다. 기존 `sweep_lora.py`는 rule dependency 때문에 사용하지 않는다.
2. r16 LoRA 충분 학습 baseline 3개(A1-A3)를 먼저 돌린다. 이 단계가 기준선이며, 이 결과 없이 high-rank/full FT를 leaderboard 후보로 보지 않는다.
3. 다음으로 high-rank LoRA r32/r64를 5 epoch까지 충분 학습한다. 좋은 후보 1개만 10 epoch로 확장한다.
4. 동시에 fail oversampling은 금지하고, label prior/calibration ablation을 별도 run으로 분리한다.
5. DoRA/QLoRA/partial FT는 high-rank LoRA baseline이 고정된 뒤 pilot으로 진행한다.
6. full fine-tuning은 partial/QLoRA pilot에서 capacity 이득이 확인된 뒤 실행한다. 48GB OOM과 small-data overfit 위험 때문에 지금 1순위는 아니다.
7. 모든 후보는 최종 adapter 또는 model artifact를 merged package로 export하고, `<12GB`, offline first-forward, no-rule scan을 통과해야 제출 후보가 된다.
8. leaderboard 제출은 서버 issue reject가 해소되고, 직전 제출 대비 model/data/package/runtime 차이가 명확하며, archive 기록이 준비됐을 때만 한다.

## 추천 sweep/monitoring 우선순위

1. 새 manifest-only sweep runner 구현: 기존 `sweep_lora.py` 대체.
2. r16 LoRA baseline 재현: `lr=1e-3/5e-4`, dropout `0.1/0.05`, `bs=2`, `ga=4`, 5 epoch.
3. high-rank LoRA: r32 -> r64 순서, OOM 없을 때만 확장.
4. calibration/label prior: oversampling 금지, threshold/ECE/Brier/temperature scaling 기록.
5. DoRA/QLoRA/partial FT pilot: resume/OOM/package gate 우선.
6. full fine-tuning: pilot 근거가 생긴 뒤 제한적으로 실행.
7. 모든 run 공통 monitoring: epoch/lr/loss/grad_norm/GPU peak/checkpoint resume/manifest-only hidden-like/package gate.

## 민감 정보 처리

- 이 문서에는 인증 정보, 비밀번호, 개인 토큰을 기록하지 않았다.
- 서버 접속에 필요한 민감 값은 조사/기록 대상에서 제외했다.
