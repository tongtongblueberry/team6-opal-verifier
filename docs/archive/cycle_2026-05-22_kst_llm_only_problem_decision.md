<!-- 변경: cycle 1 step 2 문제점 결정 기록을 신규 작성. 이유: LLM-only 방향의 우선순위, 제출 판정, 다음 목표 설정 입력을 KST 기준으로 보존하기 위함. -->
# Cycle 기록: LLM-only 문제점 결정 (KST 2026-05-22)

기록 시각: 2026-05-22 14:54:48 KST

## 구조적 Skeleton

- 문서 목적: cycle 1 step 2에서 현재 문제점의 우선순위와 leaderboard 제출 여부를 결정한다.
- 입력 근거: git agent, 데이터 agent, 학습 agent, leaderboard agent, architecture agent의 이전 결론 요약.
- 허용 범위: LLM-only architecture만 인정한다. Rule engine, rule-gated fallback, rule-context 학습/추론은 architecture에 포함하지 않는다.
- 산출 항목:
  - 결정 요약
  - 원자료 해석 기록
  - 우선순위 문제
  - Leaderboard 제출 판정
  - 다음 목표 설정 입력
  - Git/운영 주의사항

## 결정 요약

오늘의 결론은 제출 no-go이다. 현재 가장 큰 문제는 모델 성능 자체가 아니라 데이터 계약과 평가 신뢰성이다. 공개 20개 label이 train/upsample/original anchors에 직접 들어간 흔적이 있고, random split은 group/template leakage 가능성이 있으며, rule-context 계열은 LLM-only 제약과 충돌한다. 따라서 step 3은 새 학습이나 제출이 아니라 LLM-only 데이터 계약, 검증 metric, 제출 gate를 먼저 확정해야 한다.

Architecture 결정은 `src/solver.py::Solver`의 LoRA-only fail-closed 후보만 인정한다. Stateful verifier, rule-gated fallback, probe, conformal rule deferral, rule-context LoRA v3는 이번 LLM-only 제출 후보에서 제외하거나 격리한다.

## [Original Text/Data] → [Exact Interpretation] → [Detailed Explanation/Example]

1. [Original Text/Data] "현재 branch dev, origin/dev보다 8 commits ahead. staged 없음. unstaged: .gitignore, docs/cycle_tracker.md, src/solver.py, tools/eval/eval_consistency.py. untracked: configs/train_manifest.cycle7.json, tools/analysis/build_supervised_manifest.py, tools/analysis/data_audit.py, tools/analysis/validate_manifest.py, tools/eval/eval_3adapters.py, tools/training/train_wd.py. 기존 변경은 건드리지 말 것." → [Exact Interpretation] 현재 worktree는 이미 여러 agent/user 변경을 포함하며, 이번 step 2는 기존 변경을 수정하거나 되돌리면 안 된다. → [Detailed Explanation/Example] 문제점 결정 기록은 신규 markdown 파일 1개로만 남긴다. `src/solver.py`나 eval/training script를 열어 수정하지 않는다.

2. [Original Text/Data] "가장 큰 데이터 위험은 공개 20개 label이 train/upsample/original anchors에 직접 들어간 흔적. 문서상 원칙과 코드가 충돌." → [Exact Interpretation] 현재 학습 데이터는 public label contamination 가능성이 있어 leaderboard 성능과 validation 성능을 신뢰하기 어렵다. → [Detailed Explanation/Example] 공개 20문제의 label이 학습 anchor로 들어갔다면 public 16/20 같은 점수는 일반화 근거가 아니라 노출된 정답에 대한 적합 결과일 수 있다.

3. [Original Text/Data] "random split은 group/template leakage 가능." → [Exact Interpretation] validation split이 동일 template 또는 유사 group을 train과 공유할 수 있어 hidden-like 검증으로 보기 어렵다. → [Detailed Explanation/Example] 같은 template에서 값만 바뀐 샘플이 train과 validation에 동시에 있으면 validation accuracy는 실제 hidden 성능보다 높게 측정될 수 있다.

