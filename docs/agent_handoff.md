# Agent Handoff

<!-- Changed: handoff를 gen3.1 stopped state와 cleanup 상태 중심으로 갱신했다. -->
<!-- Why: 다음 agent가 멈춘 generation/watcher를 active pipeline으로 오해하지 않게 한다. -->

- Updated: `2026-05-29 14:13:39 KST`.
- Active local root:
  `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`.
- Active server root: `/workspace/sinjeongmin_opal_verifier/repo`.

## 먼저 읽을 것

<!-- Changed: handoff 시작 시 읽어야 할 파일을 현재 권위 순서로 정리했다. -->
<!-- Why: gen3 전환 근거를 archive에서 먼저 확인해야 current 설정을 오해하지 않는다. -->

1. `docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`
2. `docs/archive/cycles/2026-05-29_gen3_zero_accept_gen31_restart.md`
3. `README.md`
4. `PROGRESS.md`
5. `docs/current_task.md`
6. `docs/agent_handoff.md`
7. `tools/datagen/run_qwen_local_200_pipeline.sh`
8. `tools/datagen/watch_qwen_incremental_pull.sh`
9. `tools/analysis/adversarial_rulebook_quality_gate.py`

## 현재 목표

<!-- Changed: active objective를 stopped pipeline 기록과 문서 정리로 고정했다. -->
<!-- Why: old fallback/model-validation/training lanes뿐 아니라 gen3.1 rerun도 자동 재개하면 안 된다. -->

현재 목표는 gen3.1 Self-Instruct/Qwen generation 중단 상태를 보존하면서 다음을 끝내는 것이다.

- gen3.1 server generation과 local watcher를 재시작하지 않는다.
- stopped evidence mirror인 `runs/self_instruct/server_qwen_prod_gen31`을 보존한다.
- `data/local/gen3_pending` 1 row는 monitoring artifact로만 둔다.
- `data/local/gen3` 0 rows 상태를 유지한다.
- legacy run artifacts는 `archive/runs_legacy_20260529_gen3_cleanup/`로 이동한다.

## Self-Instruct mapping

<!-- Changed: Notion-derived six-point mapping을 현재 구현 기준으로 남겼다. -->
<!-- Why: 원본 Self-Instruct를 verbatim 적용하지 않는 이유가 다음 작업 판단의 기준이다. -->

Notion page가 지적한 원본 Self-Instruct 대비 우리 적용/비적용 포인트:

1. Instruction generation: fixed Opal final-response instruction으로 대체.
2. Input null: trajectory input 필수라 금지.
3. Input-first vs output-first: output-first only.
4. Few-shot type matching: 단일 task type이라 생략.
5. Similarity filtering: instruction text 대신 trajectory/domain/source-span 기준으로 adaptation.
6. Fine-tuning: full FT 고정이 아니라 resource에 따라 TRL SFT full FT/LoRA/QLoRA.

현재 코드 대응:

- `run_self_instruct_generation.py`: fixed instruction, provenance, output-first schema, candidate target schedule.
- `self_instruct_invariants.py`: `records[-1].output` final-response target 검증.
- `dedup_self_instruct_candidates.py`: fixed instruction collapse를 피하고 domain/trajectory similarity 사용.
- `filter_self_instruct_judge.py`: final target/source span/state transition judge payload.
- `adversarial_rulebook_quality_gate.py`: export 전 source span, target schedule, auth, required domain 검증.

## gen3 restart 기준

<!-- Changed: current run 설정의 근거를 gen2 no-go archive로 명확히 연결했다. -->
<!-- Why: Notion의 이전 실행 스냅샷과 현재 gen3 실행값은 gen2 no-go 전후의 서로 다른 기준이다. -->

`docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`에 따르면:

- gen2는 raw `208/1000`까지 갔지만 final-pair parser 기준으로 `accepted_count=0`, `rejected_count=200`.
- reject reason은 `instruction_not_fixed=200`.
- gen2 usable export 41 rows는 auth-session row rate `0.122`로 public20 `0.8` 대비 낮았다.
- missing coverage는 record counts `1,21,26,27,39`, `Write`, `Locking`, `MBRControl`, `LockingInfo`.
- gen3는 `opal_final_response_spec_grounded_output_first.v2`, exact rule-book `source_text`, required domains, auth-session evidence, long trajectory counts를 강제한다.

