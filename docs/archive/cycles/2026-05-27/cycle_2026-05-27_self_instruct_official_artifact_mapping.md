<!-- Changed: archive the official Self-Instruct artifact mapping implemented in the dry-run tools. -->
<!-- Why: future workers must distinguish official-stage request artifacts from accepted synthetic data. -->

# 2026-05-27 Self-Instruct Official Artifact Mapping

- 작성일: 2026-05-27 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 범위: LLM 호출 없는 dry-run request/metadata, parser schema, dedup report, judge request provenance.

## 공식 코드 확인

<!-- Changed: record the local official-code files read for this implementation pass. -->
<!-- Why: the mapping must be traceable to the official repository layout without vendoring code. -->

- `/tmp/self-instruct-official-current/self_instruct/bootstrap_instructions.py`
  - 공식 `machine_generated_instructions.jsonl` 생성 단계.
- `/tmp/self-instruct-official-current/self_instruct/identify_clf_or_not.py`
  - 공식 `is_clf_or_not_<engine>_<template>.jsonl` 생성 단계.
- `/tmp/self-instruct-official-current/self_instruct/generate_instances.py`
  - 공식 `machine_generated_instances.jsonl` 생성 단계.
- `/tmp/self-instruct-official-current/self_instruct/prepare_for_finetuning.py`
  - 공식 generated instances를 finetuning row로 파싱/필터링하는 단계.
- `/tmp/self-instruct-official-current/self_instruct/templates/*`
  - classification 판정 template와 output-first classification instance template.
- `/tmp/self-instruct-official-current/scripts/*`
  - 위 네 단계를 순서대로 실행하는 shell wrapper.

## 우리 dry-run artifact 대응

<!-- Changed: separate each official stage in local metadata instead of calling one fixed prompt official Self-Instruct. -->
<!-- Why: fixed Opal instruction plus trajectory candidates is not, by itself, the full official Self-Instruct pipeline. -->

- Instruction generation
  - 공식 대응: `machine_generated_instructions.jsonl`.
  - local 대응: `self_instruct.machine_generated_instructions.dry_run.v1`.
  - 상태: LLM-generated instruction이 아니라 dry-run provenance artifact다.

- Classification detection
  - 공식 대응: `is_clf_or_not_<engine>_<template>.jsonl`.
  - local 대응: `self_instruct.is_clf_or_not.audited_noop.v1`.
  - 상태: Opal pass/fail domain은 classification이므로 `is_classification=true` audited no-op artifact로 남긴다.

- Output-first instance generation
  - 공식 대응: `machine_generated_instances.jsonl`.
  - local 대응: `self_instruct.generation_request.v1`.
  - 상태: request payload만 작성한다. 실제 LLM 호출과 sample 생성은 하지 않는다.

- Candidate/finetuning preparation
  - 공식 대응: `prepare_for_finetuning.py` output.
  - local 대응: `parse_self_instruct_outputs.py`와 `self_instruct_candidate_schema.py`.
  - 상태: raw external output을 candidate schema로 normalize/reject한다. training-ready split 선언은 Gate A/B/C/D 이후다.

## 구현 메모

<!-- Changed: summarize the exact local contract changes. -->
<!-- Why: downstream workers need the migration and report semantics before running real generation. -->

- candidate에는 `source_instruction_id`가 필수다.
- backward-compatible parser migration은 old raw wrapper에 `source_instruction_id`가 없고 `request_id`만 있을 때 `legacy-migrated:<request_id>`를 붙인다. 이 경로는 parser wiring compatibility일 뿐 accepted synthetic 승격 근거가 아니다.
- dedup report는 `instruction_level_rouge_l`, `trajectory_level_duplicate`, `public20_reference_overlap`, `schema_validation` stage count를 분리한다.
- judge request payload는 candidate trajectory, generated label, `spec_grounding`, `source_instruction_id`, classification detection provenance를 함께 포함한다.
- mock fixture는 wiring 검증 전용이며 accepted synthetic data가 아니다.

## 남은 gap

<!-- Changed: keep non-implemented pieces explicit. -->
<!-- Why: dry-run/schema success must not be mistaken for generated-data acceptance. -->

- real LLM generation raw output 없음.
- human Gate A state-transition audit 없음.
- Gate B public20 comparison, Gate C manifest/model input equivalence, Gate D submission 판단 없음.
- Gate A/B/C/D 통과 sample publication 없음.
