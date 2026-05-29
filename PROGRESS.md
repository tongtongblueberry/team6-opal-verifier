# Progress Log

<!-- Changed: progress를 gen3.1 중단 상태로 갱신했다. -->
<!-- Why: 이전 기록은 gen3.1이 active generation 중인 상태였고, 현재는 사용자 지시에 따라 서버 생성과 watcher를 모두 멈췄다. -->

- Updated: `2026-05-29 14:13:39 KST`.

## 현재 결론

<!-- Changed: 현재 lane을 stopped/no-training 상태로 명확히 했다. -->
<!-- Why: pending 1 row가 있지만 canonical generated training data는 없다. -->

- Active synthetic-data lane은 없다. gen3.1 Qwen local Self-Instruct run은 중단됐다.
- Stopped server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`.
- Local watcher mirror preserved for evidence: `runs/self_instruct/server_qwen_prod_gen31`.
- Canonical final export path: server `$RUN/gen_export`, then local `data/local/gen3` after explicit sync.
- Local incremental pending export path: `data/local/gen3_pending`.
- Stopped server command는 `1000` requests, `1` candidate/request, batch size `4`,
  `max_new_tokens=8192`, temperature `0.45`, top_p `0.9`, pass/fail alternating schedule,
  `CURRICULUM_WARMUP_REQUESTS=160`이다.
- Stop counts: server raw `72/1000`; local raw `72`, parse rejects `51`,
  parsed candidates `21`, rule-book accepted `1`, rejected `20`, pending exported rows `1`.
- Server former PIDs `120144` and `120148` are stopped; GPU after stop was `0 %, 0 MiB / 46068 MiB`.
- Local watcher screen `qwen_incremental_watch_gen31` and orphan watcher children are stopped.
- 따라서 `data/local/gen3_pending`은 현재 1 row지만 monitoring artifact일 뿐이다.
- `data/local/gen3`은 server canonical final export 전용이라 현재 0 row로 유지한다.

## 정정 사항

<!-- Changed: Notion 기록과 current run의 관계를 정정했다. -->
<!-- Why: 현재 run 설정은 gen2 no-go 분석 이후의 의도된 gen3 변경이다. -->

- Notion `SELF-INSTRUCT` 페이지의 `480 / batch16 / max_new_tokens=4096 / pass:fail≈1:2`는 이전 파이프라인 스냅샷이다.
- `docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`가 gen3 전환의 직접 근거다.
- 현재 `1000 / batch4 / max_new_tokens=8192 / pass:fail=1:1` 실행은 gen2 no-go 이후 재시작한 active gen3 run이다.
- 따라서 올바른 해석은 "Notion 메모 이후 gen2 실패 분석을 반영한 gen3 전환"이다.
- gen3 raw `76/1000`까지 확인한 뒤 accepted `0`과 auth-session reject 반복을 근거로 gen3.1로 다시 재시작했다.

## Self-Instruct 확인

<!-- Changed: Notion의 여섯 가지 적용/비적용 포인트를 현재 pipeline과 연결했다. -->
<!-- Why: 우리 파이프라인은 원본 Self-Instruct를 그대로 복제하지 않고 Opal final-response 판정 문제에 맞게 축소/변형한다. -->

Notion에서 확인한 원본 논문 구성 요소 중 우리 파이프라인에 그대로 적용하지 않는 여섯 가지:

1. Instruction 생성: fixed Opal final-response instruction으로 대체한다.
2. Input null: trajectory input이 필수라 null input을 허용하지 않는다.
3. 입력 우선 vs 출력 우선: output-first만 사용한다.
4. Few-shot 유형 매칭: task type이 하나라 생략한다.
5. 유사도/중복 필터링: 고정 instruction 대신 trajectory/domain/source-span 텍스트 기준으로 바꾼다.
6. Fine-tuning: full FT만 고정하지 않고 resource에 따라 TRL SFT full FT/LoRA/QLoRA를 선택한다.

현재 코드는 이 대응을 다음 방식으로 구현한다.

- `run_self_instruct_generation.py`: fixed instruction, `source_instruction_id`, classification no-op provenance, output-first candidate schema, target schedule metadata를 생성한다.
- `run_qwen_local_200_pipeline.sh`: gen3 target schedule에 final method/status/count, required domains, auth-session 조건을 넣는다.
- `parse_self_instruct_outputs.py`: raw wrapper의 instruction/provenance를 candidate로 보존한다.
- `self_instruct_invariants.py`: label target이 `records[-1].output`인지 검증한다.
- `dedup_self_instruct_candidates.py`: 고정 instruction 대신 domain/trajectory signature 기반 중복 제거를 수행한다.
- `filter_self_instruct_judge.py`: final-response target, source span support, state transition consistency를 judge payload로 만든다.
- `adversarial_rulebook_quality_gate.py`: `docs/legacy_spec_rules.md` source span, final pair, target schedule, auth session, required domains를 실제 export 전에 검사한다.

gen3.1 추가 구현:

- public20 input-only records에서 delexicalized `StartSession` auth skeleton을 prompt에 제공한다.
- generator가 rule-book source span을 보며 session/auth/object state table을 internally 확인하고, 그 결과를 `spec_grounding.state_transition_notes`와 `primary_evidence.reason`에 쓰도록 요구한다.
- warm-up schedule은 먼저 authenticated `Get`, `Set`, `Activate` cases에서 accepted rate를 만들도록 조정했다.

## gen2 no-go 근거

<!-- Changed: archive 기록의 핵심 근거를 progress에 반영했다. -->
<!-- Why: gen3 설정 변경의 원인을 raw count나 임의 튜닝으로 오해하지 않게 한다. -->

`docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md` 기준:

- gen2 server run은 `208/1000` raw까지 갔지만 final-pair parser 기준으로 `accepted_count=0`, `rejected_count=200`.
- reject reason은 `instruction_not_fixed=200`.
- 마지막 usable pre-update gen2 export는 41 rows였지만 auth-session row rate `0.122`로 public20 `0.8` 대비 낮았다.
- 부족했던 coverage는 public-like record counts `1,21,26,27,39`, `Write`, `Locking`, `MBRControl`, `LockingInfo`.
- root cause는 final `(cN, rN)` 판정 contract, rule-book source text, public-like session/domain/length 강제가 약했던 것이다.

## 현재 rejection 근거

<!-- Changed: stopped gen3.1의 마지막 reject 근거를 최신 rule-book report로 기록했다. -->
<!-- Why: 중단 이유가 watcher 문제가 아니라 낮은 yield와 반복 target/rule-book mismatch임을 보존한다. -->

Latest gen3.1 local rule-book report:

- `candidate_count=21`
- `accepted_count=1`
- `rejected_count=20`

Reject reasons:

- `required_context_domains_missing:Locking`: `8`
- `target_label_mismatch:fail!=pass`: `5`
- `target_final_status_mismatch:SUCCESS!=INVALID_PARAMETER`: `4`
- `required_auth_session_missing_hostchallenge_or_authority`: `4`
- record-count mismatches across scheduled `9/10/11/21` targets: multiple.
- pass final status not supported by cited rule-book for `SUCCESS` against `INVALID_PARAMETER/FAIL` and `NOT_AUTHORIZED/FAIL`: `2` total.

Interpretation: gen3.1은 raw `72`에서 accepted `1`을 만들었다. gen3보다 개선은 있었지만 accepted yield가 낮고 target schedule alignment, required domain, auth-session evidence 문제가 다시 반복되어 계속 태우는 효율이 낮다.

## runs 정리

<!-- Changed: active/archive boundary를 cleanup 작업 기준으로 명시했다. -->
<!-- Why: runs/에는 현재 pipeline artifacts만 남겨야 한다. -->

- Keep as stopped evidence: `runs/self_instruct/server_qwen_prod_gen31`.
- Move legacy artifacts to: `archive/runs_legacy_20260529_gen3_cleanup/`.
- Archive targets: old figures, old model-validation artifacts, old public20 baseline run artifacts,
  old self-instruct partial/prod/gen2/smoke/targeted/fallback roots.

## 다음 작업

<!-- Changed: 다음 작업을 stopped state 기준으로 정리했다. -->
<!-- Why: 현 파이프라인을 그대로 재개하면 같은 낮은 yield가 반복된다. -->

1. gen3.1 server generation과 watcher는 재시작하지 않는다.
2. `data/local/gen3_pending` 1 row는 monitoring artifact일 뿐 학습 데이터가 아니다.
3. `data/local/gen3`은 0 rows이며 학습 데이터가 없다.
4. 다음 synthetic-data 시도는 prompt만 늘리는 방식이 아니라 reject taxonomy/gate audit 또는 deterministic OPAL skeleton/value generator 설계 후 시작한다.