4. [Original Text/Data] "rule-context prompt/data는 LLM-only 제약과 충돌." → [Exact Interpretation] rule engine 또는 rule-derived context를 입력 prompt/data로 사용하는 경로는 LLM-only architecture 후보에서 제외해야 한다. → [Detailed Explanation/Example] rule-context LoRA v3가 점수를 올리더라도 이번 방향에서는 architecture 위반 리스크가 있으므로 제출 후보가 아니다.

5. [Original Text/Data] "train max_length 1024 vs inference 2048 mismatch." → [Exact Interpretation] 학습과 추론 입력 길이 조건이 다르며, truncation/position behavior 차이로 checkpoint 평가가 불안정할 수 있다. → [Detailed Explanation/Example] 학습 때 잘린 context가 추론 때 포함되면 LoRA가 보지 못한 prompt 분포에서 동작할 수 있고, 반대로 학습 때 필요한 suffix가 잘렸다면 학습 label과 실제 추론 조건이 어긋난다.

6. [Original Text/Data] "canonical manifest null과 safety gate 비활성." → [Exact Interpretation] canonical 데이터 계약과 제출 전 차단 조건이 충분히 강제되지 않는다. → [Detailed Explanation/Example] manifest 필드가 null인 상태로 학습/평가가 진행되면 어떤 데이터가 어떤 split과 source에서 왔는지 검증할 수 없고, gate가 비활성화되어도 제출 pipeline이 멈추지 않을 수 있다.

7. [Original Text/Data] "여러 학습 경로가 있으나 지금은 학습을 더 돌리기보다 데이터 계약, LLM-only schema, checkpoint별 eval 로그 확보가 선행." → [Exact Interpretation] cycle 1 step 3의 우선 목표는 training run이 아니라 계약/스키마/eval 로그 정리이다. → [Detailed Explanation/Example] 새 adapter를 학습하기 전에 어떤 manifest가 허용되는지, 어떤 prompt schema가 LLM-only인지, 어떤 checkpoint가 어떤 metric을 통과했는지 먼저 남겨야 한다.

8. [Original Text/Data] "KST 2026-05-22 현재 제출 no-go. #24 LLM-only 제출은 public 16/20, hidden 70.00으로 기존 최고 73.00보다 낮음." → [Exact Interpretation] 최신 LLM-only 제출은 기존 최고 성능을 넘지 못했고, 오늘 leaderboard 제출의 기대 이득이 낮다. → [Detailed Explanation/Example] hidden 70.00은 기존 최고 73.00보다 3.00 낮으므로 동일 계열을 추가 근거 없이 재제출할 이유가 없다.

9. [Original Text/Data] "#24 대비 새 adapter, canonical manifest, hidden-like validation, gate 통과 기록이 없음." → [Exact Interpretation] #24 이후 제출을 정당화할 새 evidence가 없다. → [Detailed Explanation/Example] 새 checkpoint가 있더라도 canonical manifest와 hidden-like validation 및 gate 통과 로그가 없으면 제출 판단 근거로 사용할 수 없다.

10. [Original Text/Data] "제출 진입점은 src/solver.py::Solver LoRA-only fail-closed 후보만 인정." → [Exact Interpretation] 최종 제출 후보는 단일 LLM/LoRA 경로로 실패 시 안전하게 닫히는 구조여야 한다. → [Detailed Explanation/Example] fallback이 rule output을 내거나 verifier가 stateful rule을 적용하면 LLM-only 후보에서 제외한다.

11. [Original Text/Data] "StatefulOpalVerifier, llm_solver rule-gated fallback, probe, conformal rule deferral, rule-context LoRA v3는 보류/격리." → [Exact Interpretation] 이 컴포넌트들은 연구/분석 artifact로 남길 수는 있어도 제출 architecture에는 포함하지 않는다. → [Detailed Explanation/Example] step 3에서 metric을 잡을 때도 이 경로들의 점수와 LoRA-only 점수를 섞으면 안 된다.

