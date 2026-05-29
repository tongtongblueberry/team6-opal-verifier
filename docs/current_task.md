# Current Task

<!-- Changed: 현재 task를 gen3.1 중단 후 문서 동기화 상태로 고정했다. -->
<!-- Why: 서버 생성과 local watcher가 모두 멈췄으므로 다음 worker가 active generation을 찾으면 안 된다. -->

- Updated: `2026-05-29 14:13:39 KST`.
- Local repo:
  `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`.
- Server repo: `/workspace/sinjeongmin_opal_verifier/repo`.
- Current user request: gen3.1 generation과 watcher를 멈추고 모든 live docs/Markdown 기록을 최신 상태로 맞춘다.

## 확인한 문서 구조

<!-- Changed: 파일 분석 전에 확인한 구조를 기록했다. -->
<!-- Why: file/document analysis는 skeleton을 먼저 확인해야 한다. -->

- `README.md`: current status, operating rule, Self-Instruct fit, current pipeline, active files, runs layout, verification.
- `PROGRESS.md`: current conclusion, Self-Instruct check, pipeline state, rejection evidence, runs cleanup, next work.
- `docs/agent_handoff.md`: first read, current objective, Self-Instruct mapping, live pipeline, interpretation, runs policy, hard rules.
- `docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`: decision, evidence, root cause, gen3 changes, restart plan.

## 현재 서버 상태

<!-- Changed: 서버와 로컬 watcher의 stopped factual state를 기록했다. -->
<!-- Why: 후속 작업은 stopped run evidence를 기준으로 해야 한다. -->

- Server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`.
- Server former parent PID: `120144`, stopped.
- Server former generator PID: `120148`, stopped.
- Server raw at stop: `72 / 1000`.
- GPU state after stop: `0 %, 0 MiB / 46068 MiB`.
- Local watcher screen `qwen_incremental_watch_gen31`: stopped.
- Local mirror: `runs/self_instruct/server_qwen_prod_gen31`.
- Local pending export: `data/local/gen3_pending`.
- Canonical local final export: `data/local/gen3`, kept empty until server full pipeline export is synced.
- Local counts at stop: raw `72`, parse rejects `51`, parsed candidates `21`,
  rule-book accepted `1`, rule-book rejected `20`, pending exported rows `1`.

## Self-Instruct 이해

<!-- Changed: Notion의 여섯 포인트와 현재 구현의 연결을 task 기준으로 압축했다. -->
<!-- Why: 지금 해야 할 일은 원본 paper를 그대로 복제하는 것이 아니라 fixed Opal 판정 task에 맞춘 구현을 유지하는 것이다. -->

Notion이 지적한 원본 Self-Instruct 대비 적용/비적용 포인트:

1. Instruction generation은 하지 않는다. fixed instruction을 사용한다.
2. Input null은 허용하지 않는다. trajectory가 없으면 판정 불가다.
3. Output-first를 사용한다. label은 final response에 붙는다.
4. Few-shot type matching은 생략한다. task type이 하나다.
5. Similarity filtering은 trajectory/domain/source-span 기준으로 바꾼다.
6. Fine-tuning은 full FT 고정이 아니라 resource-constrained SFT로 다룬다.

현재 pipeline 구현:

- fixed instruction과 `source_instruction_id`: `tools/datagen/run_self_instruct_generation.py`.
- target schedule: `tools/datagen/run_qwen_local_200_pipeline.sh`.
- raw parse/provenance 보존: `tools/datagen/parse_self_instruct_outputs.py`.
- final-response target invariant: `tools/analysis/self_instruct_invariants.py`.
- trajectory/domain dedup: `tools/analysis/dedup_self_instruct_candidates.py`.
- adversarial judge request: `tools/analysis/filter_self_instruct_judge.py`.
- rule-book export gate: `tools/analysis/adversarial_rulebook_quality_gate.py`.
- public schema export: `tools/datagen/export_self_instruct_gen_public_schema.py`.

## gen3 전환 근거

<!-- Changed: current run 설정의 근거를 archive 기록으로 연결했다. -->
<!-- Why: `1000/batch4/8192/pass:fail=1:1`은 Notion과 충돌한 것이 아니라 gen2 실패 이후의 전환 결과다. -->

`docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`에 따르면 gen2는 no-go다.

- gen2 raw `208/1000` 이후 final-pair parser 기준 `accepted_count=0`, `rejected_count=200`.
- `instruction_not_fixed=200`.
- pre-update gen2 export 41 rows는 auth-session row rate `0.122`로 public20 `0.8` 대비 낮았다.
- record counts `1,21,26,27,39`, `Write`, `Locking`, `MBRControl`, `LockingInfo` coverage가 부족했다.
- 그래서 gen3는 final-pair fixed instruction, exact rule-book source text, required domains, auth-session evidence, long public20-like lengths를 강제한다.
- `docs/archive/cycles/2026-05-29_gen3_zero_accept_gen31_restart.md`에 따르면 gen3는 raw `76/1000`까지 확인했지만 accepted `0`과 auth-session reject 반복으로 gen3.1로 재시작했다.
- gen3.1은 prompt contract `opal_final_response_spec_grounded_output_first.v3`, delexicalized public20 auth skeleton, state-transition self-check, warm-up curriculum을 사용한다.

## 현재 data flow

<!-- Changed: current data flow를 stopped gen3.1 evidence flow로 정리했다. -->
<!-- Why: old run roots와 stopped pending artifacts를 현재 generated training data로 쓰면 안 된다. -->

```text
public20 input-only seed
  -> gen3.1 target schedule with auth warm-up curriculum
  -> Qwen2.5-7B-Instruct local generation on team6 [stopped at 72 raw]
  -> local watcher pull [stopped]
  -> parser
  -> final-response invariant gate
  -> dedup
  -> adversarial judge payload
  -> adversarial rule-book gate
  -> data/local/gen3_pending export for monitoring
  -> server canonical gen_export after full server pipeline
  -> data/local/gen3 only after canonical sync
