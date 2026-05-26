<!-- 변경: Cycle 2 Step 3 목표 설정 기록을 신규 작성. 이유: archive 기반으로 leaderboard, hidden-like, 20-case, package runtime, data gate 목표를 LLM-only 기준으로 고정하기 위함. -->
# Cycle 2 Step 3 목표 설정 - archive 기록 기반

작성 시각: 2026-05-26 01:35 KST  
작성 범위: `docs/archive` 전체와 관련 training/eval 기록을 근거로 한 목표 설정  
원칙: architecture에는 rule engine을 포함하지 않는다. 과거 rule 기반 결과는 비교 기준으로만 언급한다.

## 구조 Skeleton

1. 검토 범위
   - archive 문서 22개: `docs/archive/*.md`
   - 학습 기록: `tools/training/train_manifest_lora.py`, legacy trainer/sweep 관련 archive 기록
   - 평가/패키징 기록: `tools/eval/eval_manifest_adapter.py`, `tools/eval/check_submit_package.py`, `tools/eval/runtime_smoke_submit_package.py`, `tools/eval/export_merged_model.py`
2. 현재 기준선
   - leaderboard/제출 상태
   - LLM-only public/20-case 및 hidden-like 기록
   - packaging/runtime gate 기록
   - data gate 기록
3. 주요 근거
4. 목표 제안
   - 1차 목표
   - 2차 목표
   - 궁극 목표
5. 제출 판정 원칙
6. 다음 cycle로 넘길 실행 기준

## 현재 기준선

- LLM-only leaderboard 기준선: `70.00`. 근거는 `cycle_8_step2_problem_analysis.md`의 기준선 기록과 `cycle_8_step6_results.md`의 사이클 2 결과다.
- LLM-only public/20-case 기준선: 최고 `16/20`, 최신 악화 사례 `15/20`.
- archive상 최고 비교 기준: rule 기반 `71.50` 실제 확인, `73.00`은 이전 목표/메모리 기록의 비교 기준이다. 이 문서는 이 값을 architecture 후보로 사용하지 않는다.
- Data Contract v2 기준선: selected records `480`, length JSD `0.006999`, public/eval holdout metadata hits `0`, rule-context metadata/input hits `0`.
- package 기준선:
  - adapter-only actual package: `32M`, offline first-forward PASS였지만 제출 서버 issue reject.
  - merged artifact candidate: package `7.9G`, submit archive `6378.08 MB`, static gate와 first-forward PASS였지만 제출 서버 issue reject.
- 제출 상태: 현재 leaderboard는 server availability reject로 job ID와 score가 없다. 같은 package 반복 제출은 NO-GO다.

## 주요 근거

1. [Original Text/Data] `cycle_2026-05-22_kst_llm_only_problem_decision.md:21-23`는 "제출 no-go", "가장 큰 문제는 모델 성능 자체가 아니라 데이터 계약과 평가 신뢰성", 그리고 `src/solver.py::Solver`의 LoRA-only fail-closed 후보만 인정한다고 기록했다.  
   → [Exact Interpretation] 목표는 새 모델 점수만으로 정하면 안 되고, LLM-only data/eval/package gate를 동시에 포함해야 한다.  
   → [Detailed Explanation/Example] public label contamination, random split leakage, rule-context 혼재가 해결되지 않으면 public 또는 local 점수가 높아도 leaderboard 제출 근거가 되지 않는다.

2. [Original Text/Data] `cycle_2026-05-22_kst_data_contract_v2_pass.md:8-19`는 Data Contract v2 manifest gate 통과, `selected_records=480`, `length_jsd=0.006999`, public/eval holdout metadata hits `0`, rule-context metadata/input hits `0`을 기록했다.  
   → [Exact Interpretation] 현재 데이터 gate의 최소 기준은 DCv2 hard gate 통과다.  
   → [Detailed Explanation/Example] 새 학습 manifest가 만들어져도 `exact duplicate`, `group leakage`, `public/eval holdout`, `rule-context`가 다시 0이어야 하며, length JSD는 `<= 0.08` 기준을 유지해야 한다.

3. [Original Text/Data] `cycle_2026-05-22_kst_data_contract_v2_pass.md:40-47`는 train split만 학습, calibration/hidden split 학습 금지, rule engine/StatefulOpalVerifier/public dataset path trainer 호출 금지, `--resume` 가능성을 필수 조건으로 기록했다.  
   → [Exact Interpretation] 목표에는 재시작 가능한 학습 운영 gate가 포함되어야 한다.  
   → [Detailed Explanation/Example] GPU OOM 없이 충분히 학습하더라도 checkpoint resume이 안 되거나 calibration/hidden split을 학습에 섞으면 제출 후보가 아니다.

