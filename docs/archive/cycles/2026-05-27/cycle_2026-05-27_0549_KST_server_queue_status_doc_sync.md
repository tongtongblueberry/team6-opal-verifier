<!-- Changed: add a docs-sync archive record for the active server queue status update. -->
<!-- Why: active docs now reflect the running 0.9B full FT official TRL queue and need a cycle record in the required evidence format. -->

# Server Queue Status Doc Sync

- 작성 시각: 2026-05-27 05:49 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 수정 범위: `docs/agent_handoff.md`, `PROGRESS.md`, `README.md`, `docs/current_task.md`, `docs/server_operations_current.md`

## Structural Skeleton

[Original Text/Data] `docs/agent_handoff.md`: `# Agent Handoff`, `## 절대 원칙`, `## 현재 결정사항`, `## 데이터 Gate 순서`, `## Agent가 반드시 읽어야 할 파일`, `## Agent 생성 시 붙일 짧은 Context Block`, `## Git/검증 기준`, `## 이번 cycle의 다음 우선순위`.
-> [Exact Interpretation] Handoff 문서는 새 worker가 가장 먼저 보는 active 상태와 금지사항의 상위 기준이다.
-> [Detailed Explanation/Example] 서버 queue가 pending restart에서 running queue로 바뀌었으므로 `현재 결정사항`, context block, 다음 우선순위가 새 run root와 queue pid를 포함해야 한다.

[Original Text/Data] `PROGRESS.md`: `# Progress Log`, `## 현재 Architecture`, `## 과거 Rule + LoRA 설명의 상태`, `## 현재 데이터/학습 상태`, `## 현재 서버 상태`, `## Leaderboard 제출 판단`, `## 최근 정리`.
-> [Exact Interpretation] Progress 문서는 현재 학습/서버/제출 판단을 요약하는 active log다.
-> [Detailed Explanation/Example] 0.9B full FT official TRL queue start는 학습 상태와 서버 상태에 모두 반영되어야 하며, 결과 pending 때문에 leaderboard는 no-go로 유지된다.

[Original Text/Data] `README.md`: `# Team 6 Opal Verifier`, `## 현재 원칙`, `## 현재 제출 구조`, `## 현재 주요 도구`, `## 현재 운영 문서`, `## 로컬 검증`, `## 서버 Sync 원칙`, `## Leaderboard 제출 기준`.
-> [Exact Interpretation] README는 repo root에서 보는 운영 기준과 제출 gate의 입구 문서다.
-> [Detailed Explanation/Example] 서버 sync 섹션은 현재 running queue를 알려야 하고, leaderboard 섹션은 package/submission candidate가 없음을 명시해야 한다.

[Original Text/Data] `docs/current_task.md`: `# 현재 진행 상태 (세션 이어받기용)`, `## 현재 Cycle 결론`, `## 데이터 현황`, `## v4/v4.1 폐기 evidence`, `## 학습 현황`, `## Full/Selective Fine-tuning 판단`, `## Package/Git 현황`, `## 서버 상태`, `## 다음 실행 순서`, `## 보안`.
-> [Exact Interpretation] current_task는 이어받는 worker의 실행 순서를 정하는 문서다.
-> [Detailed Explanation/Example] 다음 실행 순서는 TRL dataset 변환/재시작이 아니라 queue 결과 확인으로 바뀌어야 한다.

[Original Text/Data] `docs/server_operations_current.md`: `# 현재 서버 운영 절차`, `## 접속`, `## 서버 Repo 동기화`, `## 연결 회복 직후 확인 순서`, `## 제출 판단`.
-> [Exact Interpretation] 서버 운영 문서는 server worker가 queue 상태와 제출 판단을 확인하는 active 절차다.
-> [Detailed Explanation/Example] 연결 회복 직후 확인 순서에는 run root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft`, queue pid `318407`, job `plain_seed11_e20`, GPU process pid `318415` 확인이 포함되어야 한다.

## Queue Facts

[Original Text/Data] `0.9B full FT official TRL 10/10 queue started on server`.
-> [Exact Interpretation] public20-only 10/10 model validation의 0.9B full fine-tuning queue가 시작됐다.
-> [Detailed Explanation/Example] 이전 문서의 "GPU retraining restart pending"은 더 이상 현재 상태가 아니며, active docs는 running queue로 갱신되어야 한다.

[Original Text/Data] run root `/workspace/sinjeongmin_opal_verifier/ops/runs/20260527_0545_KST_public20_trl_10_10_09b_fullft`.
-> [Exact Interpretation] 현재 서버 queue의 root directory다.
-> [Detailed Explanation/Example] 결과, logs, model/eval/status 확인은 이 경로 아래에서 수행해야 하며 이전 4B interrupted run root를 후보 root로 쓰면 안 된다.

[Original Text/Data] queue pid `318407`, current job initially `plain_seed11_e20`, GPU process pid `318415`, L40S ~27GB used.
-> [Exact Interpretation] queue manager와 첫 training process가 실행 중인 상태로 관측됐다.
-> [Detailed Explanation/Example] `plain_seed11_e20`은 plain variant, seed `11`, epoch `20` job이며 GPU memory 사용량은 실제 training process가 올라왔다는 상태 evidence다.

[Original Text/Data] queue order: e20, e30, e5, e10; each block plain seeds 11/29/47 then retrieved seeds 11/29/47; model Qwen/Qwen3.5-0.8B; PEFT/LoRA disabled.
-> [Exact Interpretation] 실행 순서는 epoch block 우선이고 각 block 안에서 plain 3 seeds 뒤 retrieved 3 seeds를 실행한다. 학습은 Qwen 0.8B 계열 full fine-tuning이다.
-> [Detailed Explanation/Example] queue의 첫 6개 job은 `plain_seed11_e20`, `plain_seed29_e20`, `plain_seed47_e20`, `retrieved_seed11_e20`, `retrieved_seed29_e20`, `retrieved_seed47_e20`로 해석된다.

[Original Text/Data] eval configured: generation + logprob, max-length 8192, sidecar p_fail json.
-> [Exact Interpretation] 각 완료 job은 generation evaluator와 logprob evaluator를 모두 돌리고, logprob 기반 fail probability sidecar를 남기도록 설정됐다.
-> [Detailed Explanation/Example] `p_fail` sidecar는 package candidate가 아니라 validation evidence 보조 파일이다. threshold/package 판단은 결과 확인 뒤 별도 기록이 필요하다.

[Original Text/Data] results pending; no package/submission candidate yet.
-> [Exact Interpretation] queue start 자체는 제출 근거가 아니며 leaderboard no-go는 유지된다.
-> [Detailed Explanation/Example] active docs는 "running"과 "candidate 없음"을 동시에 기록해야 한다. metric, calibration, package smoke가 없으면 제출 판단을 열 수 없다.

[Original Text/Data] sample.md remains no-go; data real generation blocked by missing provider key.
-> [Exact Interpretation] synthetic data sample 공개 상태는 서버 queue start와 무관하게 닫혀 있다.
-> [Detailed Explanation/Example] `OPENAI_API_KEY`/`GEMINI_API_KEY` 부재로 real Self-Instruct raw generation이 없으므로 `docs/samples/self_instruct_sample.md`는 만들지 않는다.