따라서 current server run의 `1000 / batch4 / max_new_tokens=8192 / pass:fail=1:1`은 gen2 no-go 이후의 active restart 설정이다.

gen3.1 restart 기준:

- `docs/archive/cycles/2026-05-29_gen3_zero_accept_gen31_restart.md`에 따르면 gen3는 raw `76/1000`에서 stopped.
- gen3 local mirror는 parsed `8`, accepted `0`, rejected `8`.
- 반복 reject는 `required_auth_session_missing_hostchallenge_or_authority=8`.
- gen3.1은 `opal_final_response_spec_grounded_output_first.v3`, delexicalized public20 auth skeleton, state-transition self-check, warm-up curriculum을 사용한다.

## live pipeline

<!-- Changed: stopped generation/export path를 기록했다. -->
<!-- Why: archived gen2/smoke/fallback/model-validation outputs와 gen3.1 pending row를 current training data로 쓰면 안 된다. -->

```text
public20 input-only seed
  -> gen3.1 target schedule with auth warm-up curriculum
  -> Qwen2.5-7B-Instruct local generation on server [stopped at 72 raw]
  -> local incremental watcher [stopped]
  -> parser
  -> invariant gate
  -> dedup
  -> adversarial judge payload
  -> adversarial rule-book gate
  -> data/local/gen3_pending export for monitoring
  -> server canonical gen_export after full server pipeline
  -> data/local/gen3 only after canonical sync
```

Stopped paths:

- Server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`
- Local mirror:
  `runs/self_instruct/server_qwen_prod_gen31`
- Export:
  pending local monitor `data/local/gen3_pending`; canonical final `data/local/gen3`
- Watcher:
  screen `qwen_incremental_watch_gen31`, stopped

Last checked state:

- Server raw: `72 / 1000`.
- Server former PIDs `120144` and `120148`: stopped.
- Server GPU after stop: `0 %, 0 MiB / 46068 MiB`.
- Local raw: `72`.
- Parse rejects: `51`.
- Parsed candidates: `21`.
- Rule-book accepted: `1`.
- Rule-book rejected: `20`.
- Pending exported rows: `1`.
- Canonical `data/local/gen3` rows: `0`.
- Canonical exported rows: `0`.

## interpretation

<!-- Changed: stopped low-yield 상태를 future worker가 gate bypass로 처리하지 않도록 설명했다. -->
<!-- Why: gen2/gen3 실패 원인이 quality gate 약화와 prompt contract 부족이었기 때문이다. -->

gen3.1 produced one accepted pending-export row from 72 raw rows. That is not enough for
training or sample publication. Remaining rejects include target-schedule mismatch,
required-domain missing, label/final-status mismatch, and auth-session evidence missing.

For any future restart:

- Do not weaken `adversarial_rulebook_quality_gate.py`.
- Inspect raw/parse rejects.
- First build reject taxonomy/gate audit or deterministic OPAL skeleton/value generation.

## runs policy

<!-- Changed: cleanup 후 active/archive boundary를 handoff에 남겼다. -->
<!-- Why: 사용자가 runs/에 현재 pipeline artifacts만 남기라고 요청했다. -->

- Keep as stopped evidence: `runs/self_instruct/server_qwen_prod_gen31`.
- Move legacy to: `archive/runs_legacy_20260529_gen3_cleanup/`.
- Legacy includes old figures, model-validation data, public20 baseline run artifacts,
  prior Qwen partial/prod/gen2/smoke outputs, targeted schedules, and old self-instruct archives.

## hard rules

<!-- Changed: runtime and data eligibility rules를 유지했다. -->
<!-- Why: cleanup이 solver architecture나 training eligibility를 바꾸면 안 된다. -->

- Runtime solver remains LLM-only.
- Offline rule-book gates are data validation, not runtime inference.
- Do not use public20 labels in generation, judge prompts, or generated targets.
- Do not train on `data/local/gen3_pending`.
- Do not train on `data/local/gen3` until server canonical export is synced and follow-up gates pass.
- Do not store secrets in repo files, docs, command lines, logs, or archives.
- Do not revert user changes or run destructive git commands.
