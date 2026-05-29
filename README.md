# Team 6 Opal Verifier

<!-- Changed: 문서를 현재 gen3 Self-Instruct/Qwen 파이프라인 기준으로 다시 작성했다. -->
<!-- Why: Notion의 이전 파이프라인 메모와 gen2 no-go 이후 gen3 전환 기록을 혼동하지 않도록 현재 권위 기준을 분리한다. -->

SNU Introduction to Deep Learning (M2177.0043) Opal command-response trajectory
pass/fail classification project.

## 현재 기준

<!-- Changed: 현재 작업의 권위 기록과 gen3.1 중단 상태를 명시했다. -->
<!-- Why: stopped run을 active generation으로 오해하면 watcher나 training data를 다시 섞게 된다. -->

- 최신 확인 시각: `2026-05-29 14:13:39 KST`.
- Notion `SELF-INSTRUCT` 페이지는 원본 Self-Instruct를 우리 문제에 어떻게 적용/비적용할지 정리한 메모다.
- gen3 전환의 권위 기록은
  `docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`다.
- gen3.1 중단 기록은
  `docs/archive/cycles/2026-05-29_gen3_zero_accept_gen31_restart.md`다.
- Notion에 적힌 `480 / batch16 / max_new_tokens=4096 / pass:fail≈1:2`는 gen3 전환 전 파이프라인 스냅샷이다.
- 마지막 gen3.1 run은 gen3 zero-accept 이후 재시작한 run이며, 실행값은 서버 프로세스 기준
  `1000 / batch4 / max_new_tokens=8192 / pass:fail=1:1`이었다.
- `2026-05-29 14:13 KST` 기준 gen3.1 generation과 local watcher는 모두 중단됐다.

## Self-Instruct 적용

<!-- Changed: Notion 페이지에서 확인한 여섯 가지 적용/비적용 포인트를 현재 해석으로 고정했다. -->
<!-- Why: 우리 문제는 단일 Opal final-response 판정 태스크라 원본 Self-Instruct를 그대로 복제하면 안 된다. -->

Notion이 정리한 원본 Self-Instruct 대비 우리 파이프라인의 핵심 차이는 여섯 가지다.

1. Instruction 생성: 원본은 instruction을 생성하지만, 우리는 Opal final-response 판정 instruction 하나를 고정한다.
2. Input null: 원본은 null input이 가능하지만, 우리는 trajectory record가 없으면 판정 불가라 input이 필수다.
3. 입력 우선 vs 출력 우선: 원본은 태스크별 선택이지만, 우리는 `records[-1].output`을 label target으로 삼는 output-first 생성만 사용한다.
4. Few-shot 유형 매칭: 원본은 task type별 few-shot을 맞추지만, 우리는 task type이 하나라 별도 유형 매칭이 필요 없다.
5. 유사도/중복 필터링: 원본의 ROUGE-L instruction 중복 필터 원칙은 유지하되, 고정 instruction 대신 trajectory/domain/source-span 기반으로 바꾼다.
6. Fine-tuning: 원본은 full fine-tuning을 사용하지만, 우리는 resource에 따라 TRL SFT full FT/LoRA/QLoRA를 선택한다.

[EXTERNAL KNOWLEDGE] Wang, Y., Kordi, Y., Mishra, S., Liu, A., Smith, N. A.,
Khashabi, D., & Hajishirzi, H. (2023). Self-Instruct: Aligning language models
with self-generated instructions. In A. Rogers, J. Boyd-Graber, & N. Okazaki
(Eds.), Proceedings of the 61st Annual Meeting of the Association for
Computational Linguistics (Volume 1: Long Papers) (pp. 13484-13508).
Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.754

## gen3 전환 근거

<!-- Changed: gen2 no-go 원인을 README의 운영 기준으로 올렸다. -->
<!-- Why: 현재 1000/batch4/8192 설정과 rule-book gate는 임의 변경이 아니라 gen2 실패 분석의 후속 조치다. -->

`docs/archive/cycles/2026-05-29_gen2_no_go_gen3_restart.md`에 기록된 gen2 no-go 이유:

- gen2 raw `208/1000` 중 parser를 final-pair instruction 기준으로 바꾼 뒤 `accepted_count=0`, `rejected_count=200`.
- reject 핵심 이유는 `instruction_not_fixed=200`.
- 마지막 usable gen2 export는 41 rows였지만 auth-session row rate가 `0.122`로 public20의 `0.8`보다 낮았다.
- public-like record count `1,21,26,27,39`, `Write`, `Locking`, `MBRControl`, `LockingInfo` coverage가 부족했다.
- root cause는 전체 trajectory를 읽되 최종 `(cN, rN)`만 판정한다는 contract와 rule-book grounded source text 강제가 약했던 것이다.

따라서 gen3는 다음을 강제한다.

- Prompt contract: `opal_final_response_spec_grounded_output_first.v2`.
- Fixed instruction:
  `Given the full Opal command-response trajectory, judge only whether the final command-response pair (cN, rN) is valid under the cited rule-book.`
- `docs/legacy_spec_rules.md`의 exact `source_text`를 prompt와 gate에서 사용한다.
- target schedule에 `required_context_domains`, auth-session 요구, final method/status/count 요구를 넣는다.
- Locking, MBRControl, LockingInfo, Authority, K_AES_256, C_PIN, SP와 long trajectory count `21,26,27,39`를 강제한다.
- watcher는 export 전에 `adversarial_rulebook_quality_gate.py`를 실행한다.

gen3.1 추가 변경:

