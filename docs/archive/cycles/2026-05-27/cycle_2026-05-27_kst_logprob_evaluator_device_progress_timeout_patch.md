<!-- Changed: archive the logprob evaluator device/progress/timeout patch. -->
<!-- Why: active docs are frozen for this worker, but the queue-revision rationale needs a dated record. -->

# logprob evaluator device/progress/timeout patch

- 작성일: 2026-05-27 KST
- 범위:
  - `tools/eval/eval_trl_sft_public20_generation.py`
  - `tools/eval/eval_trl_sft_public20_logprob.py`
  - `tests/test_eval_trl_sft_public20_generation.py`
  - `tests/test_eval_trl_sft_public20_logprob.py`

## 변경

- `--device-map`, `--torch-dtype`를 공통 model load helper에서
  `AutoModelForCausalLM.from_pretrained(..., **kwargs)`로 얇게 전달한다.
- logprob evaluator에 `--progress-every`를 추가하고, row 완료 progress를 stderr에 flush한다.
- `--timeout-seconds`는 report metadata로만 기록한다. evaluator 내부 signal alarm, hard kill, process kill은 추가하지 않았다.

## 근거

[EXTERNAL KNOWLEDGE] Hugging Face. (2026). *Loading models*. Hugging Face Transformers Documentation.
https://huggingface.co/docs/transformers/main/models

공식 Transformers 문서는 `AutoModelForCausalLM.from_pretrained(..., device_map="auto")` 및 dtype 지정 예시를 제공한다.
이번 변경은 evaluator 자체 device 이동 정책을 새로 만들지 않고 해당 공식 `from_pretrained` kwargs만 노출한다.

## 적용 경계

- 현재 running server queue에는 자동 적용되지 않는다.
- 다음 queue revision 또는 새 evaluator command에서 CLI option을 명시해야 반영된다.
- timeout enforcement는 queue wrapper 책임이다.
