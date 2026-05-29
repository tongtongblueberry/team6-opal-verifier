<!-- Changed: record the official Self-Instruct restart pilot dry-run and provider-env blocker. -->
<!-- Why: this cycle needs an auditable no-key stop record without exposing secrets or promoting dry-run artifacts to accepted data. -->

# 2026-05-27 Self-Instruct Official Restart Dry-Run No-Key Archive

- 기록 시각: 2026-05-27 KST
- run dir: `runs/self_instruct/official_restart_20260527_v1`
- 작업 범위: official Self-Instruct request artifacts 생성, provider env 존재 여부 확인, no-key blocker 기록
- raw sample 공개: no-go
- Gate A/B/C 실행: no-go

## 결과

[Original Text/Data] `run_self_instruct_generation.py`를 request-count `4`, candidates-per-request `3`, provider `openai`, `--execute`로 실행했다.
→ [Exact Interpretation] dry-run request artifacts는 생성됐지만 `OPENAI_API_KEY`가 없어 provider execution은 `skipped_missing_env`로 중단됐다.
→ [Detailed Explanation/Example] `runner_report.json`의 `executed_count`는 `0`이고 `raw_outputs.jsonl`은 생성되지 않았다. 따라서 parser, dedup, judge request, Gate A/B/C는 실행하지 않았다.

[Original Text/Data] provider env status check: `OPENAI_API_KEY=False`, `GEMINI_API_KEY=False`, `GOOGLE_API_KEY=False`, `ANTHROPIC_API_KEY=False`.
→ [Exact Interpretation] 현재 로컬 환경에는 real raw generation에 사용할 provider key가 없다.
→ [Detailed Explanation/Example] secret 값은 출력하거나 저장하지 않았다. 존재 여부만 기록했다.

[Original Text/Data] 생성 artifact:
- `runs/self_instruct/official_restart_20260527_v1/01_generation_requests/generation_requests.jsonl`
- `runs/self_instruct/official_restart_20260527_v1/01_generation_requests/generation_metadata.json`
- `runs/self_instruct/official_restart_20260527_v1/01_generation_requests/machine_generated_instructions.dry_run.jsonl`
- `runs/self_instruct/official_restart_20260527_v1/01_generation_requests/is_clf_or_not_audited_noop.jsonl`
- `runs/self_instruct/official_restart_20260527_v1/02_raw_generation/runner_report.json`
→ [Exact Interpretation] official stages는 instruction generation, classification detection audited no-op, output-first instance generation request, candidate preparation provenance로 metadata에 반영됐다.
→ [Detailed Explanation/Example] candidate preparation은 raw LLM output 이후 parser/candidate schema가 담당하는 stage로만 기록됐고, accepted candidate나 manifest는 만들지 않았다.

[Original Text/Data] 구조 검증 결과: request count `4`, metadata request count `4`, metadata official source `Wang et al. 2023 Self-Instruct`, official code `https://github.com/yizhongw/self-instruct`, license `Apache-2.0`.
→ [Exact Interpretation] request-count는 pilot 범위 `3~5` 안에 있고 official source metadata가 포함됐다.
→ [Detailed Explanation/Example] generated request payload는 input-only seed profile과 `docs/legacy_spec_rules.md` source-span rule card를 사용한다.

[Original Text/Data] source-span card check: all request `payload.spec_rule_context` entries had `source_path == docs/legacy_spec_rules.md` and non-empty `source_span`.
→ [Exact Interpretation] generation request는 source-span card presence 조건을 만족한다.
→ [Detailed Explanation/Example] source-span 없는 candidate를 accepted로 넘기는 후속 단계는 실행되지 않았다.

[Original Text/Data] public label leakage check:
- seed profile label-like fields: `[]`
- grep for `public20_labels`, `data/local/public20/public20_labels`, `labels.local`, `gold_label`, `expected_label`, `label_reference`, `"answer"`: no matches
→ [Exact Interpretation] public20 label file/path or label-like seed fields were not included in generated request artifacts.
→ [Detailed Explanation/Example] request prompt에는 public labels를 사용하지 말라는 prohibition text가 들어가지만, public20 label source itself was not used as generation/judge/manifest target.

[Original Text/Data] `git diff --check` exit code `0`.
→ [Exact Interpretation] tracked diff whitespace check passed.
→ [Detailed Explanation/Example] this run created only run artifacts and this archive record; active docs/code were not intentionally modified by this worker.

## Blocker

[Original Text/Data] no provider API key exists in the current shell environment.
→ [Exact Interpretation] real `raw_outputs.jsonl` generation cannot be executed locally in this run.
→ [Detailed Explanation/Example] Next worker with a provider key should rerun the same request artifact lane or execute the existing `generation_requests.jsonl`, then run parser and dedup. Judge should only be requested after real parsed/deduped candidates exist. Gate A/B/C must remain blocked until judge-accepted real candidates exist.
