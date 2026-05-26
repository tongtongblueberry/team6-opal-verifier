# Gate A/B/C Preflight - active synthetic 후보 없음

<!-- Changed: Gate A/B/C preflight note를 추가한다. -->
<!-- Why: raw synthetic 후보가 생겼을 때 실행할 검증 순서와 no-go 조건을 코드 변경 없이 고정하기 위해서다. -->

## 현재 상태

- 기준 시각: 2026-05-26 KST
- inventory 전제: Gate 대상 active synthetic candidate 없음
- public20 역할: 검증 대상이 아니라 reference/profile 및 모델 train/val 기준
- Gate 검증 대상: synthetic 데이터만
- runtime rule engine: 금지
- offline invariant/data-quality check: 허용
- `sample.md`: Gate A/B/C 통과 전 생성 금지

## 확인된 기존 artifact 위치

- Gate A public20 reference baseline:
  - `runs/self_instruct/public20_baseline/gate_a/public20_reference_audit_report.md`
  - `runs/self_instruct/public20_baseline/gate_a/public20_reference_audit_report.json`
  - `runs/self_instruct/public20_baseline/gate_a/public20_reference_audit_pack.md`
- Gate B public20 profile baseline:
  - `runs/self_instruct/public20_baseline/gate_b/public20.profile.json`
  - `runs/self_instruct/public20_baseline/gate_b/public20.normalized.jsonl`
  - `runs/self_instruct/public20_baseline/gate_b/public20_raw_format_profile.json`
  - `runs/self_instruct/public20_baseline/gate_b/public20_label_distribution.local.json`
  - `runs/self_instruct/public20_baseline/gate_b/public20_profile_verification_report.md`
  - `runs/self_instruct/public20_baseline/gate_b/public20_profile_verification_report.json`

## 확인된 기존 도구

- raw output parser:
  - `tools/datagen/parse_self_instruct_outputs.py`
- candidate schema/profile:
  - `tools/datagen/self_instruct_candidate_schema.py`
- dedup/public20 duplicate filter:
  - `tools/analysis/dedup_self_instruct_candidates.py`
- final-response invariant:
  - `tools/analysis/self_instruct_invariants.py`
- offline judge request/result filter:
  - `tools/analysis/filter_self_instruct_judge.py`
- Gate A qualitative audit pack:
  - `tools/analysis/audit_self_instruct_quality.py`
- Gate B dimension comparison:
  - `tools/analysis/compare_public20_dimensions.py`
- supervised manifest build/validate:
  - `tools/analysis/build_supervised_manifest.py`
  - `tools/analysis/validate_manifest.py`
- Gate C manifest/model input equivalence:
  - `tools/analysis/check_manifest_model_input_equivalence.py`

## raw candidate 발생 시 실행 순서

아래 예시는 `RUN_ID=<candidate_run_id>`를 사용한다. raw 출력은 긴 원문을 report에 복사하지 않는다.

```bash
RUN_ID=<candidate_run_id>
RAW_JSONL=runs/self_instruct/${RUN_ID}/raw/candidates.raw.jsonl
OUT_DIR=runs/self_instruct/${RUN_ID}
PUBLIC20_PROFILE=runs/self_instruct/public20_baseline/gate_b/public20.profile.json
PUBLIC20_NORMALIZED=runs/self_instruct/public20_baseline/gate_b/public20.normalized.jsonl
PUBLIC20_LABEL_DIST=runs/self_instruct/public20_baseline/gate_b/public20_label_distribution.local.json
```

1. raw output parse/normalize:

```bash
python tools/datagen/parse_self_instruct_outputs.py \
  --input "$RAW_JSONL" \
  --output "$OUT_DIR/normalized/candidates.normalized.jsonl" \
  --reject-output "$OUT_DIR/normalized/candidates.parse_rejects.jsonl" \
  --report-json "$OUT_DIR/normalized/parse_report.json" \
  --profile-output "$OUT_DIR/normalized/candidates.profile.json"
```

2. public20 exact/near duplicate 및 intra-candidate conflict filter:

```bash
python tools/analysis/dedup_self_instruct_candidates.py \
  --input "$OUT_DIR/normalized/candidates.normalized.jsonl" \
  --output "$OUT_DIR/filtered/candidates.dedup.jsonl" \
  --reject-output "$OUT_DIR/filtered/candidates.dedup_rejects.jsonl" \
  --report-json "$OUT_DIR/filtered/dedup_report.json" \
  --public20-reference-jsonl "$PUBLIC20_NORMALIZED" \
  --rouge-l-threshold 0.7
```

3. final-response hard invariant 재확인:

```bash
python tools/analysis/self_instruct_invariants.py \
  "$OUT_DIR/filtered/candidates.dedup.jsonl" \
  --output-jsonl "$OUT_DIR/gate_a/final_response_invariants.jsonl"
```

4. offline judge request 생성:

