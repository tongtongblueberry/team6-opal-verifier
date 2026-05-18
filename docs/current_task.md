# 현재 진행 중인 작업 (5분마다 업데이트)

최종 갱신: 2026-05-18 ~06:00

## 최상위 목표
leaderboard accuracy 71.50 → ≥ 85.00 (LLM 필수)

## 현재 Cycle: 7 — Retrieval Quality 개선

### 왜 이것을 하는가
1. LLM이 spec을 읽어도 fail recall = 0% (Cycle 1-6)
2. 원인 진단: BM25 retrieval이 **완전히 잘못된 문서**를 가져옴 (Context Recall ≈ 0)
3. RAG 실패의 73%가 retrieval 문제 (Barnett et al., 2024)
4. → query construction을 고쳐서 올바른 spec 문서를 가져오게 해야 함

### 진행 상황
1. [완료] 문제 발견: BM25 query가 "auth False signing False" 같은 내부 용어 → 관련 문서 못 찾음
2. [완료] 문제 metric 조사: RAGAS Context Recall ≥ 0.8 목표
3. [완료] query 수정: object name, UID, method name을 query에 포함
4. [완료] retrieval 재측정: score 8→26, ACL/authentication 관련 문서 검색됨
5. [실행중] 4B 모델로 252건 logit test (서버 nohup)
6. [ ] 결과 확인 → fail recall 개선 여부

### 해결해야 할 추가 문제
- **Train/Test 비율**: 20 train / 252 test는 비정상. 비율 조정 필요.
  - 논문 기준 typical train:test = 80:20 또는 70:30
  - 우리: 20/(20+252) = 7.4% train → 너무 적음
  - 해결: test에서 일부를 train으로 옮기거나, train data augmentation
  - 하지만 public 20개가 유일한 labeled data이므로 더 만들 수 없음
  - → 전문 자료에서 적절한 비율 근거를 찾아야 함

### 서버 작업
- [nohup 실행중] 4B 모델 + improved retrieval + 252건 logit test
  - /workspace/team6/4b_improved.log
  - 예상 ~20분

### 4B + improved retrieval logit 결과
- fail recall = 0% (여전히). Logit scoring은 retrieval/model/few-shot 무관하게 실패.
- **LOGIT MODE 완전 폐기 결정**

### 4B generation + improved retrieval + few-shot 결과
- 15건 (10 pass + 5 fail): acc=66.7%, **fail recall=0%**, 186s/case
- 모든 실험 조합 (logit/gen, bad/good retrieval, 0/20-shot, 4B/27B)에서 fail recall=0%
- **LLM을 근본적으로 잘못 쓰고 있음 확정**

### 근본 원인 재분석 필요
- LLM은 "에러 응답은 valid"라는 strong prior를 가지고 있음
- Few-shot 20개 (10 pass + 10 fail)를 보여줘도 이 prior를 극복 못함
- Spec context를 정확히 제공해도 "fail"이라고 말하지 못함
- → **문제는 retrieval이나 scoring이 아님. LLM의 판단 task 자체의 framing이 잘못됨**

### 다음 Cycle: Task Framing 재설계
- 현재: "이 에러가 valid인가?" (pass/fail) → LLM은 항상 "valid" (pass)
- 대안 1: "이 에러의 원인은 무엇인가?" (open-ended) → LLM에게 원인을 설명하게 하고, 원인이 spec에 없으면 fail
- 대안 2: "이 명령이 성공해야 하는가?" (inverted question) → 성공해야 하는데 에러면 fail
- 대안 3: "spec에 따르면 이 상황에서 올바른 응답은 무엇인가?" (expected response prediction) → 예측과 실제를 비교
- → 논문 조사 필요: task framing이 LLM 정확도에 미치는 영향
