<!-- Changed: update approach to reflect current architecture (rule engine + LoRA override). -->
<!-- Why: architecture evolved from RAG hybrid to rule engine (71.50 UNEXPECTED_ERROR_STATUS) + LoRA 4B override. -->
# 접근 방식 요약

## 결론

이 문제는 전체 trajectory가 주어지므로 순수 분류 AI가 필수인 문제는 아니다. 핵심은 TCG/Opal 명령이
상태 의존적이라는 점이다. 같은 마지막 응답이라도 이전 `StartSession`, `Set`, `Activate`, `GenKey`,
`Write` 이력에 따라 맞을 수도 있고 틀릴 수도 있다.

Team 6의 접근은 **Rule Engine (71.50 base) + LoRA Override**다:
- **Rule engine**: deterministic state verifier가 모든 case를 판정. `UNEXPECTED_ERROR_STATUS`로 unexplained error를 aggressive하게 fail 처리 (이것이 71.50의 핵심)
- **LoRA 4B override**: `UNEXPECTED_ERROR_STATUS` false positive를 감지하여 pass로 rescue

## 아키텍처 변천

1. **Pure rule engine** (Cycle 1-10): 60.50 -> 71.50. UNEXPECTED_ERROR_STATUS가 결정적.
2. **RAG hybrid** (Cycle 1-6 LLM): BM25 + Qwen3.5-27B-FP8. Fail recall 0% (logit), 시간 초과 (generation). **폐기.**
3. **Embedding classifier** (Cycle 10): Ridge regression on 9B embeddings. Leaderboard 68.00 regression. **폐기.**
4. **LoRA 4B v2 override** (Cycle 12-15, 현재): Rich format + label masking. Fail precision 100%, recall 46.9%.

## 런타임 구조

`src/solver.py::Solver.predict(dataset)`는 다음 단계를 수행한다.

1. `StatefulOpalVerifier.verify_with_trace(steps)`로 rule engine을 실행한다.
   - command와 response JSON에서 method, invoking UID, status, session id, challenge, payload를 추출한다.
   - 마지막 record 이전까지 protocol state를 갱신한다.
   - 마지막 record에서 expected error와 actual status/payload를 비교한다.
   - trace에 어떤 rule이 적용되었는지 기록한다.
2. 마지막 trace의 `rule_id`를 확인한다.
   - specific rule (e.g., `STARTSESSION_FINAL`, `GET_PAYLOAD`): 그 판정을 그대로 사용한다.
   - `UNEXPECTED_ERROR_STATUS`: LoRA override로 넘긴다.
3. LoRA override (`src/lora_solver.py`):
   - Qwen3.5-4B + LoRA adapter가 trajectory를 rich format으로 변환하여 판정한다.
   - LoRA가 "pass"를 예측하면 -> rule engine의 fail을 pass로 override (false positive rescue)
   - LoRA가 "fail"을 예측하면 -> rule engine의 fail을 유지
4. 최종 prediction을 반환한다.

[EXTERNAL KNOWLEDGE] Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., & Chen, W. (2022). *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR 2022. https://arxiv.org/abs/2106.09685

## 왜 이 방식인가

1. **Rule engine alone**: 순수 rule engine은 public 20/20, leaderboard 71.50까지 도달했지만 plateau.
   `UNEXPECTED_ERROR_STATUS`가 hidden test에서 효과적이나 일부 false positive가 있음.

2. **RAG+LLM alone**: Zero-shot logit scoring은 fail recall 0%. Generation mode는 13분/case로 3시간 초과.
   Few-shot ICL도 logit mode에서 효과 없음. LLM의 zero-shot spec reasoning 능력이 부족하여 폐기.

3. **LoRA override**: Rule engine의 aggressive fail (UNEXPECTED_ERROR_STATUS)을 base로 두고,
   LoRA fine-tuned model이 false positive만 rescue. False positive 0건 (synthetic), fail recall 46.9%.
   이 조합이 regression 없이 점수 향상 가능성이 가장 높다.

## 서버 요구사항

- GPU: NVIDIA L40S 48GB VRAM (4B LoRA adapter ~14GB, 여유 충분)
- 모델: Qwen3.5-4B + LoRA adapter (artifacts/lora_adapter_v2/, ~32MB)
- Spec 문서: `/dl2026/skeleton/artifacts/documents/` (500+ .txt files)
- 로컬에서는 LoRA 비활성화, 순수 rule engine으로 동작
