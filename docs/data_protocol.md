<!-- Changed: formalize train/leaderboard/test separation. -->
<!-- Why: the user explicitly required strict separation of leaderboard, train, and test data. -->
# 데이터 분리 원칙

## 원천별 역할

`/dl2026/dataset/label.jsonl`과 `/dl2026/dataset/testcases/`는 공개 라벨 데이터다. 이 데이터는
규칙 개발, 스모크 테스트, 공개 검증에만 사용한다.

Leaderboard 결과는 모델 선택에 참고할 수 있지만, 개별 샘플 라벨처럼 역추론해서 규칙에 직접 박으면 안 된다.
제출 로그에는 점수, 제출 시각, 코드 커밋만 남긴다.

Private test 데이터는 공식 평가 시스템 내부에만 존재한다고 가정한다. 로컬 코드, 저장소, 문서에는 private
test의 내용이나 추정 라벨을 기록하지 않는다.

## 구현 정책

현재 solver는 학습 기반 분류기가 아니라 상태 기반 verifier다. 따라서 public 20개 라벨을 외우는 방식이
아니라 다음 순서로 판단한다.

1. JSON trajectory를 command/response event로 정규화한다.
2. 마지막 이전 record들로 session, authentication, activation, write/read 상태를 갱신한다.
3. 마지막 record의 command와 output이 현재 상태에서 가능한지 검사한다.
4. 가능한 응답이면 `pass`, 모순이면 `fail`을 반환한다.

## 금지 사항

- Leaderboard 샘플을 train 데이터로 합치지 않는다.
- Private test 내용을 저장소에 커밋하지 않는다.
- 서버 비밀번호나 GitHub 토큰을 문서, 코드, 커밋 메시지에 남기지 않는다.
- Qwen 같은 대형 모델을 로컬 저장소나 로컬 캐시에 내려받지 않는다. 필요한 경우 서버의 공유 캐시만 사용한다.