12. [Original Text/Data] "README/PROGRESS/prepare_submission 문서는 현재 LLM-only 방향과 불일치." → [Exact Interpretation] 운영 문서가 현재 결정과 다르므로 제출 준비 시 오판을 유발할 수 있다. → [Detailed Explanation/Example] 문서가 rule pipeline을 제출 가능 경로처럼 설명하면 담당자가 LLM-only no-go 조건을 놓칠 수 있다. 단, 이번 step 2에서는 기존 문서를 수정하지 않는다.

## 우선순위 문제

P0. Public label contamination 의심

- 결정: 최우선 차단 문제로 지정한다.
- 이유: 공개 20개 label이 train/upsample/original anchors에 들어간 흔적이 있으면 public score와 validation score를 제출 판단 근거로 사용할 수 없다.
- step 3 필요 출력: 공개 20개 label exclusion 기준, source별 audit 결과, contamination 발견 시 fail 처리 기준.

P0. LLM-only architecture 위반 경로 혼재

- 결정: rule engine, rule-gated fallback, rule-context prompt/data를 제출 후보에서 제외한다.
- 이유: 이번 architecture에는 rule engine을 포함하지 않으며, LLM 기반 방향만 허용된다.
- step 3 필요 출력: `src/solver.py::Solver` 기준 LoRA-only fail-closed 경로 정의, 제외 경로 목록, 제출 artifact에 포함 가능한 파일/모듈 기준.

P0. Leaderboard 제출 근거 부족

- 결정: 오늘 제출을 막는 제출 gate 문제로 지정한다.
- 이유: #24 이후 새 adapter, canonical manifest, hidden-like validation, gate 통과 기록이 없다.
- step 3 필요 출력: 제출 가능 조건 checklist와 각 조건의 통과 로그 위치.

P1. Hidden-like validation 부재 및 random split leakage 가능성

- 결정: 다음 metric 설계의 핵심 문제로 지정한다.
- 이유: random split이 group/template leakage를 만들면 hidden 성능 추정이 왜곡된다.
- step 3 필요 출력: group/template-aware split 기준, public 20과 hidden-like validation을 분리하는 평가 표.

P1. Canonical manifest 계약 미확정/null 허용

- 결정: 데이터 pipeline 선행 문제로 지정한다.
- 이유: manifest가 canonical하지 않거나 필수 필드 null을 허용하면 학습/평가 재현성과 검증 가능성이 떨어진다.
- step 3 필요 출력: 필수 필드, null 금지 필드, source lineage, split reason, label provenance.

P1. Checkpoint별 eval 로그 부족

- 결정: 학습 재개보다 먼저 확보해야 할 evidence로 지정한다.
- 이유: checkpoint별 public/local/hidden-like/consistency metric이 없으면 성능 변화의 원인을 판단할 수 없다.
- step 3 필요 출력: checkpoint id, adapter id, manifest id, prompt schema id, max_length, metric, timestamp를 포함한 eval log schema.

P2. Train/inference max_length mismatch

- 결정: 성능 신뢰성 문제로 지정하되 P0/P1 해결 후 조정한다.
- 이유: 학습 1024와 추론 2048의 분포 차이가 checkpoint 비교를 흐릴 수 있다.
- step 3 필요 출력: train/eval/inference max_length 통일 여부와 truncation audit metric.

P2. Safety gate 비활성

- 결정: 제출 운영 문제로 지정한다.
- 이유: known risk가 있어도 제출 pipeline이 멈추지 않으면 no-go 판단이 실행되지 않는다.
- step 3 필요 출력: contamination, schema mismatch, missing eval log, non-LLM-only path 감지 시 fail하는 gate 항목.

P3. 문서 불일치