4. [Original Text/Data] `submission_attempt_2026-05-22_kst_dcv2-final-b784715_timeout_unconfirmed.md:18-22`는 manifest-only hidden accuracy `0.9368421053 / FN 0`, package smoke `PeftModelForCausalLM`, rule engine 구조 제거를 제출 판단 근거로 기록했다.  
   → [Exact Interpretation] hidden-like metric은 이미 높은 내부 기준선이 있으므로, 다음 목표는 단순 `72%`가 아니라 기존 내부 기준선을 재현하거나 넘는 방향이어야 한다.  
   → [Detailed Explanation/Example] 1차 목표는 StratP0/merged candidate가 최소 `0.9146` 수준을 유지하고, 2차 목표는 DCv2 final의 `0.936842`를 넘기는 것으로 둔다.

5. [Original Text/Data] `compact_state_2026-05-22_kst.md:33-39`는 calibration acc `0.895833 / FN0`, hidden acc `0.936842 / FN0`을 이어받기 상태로 기록했다.  
   → [Exact Interpretation] calibration/hidden-like split은 제출 score를 대신하지 않지만, daily 제출 전 no-regress gate로 써야 한다.  
   → [Detailed Explanation/Example] hidden-like가 높아도 server package가 깨지면 0점이고, package가 통과해도 hidden-like가 낮으면 daily chance를 쓸 이유가 없다.

6. [Original Text/Data] `cycle_8_step2_problem_analysis.md:4-6`는 기준선을 LLM-only hidden `70.00`, public `16/20`, 목표 hidden `73+`로 기록했다. 같은 문서 `141-147`은 사이클 2를 public `16/20`, hidden `70.00`으로 요약했다.  
   → [Exact Interpretation] LLM-only 점수 개선의 1차 leaderboard 목표는 `70.00` 재현, 2차 목표는 `73.00` 도달이다.  
   → [Detailed Explanation/Example] package/runtime 복구 직후 첫 유효 job은 0점 실패 방지가 우선이고, 다음 유효 학습 실험은 `70.00`을 넘겨 `73.00`에 도달해야 한다.

7. [Original Text/Data] `cycle_8_step6_results.md:3-5`는 최신 악화 사례가 public `15/20`, 기존 최고 `16/20` 대비 `-1`이라고 기록했다. `cycle_8_step6_results.md:30-45`는 사이클 8이 데이터 694건, fail 65%, dropout 0.0, 낮은 LR, grad_accum 16, threshold 0.40으로 바뀌었다고 기록했다.  
   → [Exact Interpretation] 20-case 목표는 최소 `16/20` 재현이며, label prior와 calibration을 같이 관리해야 한다.  
   → [Detailed Explanation/Example] 데이터 건수만 210에서 694로 늘어도 fail prior가 65%로 치우치고 dropout을 제거하면 public 성능이 하락했다. 따라서 새 데이터 목표는 "더 많이"가 아니라 "balanced/diverse/long + gate 통과"다.

8. [Original Text/Data] `cycle_8_step6_results.md:131-145`는 실패 원인을 fail oversampling으로 인한 label prior 왜곡, dropout 0.0 과적합, eval_loss 기준 best model 선택 오류로 확정했다.  
   → [Exact Interpretation] 목표 metric에는 fail precision/recall, ECE/Brier 또는 threshold 안정성, checkpoint별 accuracy가 포함되어야 한다.  
   → [Detailed Explanation/Example] eval loss만 감소하는 checkpoint를 고르면 실제 20-case 정확도가 떨어질 수 있으므로, 충분 학습 비교는 epoch별 hidden-like accuracy와 threshold sweep을 함께 기록해야 한다.

9. [Original Text/Data] `cycle_2026-05-26_kst_005000_parent_leaderboard_submit_llmonly_offlinefix_24cb540.md:17-19`는 actual package HF readiness OK, legacy verifier/rule scan hit `0`, offline first-forward PASS를 기록했다. 같은 문서 `25-35`는 submit이 server issue로 reject되고 job이 생성되지 않았다고 기록했다.  
   → [Exact Interpretation] Cycle 1의 제출 문제는 모델 score 문제가 아니라 runtime/package 및 server availability 문제로 분류한다.  
   → [Detailed Explanation/Example] package gate를 통과한 뒤에도 server availability reject면 leaderboard score가 없으므로, 같은 artifact를 즉시 반복 제출하지 않는다.