```bash
python tools/analysis/filter_self_instruct_judge.py \
  --candidates "$OUT_DIR/filtered/candidates.dedup.jsonl" \
  --requests-output "$OUT_DIR/judge/judge_requests.jsonl" \
  --metadata-json "$OUT_DIR/judge/judge_metadata.json" \
  --model external-llm
```

5. 외부 judge 결과가 생긴 뒤 result filter 적용:

```bash
python tools/analysis/filter_self_instruct_judge.py \
  --candidates "$OUT_DIR/filtered/candidates.dedup.jsonl" \
  --requests-output "$OUT_DIR/judge/judge_requests.jsonl" \
  --metadata-json "$OUT_DIR/judge/judge_metadata.json" \
  --judge-results "$OUT_DIR/judge/judge_results.raw.jsonl" \
  --accepted-output "$OUT_DIR/judge/candidates.judge_accepted.jsonl" \
  --reject-output "$OUT_DIR/judge/candidates.judge_rejects.jsonl" \
  --decisions-output "$OUT_DIR/judge/judge_decisions.json" \
  --report-json "$OUT_DIR/judge/judge_filter_report.json" \
  --model external-llm
```

6. Gate A qualitative state-transition audit pack 생성:

```bash
python tools/analysis/audit_self_instruct_quality.py \
  --accepted-jsonl "$OUT_DIR/judge/candidates.judge_accepted.jsonl" \
  --sample-size 20 \
  --seed 42 \
  --invariant-jsonl "$OUT_DIR/gate_a/gate_a_invariants.jsonl" \
  --audit-pack-md "$OUT_DIR/gate_a/gate_a_audit_pack.md" \
  --audit-report-json "$OUT_DIR/gate_a/gate_a_audit_report.json" \
  --audit-report-md "$OUT_DIR/gate_a/gate_a_audit_report.md"
```

Gate A는 pack의 label별 sample을 처음부터 끝까지 읽고 session/auth/object/value state transition을 추적해 통과 여부를 별도 기록해야 한다. 중간 fail 뒤 final `EndSession/SUCCESS`인데 label이 `fail`인 경우는 reject다.

7. Gate B public20 dimension/profile 비교:

```bash
python tools/datagen/self_instruct_candidate_schema.py \
  --input "$OUT_DIR/judge/candidates.judge_accepted.jsonl" \
  --output "$OUT_DIR/gate_b/candidates.gate_b.normalized.jsonl" \
  --profile-output "$OUT_DIR/gate_b/candidates.gate_b.profile.json"

python tools/analysis/compare_public20_dimensions.py \
  --public-profile "$PUBLIC20_PROFILE" \
  --generated-profile "$OUT_DIR/gate_b/candidates.gate_b.profile.json" \
  --public-label-distribution "$PUBLIC20_LABEL_DIST" \
  --output-json "$OUT_DIR/gate_b/gate_b_dimension_comparison.json" \
  --output-md "$OUT_DIR/gate_b/gate_b_dimension_comparison.md"
```

8. Gate A/B 통과 후에만 supervised manifest 후보 생성:

```bash
python tools/analysis/build_supervised_manifest.py \
  --input "$OUT_DIR/judge/candidates.judge_accepted.jsonl" \
  --output "$OUT_DIR/manifest/synthetic_manifest.jsonl" \
  --report-out "$OUT_DIR/manifest/synthetic_manifest_build_report" \
  --hidden-fraction 0.2 \
  --calibration-fraction 0.1 \
  --seed 42 \
  --length-balance-reference "$PUBLIC20_NORMALIZED"
```

9. manifest hard gate:

```bash
python tools/analysis/validate_manifest.py \
  --manifest "$OUT_DIR/manifest/synthetic_manifest.jsonl" \
  --reference "$PUBLIC20_NORMALIZED" \
  --report-out "$OUT_DIR/manifest/synthetic_manifest_validate_report"
```

10. Gate C full trajectory equivalence:

```bash
python tools/analysis/check_manifest_model_input_equivalence.py \
  --candidates-jsonl "$OUT_DIR/judge/candidates.judge_accepted.jsonl" \
  --manifest-jsonl "$OUT_DIR/manifest/synthetic_manifest.jsonl" \
  --output-json "$OUT_DIR/gate_c/gate_c_manifest_model_input_equivalence.json" \
  --output-md "$OUT_DIR/gate_c/gate_c_manifest_model_input_equivalence.md"
```

## sample.md 생성 조건

`sample.md`는 다음 조건이 모두 참일 때만 생성한다.

- active synthetic raw candidate가 존재한다.
- raw synthetic -> normalized candidate 변환이 성공했다.
- duplicate/conflict/public20 exact/near duplicate filter를 통과했다.
- offline judge accepted candidate가 존재한다.
- Gate A qualitative state-transition audit가 통과했다.
- Gate B public20 reference profile 비교가 no-go 없이 통과했다.
- manifest build와 validate hard gate가 통과했다.
- Gate C에서 candidate/manifest/training loader/model input path가 같은 full trajectory 단위임을 확인했다.

통과 후에만 generated raw full trajectory와 public20 full sample을 제한적으로 보여준다.