- 결정: 제출 전 정리해야 할 운영 리스크로 지정한다.
- 이유: README/PROGRESS/prepare_submission의 설명이 LLM-only 결정과 다르면 제출 담당자가 잘못된 경로를 선택할 수 있다.
- step 3 필요 출력: 수정 대상 문서 목록과 LLM-only 기준으로 맞출 문구 범위. 이번 step에서는 기존 문서를 수정하지 않는다.

## Leaderboard 제출 판정

판정: 오늘 KST 2026-05-22 leaderboard 제출 no-go.

이유:

- #24 LLM-only 제출은 public 16/20, hidden 70.00이며 기존 최고 73.00보다 낮다.
- #24 이후 새 adapter 성능, canonical manifest, hidden-like validation, gate 통과 기록이 없다.
- public label contamination 의심이 해결되지 않아 local/public 점수를 신뢰할 수 없다.
- rule-context 또는 rule-gated 경로는 LLM-only architecture 조건과 충돌한다.
- `src/solver.py::Solver`의 LoRA-only fail-closed 제출 후보가 검증되었다는 기록이 없다.

제출 재개 조건:

- public 20 label exclusion 및 train/upsample/original anchor audit 통과.
- canonical manifest의 필수 필드와 null 금지 조건 통과.
- LLM-only prompt/data schema 확정 및 rule-context 제거 확인.
- group/template-aware hidden-like validation 통과.
- checkpoint별 eval log 확보.
- 제출 진입점이 LoRA-only fail-closed이며 rule fallback이 없다는 확인.
- safety gate 활성화 및 통과 기록 확보.

## 다음 목표 설정 입력

Step 3에서 결정해야 할 질문:

1. Canonical manifest에서 필수 필드와 null 금지 필드는 무엇인가?
2. 공개 20개 label을 train/upsample/original anchors에서 배제했음을 어떻게 증명할 것인가?
3. LLM-only schema의 허용 입력은 어디까지인가? Rule-derived context, verifier output, probe result는 모두 제외할 것인가?
4. `src/solver.py::Solver`의 제출 후보 경로를 LoRA-only fail-closed로 어떻게 식별하고 고정할 것인가?
5. Hidden-like validation은 group/template leakage를 어떤 기준으로 차단할 것인가?
6. Checkpoint별 eval log는 어떤 id와 metric을 필수로 기록할 것인가?
7. Train/eval/inference max_length는 1024로 통일할지, 2048로 재학습/재평가할지, 또는 truncation audit 후 결정할지?
8. Safety gate는 어떤 조건에서 hard fail해야 하는가?
9. 문서 불일치는 제출 전 어느 문서부터 정리할 것인가?

Step 3 metric 후보:

- contamination audit: public 20 label overlap count, source별 overlap count, anchor overlap count.
- leakage audit: group/template overlap ratio between train and validation.
- schema audit: LLM-only prompt field compliance, rule-context field count, null 필수 필드 count.
- eval metric: public 20 accuracy, hidden-like validation accuracy, consistency score, invalid output rate, fail-closed rate.
- checkpoint traceability: checkpoint id, adapter id, manifest id, prompt schema id, max_length, eval script id, timestamp.
- submission gate: contamination pass/fail, schema pass/fail, hidden-like pass/fail, solver path pass/fail, docs readiness pass/fail.
- training monitor if training resumes: epoch, learning rate, loss, eval metric, batch size, GPU memory/utilization.

## Git/운영 주의사항

- 현재 branch는 `dev`이며 `origin/dev`보다 8 commits ahead 상태로 기록되었다.
- staged 변경은 없는 상태로 기록되었다.
- 기존 unstaged/untracked 파일은 다른 agent 또는 사용자의 작업물로 간주하고 수정하지 않는다.
- 이번 step 2의 유일한 파일 생성은 `docs/archive/cycle_2026-05-22_kst_llm_only_problem_decision.md`이다.
- 코드 수정, 기존 문서 수정, 제출 실행, 학습 실행은 하지 않는다.
- Architecture 기록에는 rule engine을 포함하지 않는다. 제출 후보는 LLM-only LoRA fail-closed 경로만 인정한다.