10. [Original Text/Data] `cycle_2026-05-26_kst_005000_parent_leaderboard_submit_llmonly_offlinefix_24cb540.md:48`는 package size `32M`을 기록하고, 다음 cycle에서 merged LoRA/DoRA BF16, partial/full fine-tuning artifact, quantized merged artifact를 비교해야 한다고 기록했다.  
    → [Exact Interpretation] 12GB 제출 용량을 쓰지 않는 adapter-only package는 최종 후보로 약하다.  
    → [Detailed Explanation/Example] adapter-only는 ablation으로 유지하되, leaderboard 후보는 merged/full/partial standalone artifact를 우선한다.

11. [Original Text/Data] `cycle_2026-05-26_kst_012633_merged_artifact_submit_server_reject.md:15-24`는 merged artifact 후보가 기존 실패와 다르게 `artifacts/merged_model` 직접 로드 경로를 사용하고, package size `7.9G`, submit archive `6378.08 MB`였으며, static/runtime gate를 통과했다고 기록했다.  
    → [Exact Interpretation] package capacity와 runtime gate 목표는 Cycle 2에서 1차 달성됐다. 남은 blocker는 server availability와 점수 개선 학습이다.  
    → [Detailed Explanation/Example] 다음 목표는 merged artifact support를 유지하면서 high-rank LoRA/DoRA/QLoRA/partial/full FT 결과를 같은 gate로 비교하는 것이다.

12. [Original Text/Data] `cycle_2026-05-26_kst_012633_merged_artifact_submit_server_reject.md:65-81`는 submit output이 `Submission rejected`, `Reason: Submission is not available due to server issue`, post-submit list 34 submissions 그대로, 새 job ID 없음이라고 기록했다.  
    → [Exact Interpretation] leaderboard 현재 상태는 NO-GO다.  
    → [Detailed Explanation/Example] 새 제출은 서버 availability 정상화 증거와 새 artifact/metric 차별성이 있을 때만 허용한다.

13. [Original Text/Data] `cycle_2026-05-26_kst_0130_step2_problem_decision.md:49-65`는 최종 문제 우선순위를 길이/trajectory 구조 분포 불일치, source/template 다양성 부족, label prior 및 calibration 불안정, 학습 capacity와 구현 infra 미성숙으로 정했다.  
    → [Exact Interpretation] 목표는 data distribution, source diversity, calibration, model capacity를 모두 분리해서 측정해야 한다.  
    → [Detailed Explanation/Example] full fine-tuning을 시도하더라도 long trajectory coverage와 label prior가 깨지면 점수 개선 원인을 알 수 없다.

14. [Original Text/Data] `cycle_2026-05-26_kst_0130_step2_problem_decision.md:67-77`는 후보 목표로 hidden-like accuracy `>=72%`, `>=75%`, 궁극 LLM-only leaderboard `>=75`, package `<12GB`, server-side runtime failure `0건`을 제시했다.  
    → [Exact Interpretation] 최신 문제 판정은 package 안정화와 LLM-only leaderboard 개선을 같이 요구한다.  
    → [Detailed Explanation/Example] 이 문서에서는 archive의 더 높은 내부 hidden-like 기록을 반영해 hidden-like 수치는 상향 조정하되, leaderboard 단계 목표는 `70 -> 73 -> 80` 구조로 유지한다.

15. [Original Text/Data] `tools/training/train_manifest_lora.py:94-116`는 manifest/run-root/adapter-name 기반 LLM-only LoRA trainer 인자를 정의하고 epochs `5`, batch `1`, grad_accum `8`, lr `1e-3`, max_seq_len `2048`을 기본값으로 둔다.  
    → [Exact Interpretation] 현재 신뢰 가능한 주 학습 경로는 manifest-only LoRA이고, full FT/DoRA/QLoRA는 아직 별도 구현 목표다.  
    → [Detailed Explanation/Example] full FT를 고려하더라도 먼저 같은 manifest split, resume, epoch/lr/loss/GPU log를 남기는 training contract를 맞춰야 한다.

16. [Original Text/Data] `tools/training/train_manifest_lora.py:218-234`와 `251-261`은 trainer 내부에서 public/eval holdout marker와 rule-context marker를 fail-closed로 차단한다.  
    → [Exact Interpretation] 데이터 gate는 validator뿐 아니라 trainer에서도 재검증되어야 한다.  
    → [Detailed Explanation/Example] validator를 우회해 manifest를 넘겨도 trainer가 public/rule-context 흔적을 발견하면 학습을 중단해야 한다.

