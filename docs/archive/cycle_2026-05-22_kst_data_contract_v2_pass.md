<!-- 변경: Data Contract v2 통과 결과를 KST 기준으로 신규 아카이빙. 이유: 다음 학습/제출 판단의 근거 run, gate, no-go 조건을 재현 가능하게 남기기 위함. -->
# Cycle 기록: Data Contract v2 통과 및 학습 진입 조건

기록 시각: 2026-05-22 16:57:38 KST

## 결정 요약

Data Contract v2 manifest gate는 통과했다.

- run root: `/workspace/team6/ops/runs/20260522_164328_KST`
- manifest: `/workspace/team6/ops/runs/20260522_164328_KST/manifests/canonical_supervised_manifest.jsonl`
- build overall: 통과
- validate overall: 통과
- selected records: 480
- reference parse errors: 0
- length JSD: 0.006999
- public/eval holdout metadata hits: 0
- rule-context metadata/input hits: 0

오늘 leaderboard 제출은 아직 no-go이다. 이유는 새 manifest가 통과했지만, 이 manifest로 학습한 새 LLM-only adapter와 hidden-like 검증 결과가 아직 없기 때문이다.

## [Original Text/Data] → [Exact Interpretation] → [Detailed Explanation/Example]

1. [Original Text/Data] `build_overall=true`, `validate_overall=true` → [Exact Interpretation] 현재 canonical manifest는 Data Contract v2 hard gate를 통과했다. → [Detailed Explanation/Example] 이 결과는 학습 진입 조건 중 데이터 gate에 해당하며, leaderboard 제출 조건 전체를 의미하지 않는다.

2. [Original Text/Data] `selected_records=480` → [Exact Interpretation] rule/public/blocklist/unknown/dedupe 제거 후 supervised 학습 후보는 480개이다. → [Detailed Explanation/Example] train/calibration/hidden split은 이 480개 안에서만 사용해야 하며, raw 381086개를 직접 학습 입력으로 쓰면 안 된다.

3. [Original Text/Data] `excluded_by_reason={"blocklisted":116915,"duplicate":449,"public_holdout":284,"rule_context":2646,"unknown_label":260312}` → [Exact Interpretation] public/eval holdout 후보와 rule-context 후보가 build 단계에서 제외되었다. → [Detailed Explanation/Example] `public_holdout=284`와 `rule_context=2646`은 LLM-only 데이터 계약 때문에 학습에서 배제된 수량이다.

4. [Original Text/Data] `reference_parse_errors=0`, `reference_skipped_files=10`, `reference_skipped_records=1466784` → [Exact Interpretation] eligible reference corpus에는 parse error가 없고, score/report/checkpoint 계열 auxiliary artifact는 reference 분포 계산에서 제외되었다. → [Detailed Explanation/Example] auxiliary skip은 오류 완화가 아니라 corpus와 산출물 파일을 분리한 기록이다.

5. [Original Text/Data] `length_jsd=0.006999 <= 0.08` → [Exact Interpretation] manifest length distribution은 reference eligible corpus 목표를 통과했다. → [Detailed Explanation/Example] build와 validate가 같은 compact JSON text 기준으로 reference length bin을 계산하도록 맞춘 뒤 통과했다.

6. [Original Text/Data] `public_holdout_metadata_absent passed`, `rule_context_metadata_or_input_absent passed` → [Exact Interpretation] 완성된 manifest에는 public/eval holdout metadata나 rule-context metadata/input 흔적이 없다. → [Detailed Explanation/Example] 이것은 manifest row 기준 검증이며, public 20의 확정 ID/hash blocklist가 없는 한 “증명 가능한 완전 차단”은 별도 과제로 남는다.

## 다음 실행 결정

학습으로 진입한다. 단, 기존 `train_wd.py`, `train_replicate_best.py`, `run_full_pipeline.sh`, `train_uncertainty_resolver.py`는 사용하지 않는다.

필수 조건:

- Data Contract v2 manifest의 `split == "train"`만 학습에 사용한다.
- `calibration`과 `hidden` split은 학습에 사용하지 않는다.
- rule engine, `StatefulOpalVerifier`, public 20 eval, `/dl2026/dataset` label/testcase path를 trainer에서 호출하지 않는다.
- 산출물은 repo 내부 `artifacts/`가 아니라 `/workspace/team6/ops/runs/20260522_164328_KST/adapters/...` 아래에만 저장한다.
- `nohup`으로 실행하고 pid/log를 run root 아래에 남긴다.
- 중단 후 `--resume`으로 최신 checkpoint 재개가 가능해야 한다.

1차 학습 설정:

- base model: `Qwen/Qwen3.5-4B`
- LoRA: `r=16`, `alpha=32`, `dropout=0.1`, target `q_proj,k_proj,v_proj,o_proj`
- max sequence length: 2048
- epochs: 5
- per-device batch size: 1
- gradient accumulation: 8
- learning rate: 1e-3
- weight decay: 0.05
- label smoothing: 0.1
- precision: fp16
- gradient checkpointing: enabled

## Leaderboard 제출 판정

현재 제출 no-go.

제출 가능 조건:

- 위 manifest 기반 새 LLM-only adapter 학습 완료
- 학습 로그에 epoch/lr/loss/GPU memory 기록 존재
- calibration/hidden-like 평가가 기존 hidden 73.00을 넘길 논리적 근거 제시
- public 20 직접학습/직접평가를 제출 근거로 사용하지 않음
- 제출 전 “기존 leaderboard 결과와 무엇이 달라졌는지” 별도 기록
- 제출 후 KST 기준 md 아카이브 작성
