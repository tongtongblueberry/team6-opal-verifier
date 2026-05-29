<!-- Changed: archive the 2026-05-27 active-docs synchronization facts. -->
<!-- Why: active docs were updated to the no-trust/generated-data, 10/10 public20, stopped-server, and cleanup-pending state without deleting files. -->

# 2026-05-27 Active Docs No-Trust Sync

- 시간: 2026-05-27 KST
- 범위: active docs 상태 동기화와 archive 기록 추가
- 삭제: 없음
- runs 수정: 없음

## 기록

1. [Original Text/Data] "기존 generated synthetic data는 전부 no-trust. 학습/accepted sample/final manifest/leaderboard 근거로 사용 금지. 감사/격리/삭제 후보로만 처리." → [Exact Interpretation] 기존 생성 synthetic 산출물은 현재 신뢰 가능한 학습 데이터가 아니다. → [Detailed Explanation/Example] active docs는 과거 v3/v4/v4.1, external probe, gemini batch류 기록을 accepted data가 아니라 audit/quarantine/archive-only evidence로 표기해야 한다.

2. [Original Text/Data] "현재 runs/self_instruct에는 public20_baseline만 있으며 이는 generated synthetic이 아니라 public20 reference evidence다. external_llm_probe/gemini_batch_v2/v3 디렉터리는 현재 runs/self_instruct에 없음. 문서상 과거 결과는 no-go/conditional/archive-only." → [Exact Interpretation] 현재 `runs/self_instruct`의 유효 evidence는 public20 reference 구조 확인용 baseline뿐이다. → [Detailed Explanation/Example] `external_llm_probe`, `gemini_batch_v2`, `gemini_batch_v3`를 larger follow-up 우선순위나 accepted sample 근거로 쓰면 안 된다.

3. [Original Text/Data] "sample 1개는 real raw generation부터 parse/dedup/judge/Gate A/B/C/D/Self-Instruct quality 검증까지 모두 통과한 뒤에만 공개." → [Exact Interpretation] sample 공개 기준은 Gate A/B/C-only가 아니라 전체 생성 및 검증 chain 통과다. → [Detailed Explanation/Example] `docs/samples/self_instruct_sample.md`는 raw generation, parser, dedup, judge, Gate A, Gate B, Gate C, Gate D, quality 검증이 모두 archive evidence로 남은 뒤에만 작성한다.

4. [Original Text/Data] "서버 4B QLoRA queue는 중단됨. GPU 0 MiB/0%. seed11 train ok but logprob fail, seed29 train ok but logprob eval 중 중단. 결과 후보로 쓰지 말 것." → [Exact Interpretation] 중단 queue 산출물은 모델 후보나 leaderboard 근거가 아니다. → [Detailed Explanation/Example] 서버 운영 문서와 current task는 해당 run root를 resume/promotion 대상으로 쓰지 않고, 재시작 전 no-trust 격리와 public20 10/10 split 기준 확인을 요구한다.

5. [Original Text/Data] "public20 모델 검증 split은 10 train / 10 val로 재시작. 기존 16/4 결과는 archive-only." → [Exact Interpretation] active model-validation plan은 `10 train / 10 val`이다. → [Detailed Explanation/Example] 기존 seed 11/29/47 `16 train / 4 val` 산출물은 과거 evidence로만 남기고, 새 학습 후보 설명에는 public20 train 10개 기준을 사용한다.

6. [Original Text/Data] "docs/runs cleanup 분류: active docs/research/spec/public20_baseline/public20_splits는 keep, server_access.md secret-sensitive, public20_trl_sft derived JSONL은 remove-candidate but no delete yet, reports/plans archive." → [Exact Interpretation] cleanup은 문서상 pending이며 파일 삭제 작업이 아니다. → [Detailed Explanation/Example] active docs에는 keep/remove-candidate/archive/secret-sensitive 분류만 기록하고, derived JSONL이나 runs 파일은 이번 sync에서 삭제하지 않는다.

7. [Original Text/Data] "모든 active docs는 서로 같은 상태를 말해야 한다." → [Exact Interpretation] README, PROGRESS, current task, Self-Instruct plan, server ops, samples policy, handoff는 동일한 no-trust/10-10/stopped-queue/sample-gate/cleanup-pending 기준을 공유해야 한다. → [Detailed Explanation/Example] 한 문서가 `Gate A/B/C-only sample` 또는 `larger gemini_batch_v3 priority`를 말하면 다른 active docs와 충돌하므로 no-go/archive-only 기준으로 바꾼다.
