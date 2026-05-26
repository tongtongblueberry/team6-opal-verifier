<!-- Changed: add the public20 official model decision memo. -->
<!-- Why: the model decision lane needs one evidence-based go/no-go record for the five candidate families. -->
# public20 Official Model Decision Memo

- 작성일: 2026-05-26 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 금지 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`
- 범위: public20 official model results 통합, 다음 실행/중단 결정, leaderboard go/no-go 판단.
- 학습 실행: 금지. 이 memo는 기존 결과와 문서 근거만 통합한다.
- 외부 지식: 사용하지 않음.

## Structural Skeleton

1. Ground Truth Inputs
2. Candidate Status
3. Decision
4. Leaderboard Judgment
5. Required Gates Before Any Submission
6. Next Runner Agent Prompt Summary

## Ground Truth Inputs

1. Official full fine-tuning 3-seed result

[Original Text/Data] `docs/current_task.md:51-56` records official TRL full FT seed11/29/47: seed11 acc `0.5`, fail recall `1.0`, pass recall `0.0`; seed29 acc `1.0`, fail/pass recall `1.0/1.0`; seed47 acc `0.75`, fail recall `0.5`, pass recall `1.0`; all are full trainable with PEFT/LoRA disabled. `docs/research/public20_trl_sft_adapter_2026-05-26.md:44-51` records the same table and states seed29 is positive but insufficient for leaderboard because public20 `val` has four rows per split.
→ [Exact Interpretation] Full FT is the strongest current model family, but its cross-seed behavior is inconsistent: seed29 is perfect on its four validation rows, seed11 predicts the fail side only, and seed47 misses one fail case.
→ [Detailed Explanation/Example] The current evidence supports promoting seed29 full FT to an engineering candidate for artifact/package/first-forward checks. It does not support treating the family as validated for leaderboard, because two of three seeds still show class-recall failure modes on tiny validation splits.

2. public20 validation split size

[Original Text/Data] `docs/current_task.md:56` says public20 `val` has four rows per split and high variance. `docs/current_task.md:77-80` says public20-only validation uses public20 `train`/`val`, not `test`; `val` is internal selection/tuning, and hidden leaderboard is the test.
→ [Exact Interpretation] A perfect four-row validation score is a useful signal for candidate selection, not a reliable hidden-test estimate.
→ [Detailed Explanation/Example] seed29 full FT can move forward to package checks because it cleared its local validation split. It cannot justify submission alone because the metric can change sharply when the four held-out public20 examples change.

3. Retrieved-context full FT seed11 result

[Original Text/Data] User-provided result: retrieved full FT seed11 generation acc `0.5`, all predicted fail, same failure pattern as non-retrieved seed11.
→ [Exact Interpretation] Retrieved context did not fix the known seed11 class-collapse pattern.
→ [Detailed Explanation/Example] Because plain seed11 and retrieved seed11 both fail by predicting all validation rows as fail, retrieved context currently adds no decision value. More retrieved-context runs should be held until a stable non-retrieved base checkpoint is selected.

4. LoRA seed results

[Original Text/Data] User-provided result: LoRA seed11 generation/logprob acc `0.75`; LoRA seed29/47 generation acc `0.25` with invalid outputs; logprob improves to `0.5`/`0.75`, but fail recall remains weak. `docs/current_task.md:57-58` and `docs/current_task.md:171-172` classify LoRA seed11/29/47 as lower/unstable supporting evidence, not a replacement or submission basis.
→ [Exact Interpretation] LoRA is not a package candidate now. The gap between generation and logprob plus invalid generations means the output contract is unstable.
→ [Detailed Explanation/Example] A model that improves under logprob scoring but emits invalid generation strings is risky for `src/solver.py` first-forward behavior. This lane should remain diagnostic until generation validity and fail recall are fixed.

5. Candidate set definition

[Original Text/Data] `docs/current_task.md:238` defines five model candidates: `0.9B full FT`, `0.9B full FT + retrieved rulebook/spec context`, `4B LoRA/QLoRA selective FT`, `4B LoRA/QLoRA + retrieved context`, and `RAFT-style retrieval-augmented SFT/QLoRA`.
→ [Exact Interpretation] The decision must rank these five families, not only individual seeds.
→ [Detailed Explanation/Example] The only family with a positive package-candidate artifact is 0.9B full FT seed29. Retrieved-context and LoRA/QLoRA families remain below the package gate based on current evidence.

## Candidate Status

1. `0.9B full FT`

[Original Text/Data] Full FT seed11/29/47 results are acc `0.5`/`1.0`/`0.75`; seed29 has fail/pass recall `1.0/1.0`; seed11 has pass recall `0.0`; seed47 has fail recall `0.5`.
→ [Exact Interpretation] Status: conditional package/first-forward candidate, seed29 only.
→ [Detailed Explanation/Example] Promote the seed29 full FT artifact to package inspection and offline first-forward smoke. Do not generalize the result to the whole full FT recipe until more public20 validation splits or equivalent gates show that seed29 is not a split artifact.

2. `0.9B full FT + retrieved rulebook/spec context`

[Original Text/Data] Retrieved full FT seed11 acc is `0.5`, all fail, same as non-retrieved seed11.
→ [Exact Interpretation] Status: hold.
→ [Detailed Explanation/Example] Retrieval currently duplicates the seed11 failure mode instead of correcting it. Running more retrieved-context seeds before selecting a stable base artifact would spend compute on an unproven dependency.

3. `4B LoRA/QLoRA selective FT`

[Original Text/Data] LoRA seed11 reaches `0.75`, but seed29/47 generation acc is `0.25` with invalids; logprob improves but fail recall remains weak.
→ [Exact Interpretation] Status: diagnostic only, not package candidate.
→ [Detailed Explanation/Example] Invalid generation is a first-forward risk. Weak fail recall also targets the class that matters for verifier rejection behavior. Keep this lane for later controlled comparison, not immediate packaging.

4. `4B LoRA/QLoRA + retrieved context`

[Original Text/Data] No positive retrieved LoRA/QLoRA result is provided, while standalone LoRA generation is unstable and retrieved full FT seed11 does not improve over plain seed11.
→ [Exact Interpretation] Status: not ready; hold behind standalone LoRA stabilization.
→ [Detailed Explanation/Example] Adding retrieval to an unstable generation lane introduces another variable without evidence that retrieval fixes the current failure modes.

5. `RAFT-style retrieval-augmented SFT/QLoRA`

[Original Text/Data] `docs/current_task.md:235` says RAG/full FT/selective FT candidates should proceed after data verification or as parallel support. User-provided current results do not include a RAFT-style public20 validation run.
→ [Exact Interpretation] Status: research/backlog, not execution candidate for immediate package or leaderboard.
→ [Detailed Explanation/Example] RAFT-style training may still be a final direction, but there is no current public20 result that beats seed29 full FT or clears packaging risk.

## Decision

[Original Text/Data] The strongest current artifact-level evidence is full FT seed29 generation acc `1.0` with pass/fail recall `1.0/1.0`; public20 `val` has only four rows per split; retrieved seed11 repeats plain seed11 all-fail behavior; LoRA has invalid generations and weak fail recall.
→ [Exact Interpretation] Next action: treat seed29 full FT as the package/first-forward candidate, hold retrieved-context, and defer broad epoch/LR exploration until seed29 artifact gates are complete.
→ [Detailed Explanation/Example] The immediate next runner should inspect the seed29 full FT artifact, confirm package size, run `check_submit_package.py`, and run offline first-forward smoke. If those gates pass, then run additional public20 split validation or equivalent calibration to measure variance. Do not start with more epoch/LR sweeps because the current blocker is not only model score; it is whether the best-scoring artifact can be packaged and run safely.

## Leaderboard Judgment

[Original Text/Data] `docs/current_task.md:70` says hidden leaderboard is the test. `docs/current_task.md:78` says public20 `val` is internal validation, not test. `docs/current_task.md:274` says leaderboard remains no-go until package `<12GB`, `check_submit_package.py`, and offline first-forward runtime smoke pass. Current user-provided results show high variance across full FT seeds, no retrieved-context improvement, and unstable LoRA generations.
→ [Exact Interpretation] Leaderboard status: no-go.
→ [Detailed Explanation/Example] Submission is blocked by evidence quality and engineering gates. The best seed has only four validation rows; other full FT seeds expose pass/fail recall collapse; retrieved context has no demonstrated benefit; LoRA emits invalids; package size and offline first-forward are not yet confirmed in the provided evidence.

## Required Gates Before Any Submission

1. seed29 full FT artifact gate

[Original Text/Data] `docs/current_task.md:273-274` requires seed29 artifact inspect/calibration/threshold and package/runtime gates before leaderboard.
→ [Exact Interpretation] The seed29 artifact must be inspected as a runnable package candidate before further leaderboard discussion.
→ [Detailed Explanation/Example] Required checks: artifact path exists, no missing tokenizer/model files, package size `<12GB`, package checker passes, offline first-forward smoke returns only valid `pass`/`fail` outputs, and generation/logprob metrics do not contradict the seed29 decision.

2. variance gate

[Original Text/Data] `docs/current_task.md:56` and `docs/current_task.md:79` establish four-row high-variance validation splits.
→ [Exact Interpretation] Additional public20 split validation is required after the seed29 package gate, unless an equivalent hidden-like validation source is created without using public20 test.
→ [Detailed Explanation/Example] The next validation should measure whether full FT retains both pass recall and fail recall across multiple stratified 16/4 splits. This is a split-variance check, not an open-ended LR/epoch sweep.

3. retrieved-context gate

[Original Text/Data] Retrieved seed11 matches plain seed11 all-fail behavior.
→ [Exact Interpretation] Retrieved context is blocked from immediate execution.
→ [Detailed Explanation/Example] Resume retrieved-context only after a stable base checkpoint is selected, then compare matched seeds against the non-retrieved recipe.

## Next Runner Agent Prompt Summary

You are the next package/eval runner for the public20 official model lane. Use only `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`; do not use `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`. Do not print or commit secrets. Do not run new training unless explicitly authorized. Treat full FT seed29 as the only current package/first-forward candidate. First inspect the seed29 artifact, then run package `<12GB`, `tools/eval/check_submit_package.py`, and offline first-forward smoke. If those pass, run additional public20 split/calibration checks; keep leaderboard no-go until those gates are documented. Hold retrieved-context and LoRA/QLoRA lanes unless the seed29 package gate fails or the user explicitly redirects.
