# 2026-05-26 10:37:43 KST Manifest v3 Long-shape Enriched Gate 통과

## 결론

[Original Text/Data] 새 run root는 `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1045_KST_manifest_v3_long_shape_enriched`이다.
→ [Exact Interpretation] `/workspace/team6`를 사용하지 않고 새 소유 root에서 생성/검증했다.
→ [Detailed Explanation/Example] repo HEAD는 `01e6450 add public free long shape source generator`로 fast-forward한 뒤 실행했다.

[Original Text/Data] raw source는 `tools/datagen/generate_long_shape_source.py`로 생성했고, public 20 content/label은 쓰지 않았다.
→ [Exact Interpretation] public 20은 shape reference로만 사용했고 supervised row source는 synthetic long trajectory이다.
→ [Detailed Explanation/Example] target record lengths는 public 20의 length multiset을 사용했지만, testcase payload와 label은 학습 row에 포함하지 않았다.

[Original Text/Data] raw summary: count `1155`, label counts `pass=617`, `fail=538`, record_count mean `16.530736`, median `11`, min `2`, max `39`.
→ [Exact Interpretation] public 20 record mean `16.4`와 거의 맞고, label prior는 pass `53.42%`, fail `46.58%`로 50:50 근처이다.
→ [Detailed Explanation/Example] 이전 broken manifest처럼 1-step command나 auxiliary row 중심이 아니다.

[Original Text/Data] raw whitespace token stats: min `33`, median `257`, mean `202.768831`, max `312`; public 20 reference는 min `17`, median `211.5`, mean `211.3`, max `458`.
→ [Exact Interpretation] token density가 public 20과 같은 규모로 들어왔다.
→ [Detailed Explanation/Example] 바로 직전 v2는 token mean `136.43`이라 reference length JSD가 `0.172187`로 실패했지만, v3는 payload enrichment로 해결했다.

## Gate 결과

[Original Text/Data] builder output: selected_records `1154`, overall_gate_passed `True`.
→ [Exact Interpretation] manifest builder hard gate는 통과했다.
→ [Detailed Explanation/Example] duplicate 1개는 build 단계에서 제외되어 최종 manifest exact duplicate gate는 통과했다.

[Original Text/Data] validator with reference output: overall_gate_passed `True`, length_jsd `0.042439`, failed_gates `{}`.
→ [Exact Interpretation] public20 shape reference 대비 length-bin JSD gate `<=0.08`을 통과했다.
→ [Detailed Explanation/Example] shape-only public reference file은 `/workspace/sinjeongmin_opal_verifier/data/reference/shape20_input_reference.jsonl`이다.

[Original Text/Data] manifest split counts: train `791`, calibration `118`, hidden `245`.
→ [Exact Interpretation] train/calibration/hidden split이 생성되었고, 학습은 train split만 사용해야 한다.
→ [Detailed Explanation/Example] split assignment은 builder의 group split 기준을 사용한다.

[Original Text/Data] manifest label counts: pass `617`, fail `537`.
→ [Exact Interpretation] selected manifest prior는 pass `53.47%`, fail `46.53%`이다.
→ [Detailed Explanation/Example] fail oversampling 문제가 있던 이전 방향과 다르게 public 20 prior와 크게 어긋나지 않는다.

[Original Text/Data] trainer dry-run: `Dry-run OK`, tokenized_examples `1`, report `/workspace/sinjeongmin_opal_verifier/ops/runs/20260526_1045_KST_manifest_v3_long_shape_enriched/artifacts/dryrun_manifest_v3_long_shape_enriched.train_report.json`.
→ [Exact Interpretation] trainer가 manifest를 로드하고 tokenize path를 통과했다.
→ [Detailed Explanation/Example] 아직 실제 학습은 시작하지 않았다.

## 제출 판단

[Original Text/Data] 현재는 manifest gate와 dry-run만 통과했고 새 adapter/eval/package가 없다.
→ [Exact Interpretation] leaderboard 제출은 no-go이다.
→ [Detailed Explanation/Example] 제출하려면 이 manifest로 충분히 학습한 adapter 또는 merged/full fine-tuned artifact가 생기고, calibration/hidden metric, package <12GB, first-forward gate를 통과해야 한다.

## 다음 단계

1. GPU 상태와 기존 프로세스 유무를 확인한다.
2. manifest v3 기준 LoRA 학습을 먼저 실행한다.
3. 학습 중 OOM/48GB 활용/batch/epoch/lr를 모니터링한다.
4. adapter 평가 후 full fine-tuning 또는 merged-model packaging을 비교한다.
5. metric gate 통과 전 leaderboard 제출은 하지 않는다.