17. [Original Text/Data] `tools/eval/eval_manifest_adapter.py:20-24`, `38-57`, `168-215`는 manifest-only evaluator가 calibration/hidden split만 허용하고 public dataset path, rule-context, solver signal을 금지한다고 정의한다.  
    → [Exact Interpretation] hidden-like 목표 측정은 public 20 직접평가나 rule-derived evaluator가 아니라 manifest-only evaluator 기준이어야 한다.  
    → [Detailed Explanation/Example] `eval_checkpoints.py`는 legacy public/rule dependency가 있으므로, 제출 gate의 주 metric은 `eval_manifest_adapter.py` 계열로 옮겨야 한다.

18. [Original Text/Data] `tools/eval/check_submit_package.py:64-74`는 `_init_rule_engine`, `StatefulOpalVerifier`, `ProtocolState`, `RULE_SPEC_QUERIES`, `verify_with_trace`, `RuleEngine`, `USE_RULE_ENGINE`, `rule_context`, `rule_id`를 forbidden marker로 차단한다. 같은 파일 `275-293`은 setup, solver HF policy, no-rule path, model artifact를 package readiness gate로 묶는다.  
    → [Exact Interpretation] package 목표에는 no-rule executable scan이 반드시 포함된다.  
    → [Detailed Explanation/Example] merged model package가 로드되더라도 solver 실행 코드가 rule marker를 포함하면 제출 후보가 아니다.

19. [Original Text/Data] `tools/eval/runtime_smoke_submit_package.py:121-192`는 package static check 이후 offline env에서 solver의 `local_files_only=True`와 optional first-forward를 검증한다.  
    → [Exact Interpretation] 제출 전 package runtime gate는 static check만으로 충분하지 않고 first-forward까지 요구해야 한다.  
    → [Detailed Explanation/Example] first-forward는 Solver construction과 `predict_one()`을 한 번 통과시켜 evaluator runtime failure를 줄인다.

20. [Original Text/Data] `tools/eval/export_merged_model.py:97-165`는 base + LoRA adapter를 `merge_and_unload()`로 standalone merged artifact로 저장하고 total size를 출력한다.  
    → [Exact Interpretation] 12GB 용량 활용 목표는 이미 구현 가능한 export path가 있다.  
    → [Detailed Explanation/Example] high-rank LoRA/DoRA/partial/full FT 후보도 최종 비교 시 `artifacts/merged_model` 또는 equivalent standalone artifact로 package gate를 통과해야 한다.

## 목표 제안

### 1차 목표: 제출 가능성 회복과 LLM-only no-regress

- Leaderboard 목표:
  - server availability가 정상화된 뒤 유효 job ID를 생성한다.
  - `Error 0.00`, timeout, package/runtime failure 없이 score를 받는다.
  - score가 나오면 LLM-only 기존 기준선 `70.00` 이상을 1차 성공으로 본다.
- Hidden-like metric 목표:
  - StratP0 계열 no-regress 기준: accuracy `>= 0.9146`.
  - fail precision `>= 0.90`, fail recall `>= 0.80`.
  - calibration split에서 선택한 threshold만 사용하고 hidden-like split으로 threshold를 고르지 않는다.
- 20-case 목표:
  - LLM-only 기존 최고 public-like 기준 `16/20` 이상.
  - `15/20` 이하는 최신 악화 사례 재현이므로 제출 NO-GO.
- Package/runtime gate:
  - `check_submit_package.py` PASS.
  - `runtime_smoke_submit_package.py --offline --first-forward` PASS.
  - no-rule executable marker scan PASS.
  - package size `< 12GB`.
  - adapter-only 제출은 긴급 복구/ablation 외에는 지양하고, merged artifact 후보를 기본 제출 후보로 둔다.
- Data gate:
  - Data Contract v2 overall PASS.
  - exact duplicate `0`, group leakage `0`, unknown label `0`.
  - public/eval holdout metadata hits `0`.
  - rule-context metadata/input hits `0`.
  - length JSD `<= 0.08`.
  - training은 `split == "train"`만 사용하고 calibration/hidden split은 학습 금지.

### 2차 목표: LLM-only로 73선 도달

