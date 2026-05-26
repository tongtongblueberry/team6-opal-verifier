<!-- Changed: update to reflect current architecture (rule engine + LoRA override, not RAG hybrid). -->
<!-- Why: architecture evolved from RAG hybrid to rule engine (71.50) + LoRA override. -->
# 데이터 분리 원칙

## 원천별 역할

`/dl2026/dataset/label.jsonl`과 `/dl2026/dataset/testcases/`는 공개 라벨 데이터다. 이 데이터는
규칙 개발, 스모크 테스트, 공개 검증에만 사용한다.

Leaderboard 결과는 모델 선택에 참고할 수 있지만, 개별 샘플 라벨처럼 역추론해서 규칙에 직접 박으면 안 된다.
제출 로그에는 점수, 제출 시각, 코드 커밋만 남긴다.

Private test 데이터는 공식 평가 시스템 내부에만 존재한다고 가정한다. 로컬 코드, 저장소, 문서에는 private
test의 내용이나 추정 라벨을 기록하지 않는다.

## 구현 정책

현재 solver는 **Rule Engine (71.50 base) + LoRA Override**다.

1. JSON trajectory를 command/response event로 정규화한다.
2. 마지막 이전 record들로 session, authentication, activation, write/read 상태를 갱신한다.
3. 마지막 record의 command와 output이 현재 상태에서 가능한지 검사한다.
4. Rule engine이 specific rule로 판정하면: 그 판정을 그대로 사용한다.
5. Rule engine이 `UNEXPECTED_ERROR_STATUS`로 fail 판정하면: LoRA 4B adapter가 override 여부를 결정한다.
6. LoRA가 pass로 판정하면 override (false positive rescue), fail이면 유지.
7. 최종 prediction을 반환한다.

LoRA adapter는 rule engine이 생성한 2163건의 synthetic training data로 학습되었다.
Public 라벨을 직접 학습하지 않으며, rule engine의 판단을 보조하는 역할이다.

## 금지 사항

- Leaderboard 샘플을 train 데이터로 합치지 않는다.
- Private test 내용을 저장소에 커밋하지 않는다.
- 서버 비밀번호나 GitHub 토큰을 문서, 코드, 커밋 메시지에 남기지 않는다.
- Qwen 같은 대형 모델을 로컬 저장소나 로컬 캐시에 내려받지 않는다. 서버의 캐시만 사용한다.
- LLM의 판정에 공개 라벨 정보를 주입하지 않는다 (few-shot으로 정답을 보여주지 않음).
