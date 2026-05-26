<!-- Changed: add a stable handoff context that every worker agent must read or receive before doing repository work. -->
<!-- Why: agents were making isolated local progress without the project discussion context, which caused repeated drift from the LLM-only/data-first objective. -->

# Agent Handoff

- 최종 갱신: 2026-05-26 14:37 KST
- 목적: 새 agent가 단발 작업만 수행하지 않고, 현재 논의 맥락과 금지사항을 유지한 채 작업하게 한다.
- 적용 범위: repo 작업, 문서 정리, 데이터 생성/검증, 학습 실행, 서버 SSH 재시도, git push를 맡는 모든 worker agent.

## 절대 원칙

- 제출/학습 architecture에는 rule engine을 포함하지 않는다.
- runtime fallback, rule-id prompt, rule-derived label, rulebase verifier 결합은 금지한다.
- `src/solver.py`와 제출 package는 LLM-only entrypoint 기준으로 유지한다.
- 데이터 품질 gate용 invariant/state-transition audit는 runtime rule engine이 아니다. `src/solver.py`나 package inference path에서 import하면 안 된다.
- 사용자가 채팅에 남긴 서버 비밀번호, token, secret은 repo, docs, archive, log, command output에 저장하거나 출력하지 않는다.
- 기록은 한국어로 작성하고 시간은 KST를 사용한다.
- git push 대상은 `origin/sinjeongmin`이다.
- destructive git command, 다른 사람 변경 revert, `/workspace/team6` 의존 복구는 금지한다.

## 현재 결정사항

- 프로젝트 목표는 LLM-only Opal verifier다. Opal command-response trajectory에서 마지막 response가 명세와 현재 상태에 맞는지 `pass`/`fail`로 판정한다.
- 현재 병목은 모델보다 데이터다. 새 데이터는 양적 dimension뿐 아니라 질적으로 pass/fail이 맞는지 검증해야 한다.
- v4/v4.1 생성 데이터는 학습 금지 및 폐기 상태다.
  - 재현 근거: fail sample에서 중간 `Set FAIL` 뒤 마지막 `EndSession SUCCESS`인데 label이 `fail`이었다.
  - 원천 fail 538개 중 440개가 final `EndSession SUCCESS`로 끝나는 문제가 archive에 기록되어 있다.
  - 원인은 fail case 뒤에 `_endsession()`을 붙여 final-response label target이 중간 event로 밀린 생성 패턴이다.
- 새 데이터 생성은 Wang et al. 2023 Self-Instruct 하나를 제대로 따른다.
  - output-first classification generation을 사용한다.
  - LLM-only judge filtering을 사용한다.
  - 논문식 quality audit, evaluation, data-size/data-quality ablation을 구현 대상으로 둔다.
- leaderboard 제출은 Gate A-D와 package/runtime/secret/no-rule gate가 모두 통과한 뒤에만 검토한다.
- 12GB 제출 한계를 고려해 LoRA 3MB만 고집하지 않는다.
  - 0.8B/0.9B급 full fine-tuning은 후보로 유지한다.
  - 4B는 selective fine-tuning, LoRA/DoRA/QLoRA, last-n-layers 계열을 비교한다.
  - 27B는 full fine-tuning보다 특정 layer/adapter/quantized selective 계열만 현실 후보로 본다.

## 데이터 Gate 순서

1. Gate A: qualitative sampling state-transition audit
   - generated accepted pool 일부를 사람이 sampling한다.
   - records를 처음부터 끝까지 읽고 session state를 직접 전이해 본다.
   - final response가 generated label과 질적으로 맞는지 확인한다.
   - 중간 failure 뒤 final success인데 label `fail`인 sample은 reject한다.

2. Gate B: public20 dimension/schema/pass-fail distribution comparison
   - public 20과 schema, 평균 dimension vector, pass/fail 분포를 비교한다.
   - 최소 dimension vector: `record_count`, method sequence length, final method/status, input char/token count, return value count.
   - public 20 label은 training row로 복사하지 않고 aggregate 비교와 fold metric 계산에만 쓴다.

3. Gate C: manifest/model input path equivalence check
   - manifest validation을 통과한 동일 파일이 training loader와 model first-forward에서 같은 schema, sample id/hash, label mapping, dimension summary로 처리되는지 확인한다.
   - loader가 row를 조용히 drop/resample/relabel하거나 deprecated source를 섞으면 fail이다.