- Leaderboard 목표:
  - LLM-only leaderboard `>= 73.00`.
  - 비교 기준인 rule 기반 `71.50`을 넘거나 최소 동률 이상이어야 한다. 단, rule engine architecture를 재도입하지 않는다.
- Hidden-like metric 목표:
  - DCv2 final 기록인 accuracy `0.936842` 이상.
  - fail precision `>= 0.92`, fail recall `>= 0.85`.
  - macro-F1 개선을 같이 기록한다.
  - ECE `<= 0.12` 또는 threshold bucket별 calibration 악화 없음.
- 20-case 목표:
  - `17/20` 이상.
  - threshold 변경 전후 confusion matrix를 기록한다.
- Package/runtime gate:
  - 1차 package gate 유지.
  - merged/full/partial standalone artifact가 `< 12GB` 안에서 offline first-forward PASS.
  - 제출 전 hash, artifact manifest, KST run dir를 archive한다.
- Data gate:
  - 1차 hard gate 유지.
  - pass/fail label prior를 대략 `40:60`에서 `60:40` 범위로 유지한다.
  - fail oversampling 금지. 불균형 대응은 class weight, focal loss, threshold/calibration 쪽으로 분리한다.
  - long trajectory 비중과 source/template diversity를 기록한다.
  - Length Coverage `>= 0.25` 또는 이에 준하는 long trajectory 분포 개선 증거를 확보한다.

### 궁극 목표: LLM-only 80선과 안정 제출

- Leaderboard 목표:
  - LLM-only leaderboard `>= 80.00`.
  - stretch goal은 `85.00`으로 기록하되, 4B 단일 LoRA만으로 보장하지 않는다.
- Hidden-like metric 목표:
  - 현재 DCv2/StratP0보다 명확히 높은 accuracy `>= 0.95`.
  - fail precision `>= 0.95`, fail recall `>= 0.90`.
  - ECE `<= 0.08`.
  - worst length/source/template group accuracy `>= 0.60`.
- 20-case 목표:
  - `18/20` 이상, 가능하면 `20/20`.
  - public 20 직접학습 또는 public label anchor 사용은 금지한다.
- Package/runtime gate:
  - server-side runtime failure `0건`.
  - final submit candidate는 static gate, offline first-forward, size `< 12GB`, no-rule scan, artifact manifest hash를 모두 archive한 뒤 제출한다.
  - merged high-rank LoRA, DoRA, QLoRA, partial FT, full FT 후보 중 동일 protocol에서 가장 좋은 후보를 선택한다.
- Data gate:
  - hard gate는 1차와 동일하게 유지한다.
  - Length Coverage `>= 0.50`.
  - normalized template entropy `>= 0.75` 또는 Vendi Score `>= 10`.
  - source/template group leakage `0`.
  - label prior 왜곡 없이 long/diverse/balanced manifest를 유지한다.

## 제출 판정 원칙

- 현재 leaderboard 상태는 NO-GO다. 이유는 마지막 두 제출 시도가 모두 server availability reject이고 job ID가 없기 때문이다.
- 다음 제출은 아래 조건을 모두 만족할 때만 한다.
  - 서버 availability 정상화 증거가 있다.
  - 직전 제출과 다른 구조적 차이가 있다. 예: merged artifact, 새 학습 방법, 새 manifest, threshold/calibration, package runtime gate 중 하나 이상이 달라야 한다.
  - hidden-like metric이 직전 제출 후보보다 낮지 않다.
  - package/runtime/data gate를 모두 통과했다.
  - 제출 전후 KST 기준 archive를 작성한다.
- 같은 package를 server issue 상태에서 반복 제출하지 않는다.

## 다음 cycle로 넘길 실행 기준

1. Cycle 3는 `cycle2/merged-artifact-20260526-kst`에서 분기한다. 이유는 merged artifact/package gate infra가 이미 검증됐기 때문이다.
2. 우선 실험 순서는 high-rank LoRA 또는 DoRA/QLoRA pilot, 그 다음 partial full fine-tuning, 마지막으로 full fine-tuning이다.
3. 모든 후보는 최소 충분 학습 조건을 만족해야 한다.
   - epoch별 checkpoint 저장.
   - resume 가능.
   - lr/loss/grad norm/GPU memory 기록.
   - OOM 발생 시 batch size/grad accumulation 조정 기록.
   - 동일 manifest split과 동일 evaluator로 비교.
4. 선택 기준은 leaderboard 기대값이 아니라 `data gate + hidden-like + 20-case + package first-forward + size < 12GB`의 통합 결과다.