```

## 현재 blocker

<!-- Changed: stopped gen3.1의 blocker를 낮은 yield와 반복 mismatch로 정리했다. -->
<!-- Why: gate를 약화하거나 같은 pipeline을 재시작하면 gen2/gen3 실패가 반복된다. -->

현재 export 상태:

- gen3.1 raw `72`에서 rule-book accepted `1`이 나와 `data/local/gen3_pending` rows가 `1`이다.
- `data/local/gen3`은 server canonical final export 전용이라 현재 0 rows다.
- rejected rows는 `20`이며 주요 reject는 missing `Locking`, label mismatch, final status mismatch, auth-session evidence missing, record-count mismatch다.

조치 방향:

- gate를 약화하지 않는다.
- gen3.1을 그대로 재시작하지 않는다.
- 다음 시도 전 reject taxonomy/gate audit 또는 deterministic OPAL skeleton/value generator를 설계한다.

## cleanup 작업

<!-- Changed: 사용자 요청의 남은 작업을 stopped state 문서화로 남겼다. -->
<!-- Why: 다음 agent가 멈춘 pipeline을 되살리거나 pending row를 training data로 쓰면 안 된다. -->

1. gen3.1 run과 watcher는 멈춘 상태로 유지한다.
2. 모든 live docs/Markdown은 stop counts와 no-training status를 반영한다.
3. `runs/self_instruct/server_qwen_prod_gen31`은 active generation이 아니라 stopped evidence mirror다.
4. legacy `runs` artifacts는 `archive/runs_legacy_20260529_gen3_cleanup/`에 둔다.

## hard rules

<!-- Changed: runtime/data safety rules를 현 task에 맞게 유지했다. -->
<!-- Why: cleanup 중 old generated data나 runtime rule logic이 다시 들어오면 안 된다. -->

- Runtime remains LLM-only.
- Offline rule-book gates are data validation, not runtime inference.
- `public20` labels are local-only and never enter synthetic generation or judge prompts.
- `data/local/gen3_pending` rows are not training/sample eligible.
- `data/local/gen3` rows are training/sample eligible only after server canonical export sync and all gates pass.
- Secrets must not be copied into docs, commands, logs, or archives.