- Prompt contract: `opal_final_response_spec_grounded_output_first.v3`.
- public20 input-only records에서 delexicalized auth skeleton을 추출해 prompt에 넣는다.
- 생성 중 rule-book/source span을 기준으로 session/auth/object state self-check를 하도록 요구한다.
- 첫 warm-up curriculum은 authenticated `Get`, `Set`, `Activate` 중심으로 시작한다.

## 현재 파이프라인

<!-- Changed: gen3.1 데이터 흐름을 stopped state 기준으로 남겼다. -->
<!-- Why: legacy fallback, gen2, smoke, model-validation 산출물뿐 아니라 중단된 gen3.1 pending export도 training data로 오해하지 않게 한다. -->

```text
data/local/public20/public20_input.jsonl
  -> tools/datagen/run_qwen_local_200_pipeline.sh
  -> target_schedule.json
  -> tools/datagen/run_self_instruct_generation.py
  -> Qwen2.5-7B-Instruct local raw generation on team6
  -> tools/datagen/watch_qwen_incremental_pull.sh [stopped]
  -> tools/datagen/parse_self_instruct_outputs.py
  -> tools/analysis/self_instruct_invariants.py
  -> tools/analysis/dedup_self_instruct_candidates.py
  -> tools/analysis/filter_self_instruct_judge.py request/audit payload
  -> tools/analysis/adversarial_rulebook_quality_gate.py
  -> tools/datagen/export_self_instruct_gen_public_schema.py
  -> server canonical gen_export after full server pipeline
  -> local data/local/gen3 only after canonical sync
```

Final gen3.1 state:

- Server repo: `/workspace/sinjeongmin_opal_verifier/repo`.
- Local repo: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`.
- Server run:
  `runs/self_instruct/qwen_local_200_auth_statecheck_gen31_batch4_20260529_132800_KST`.
- Server process: stopped. Former parent `120144`, generator `120148`.
- Server raw at stop: `72 / 1000`.
- Server GPU after stop: `0 %, 0 MiB / 46068 MiB`.
- Local watcher: stopped. Former screen `qwen_incremental_watch_gen31`.
- Local mirror: `runs/self_instruct/server_qwen_prod_gen31`.
- Canonical final export path: server `$RUN/gen_export`, then synced to `data/local/gen3`.
- Local pending export path: `data/local/gen3_pending`.
- Local mirror counts at stop: raw `72`, parse rejects `51`, parsed candidates `21`,
  rule-book accepted `1`, rule-book rejected `20`, pending exported rows `1`.

gen3.1은 gen3보다 나아져 pending accepted row `1`개를 만들었지만, yield가 낮고 reject reason이 구조적으로 반복되어 중단했다. `data/local/gen3_pending`의 1 row는 monitoring artifact일 뿐 training data가 아니다. `data/local/gen3`는 server canonical final export가 없으므로 0 row로 유지한다.

## 현재 도구

<!-- Changed: 현재 pipeline에서 실제 사용하는 코드만 active tool로 정리했다. -->
<!-- Why: runs cleanup 이후에도 어떤 파일이 active인지 명확해야 한다. -->

- Generation/pipeline: `tools/datagen/run_qwen_local_200_pipeline.sh`.
- Incremental watcher: `tools/datagen/watch_qwen_incremental_pull.sh`.
- Request builder/local runner bridge: `tools/datagen/run_self_instruct_generation.py`.
- Parser: `tools/datagen/parse_self_instruct_outputs.py`.
- Candidate schema: `tools/datagen/self_instruct_candidate_schema.py`.
- Final-response invariant gate: `tools/analysis/self_instruct_invariants.py`.
- Dedup gate: `tools/analysis/dedup_self_instruct_candidates.py`.
- Judge payload/filter tooling: `tools/analysis/filter_self_instruct_judge.py`.
- Local judge runner: `tools/analysis/run_self_instruct_judge_local.py`.
- Rule-book quality gate: `tools/analysis/adversarial_rulebook_quality_gate.py`.
- Exporter: `tools/datagen/export_self_instruct_gen_public_schema.py`.
- Rule-book source: `docs/legacy_spec_rules.md`.

## runs 기준

<!-- Changed: runs/에는 current pipeline mirror만 남기는 기준을 명시했다. -->
<!-- Why: 사용자가 runs/에서 현재 생성/검증/watcher 산출물만 남기라고 요청했다. -->

- Stopped `runs/` path kept for evidence: `runs/self_instruct/server_qwen_prod_gen31`.
- Local incremental export는 `data/local/gen3_pending`에 있다.
- `data/local/gen3`는 server full pipeline canonical export를 sync할 때만 채운다.
- Legacy run artifacts는 repo-local archive
  `archive/runs_legacy_20260529_gen3_cleanup/`로 이동한다.
- `server_qwen_prod`, `server_qwen_prod_gen2`, `server_qwen_smokes`, targeted schedules,
  old model-validation, old figures, old public20 baseline run artifacts는 active `runs/`로 복원하지 않는다.

## 검증

<!-- Changed: 현재 data pipeline에 필요한 검증 명령만 남겼다. -->
<!-- Why: cleanup turn에서 full training queue를 다시 시작하지 않는다. -->

```bash
python3 -m py_compile \
  tools/datagen/run_self_instruct_generation.py \
  tools/datagen/parse_self_instruct_outputs.py \
  tools/datagen/export_self_instruct_gen_public_schema.py \
  tools/analysis/adversarial_rulebook_quality_gate.py \
  tools/analysis/filter_self_instruct_judge.py \
  tools/analysis/dedup_self_instruct_candidates.py

bash -n tools/datagen/run_qwen_local_200_pipeline.sh
bash -n tools/datagen/watch_qwen_incremental_pull.sh
git diff --check
```