4. Gate D: leaderboard submission decision
   - Gate A-C, package `<12GB`, offline first-forward smoke, no-rule/secret gate가 모두 통과해야 go다.
   - 제출 전후에는 Korean archive record를 남긴다.
   - 하루 leaderboard 기회는 기존 결과와 무엇이 달라졌는지 설명할 수 있을 때만 사용한다.

## Agent가 반드시 읽어야 할 파일

- [docs/current_task.md](current_task.md): 현재 cycle 상태, 서버 상태, 다음 실행 순서.
- [docs/current_self_instruct_data_plan.md](current_self_instruct_data_plan.md): Self-Instruct 데이터 생성/검증 active spec.
- [docs/server_operations_current.md](server_operations_current.md): 서버 접속, sync, 제출 판단 절차.
- [docs/README.md](README.md): active/archive/delete 문서 정리 기준.
- [../README.md](../README.md): 현재 repo 운영 원칙과 도구 목록.
- [../PROGRESS.md](../PROGRESS.md): 현재 진행 상황 요약.
- [archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md](archive/cycles/2026-05-26/cycle_2026-05-26_kst_141324_v4_v41_data_invalidation.md): v4/v4.1 폐기 근거.
- [../tools/analysis/self_instruct_invariants.py](../tools/analysis/self_instruct_invariants.py): final-response invariant checker. 데이터 품질 gate 전용이다.
- [../tests/test_self_instruct_final_response_invariant.py](../tests/test_self_instruct_final_response_invariant.py): v4/v4.1 실패 모드 회귀 테스트.

## Agent 생성 시 붙일 짧은 Context Block

```text
공통 맥락:
- 목표는 LLM-only Opal verifier이며 architecture에 rule engine은 절대 넣지 않는다.
- 현재 병목은 데이터다. 생성 데이터는 평균 dimension뿐 아니라 pass/fail이 final response 기준으로 질적으로 맞는지 sampling state-transition audit로 확인해야 한다.
- v4/v4.1 생성 데이터는 폐기/학습 금지다. 중간 Set FAIL 뒤 final EndSession SUCCESS인데 label fail인 문제가 archive되어 있다.
- 새 데이터는 Wang et al. 2023 Self-Instruct 하나를 제대로 따른다: output-first classification generation, LLM-only judge filtering, quality audit/eval/ablation.
- Gate 순서: A 질적 state-transition audit, B public20 dimension/schema/pass-fail 분포 비교, C manifest/model input path equivalence, D leaderboard 제출 판단.
- invariant checker/state-transition audit는 데이터 품질 gate이지 runtime rule engine이 아니다.
- 작업 root는 /Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst 이고 서버 기준 root는 /workspace/sinjeongmin_opal_verifier 이다.
- push 대상은 origin/sinjeongmin 이다.
- 기록은 한국어, 시간은 KST, secret/password 출력/저장 금지.
- 다른 사람 변경을 되돌리지 말고 destructive git command를 쓰지 않는다.
```

## Git/검증 기준

- 작업 전 `git status --short --branch`로 현재 변경을 확인한다.
- 관련 파일을 읽고 active/archive/delete 기준에 맞는지 먼저 판단한다.
- 코드나 문서를 수정하면 이유가 드러나도록 Changed/Why comment 또는 archive record를 남긴다.
- 최소 검증:
  - secret scan은 원문 출력 없이 수행한다.
  - `git diff --check`
  - 변경 관련 단위 테스트
  - `python3 -m unittest discover -s tests -v`
- push 전 `origin/sinjeongmin`에 올릴 commit 범위를 확인한다.
- push 후 local HEAD와 `origin/sinjeongmin`의 commit hash 일치를 확인한다.

## 이번 cycle의 다음 우선순위

- 새 Self-Instruct pipeline 구현 전에 Gate A-D를 실행 가능한 도구와 문서로 고정한다.
- public20 원본 확보 자체는 사용자가 확인했으므로, 다음 agent는 public20을 학습 source로 쓰지 말고 dimension/schema/distribution reference로만 써야 한다.
- 생성 candidate가 만들어지면 일부 sample을 직접 state-transition audit한 뒤에만 public20 dimension 비교로 넘어간다.
- 서버 SSH는 main이 직접 치지 말고 agent가 10회 이상 재시도 단위로 수행한다.
- 서버가 회복되면 `/workspace/sinjeongmin_opal_verifier/repo`를 `origin/sinjeongmin` HEAD로 sync하고 기존 4B LoRA baseline 상태를 확인한다.
