<!-- Changed: external-method survey for choosing the Team 6 methodology. -->
<!-- Why: we need to separate train/leaderboard/test data and understand how related work actually trains or avoids training. -->

> **NOTE: This document reflects an earlier project phase (Cycle 1-3).** The RAG hybrid architecture
> described here was subsequently abandoned (fail recall 0%). Current architecture is Rule Engine
> (71.50 UNEXPECTED_ERROR_STATUS) + LoRA 4B override. See `PROGRESS.md` for current state.
> The methodology survey content below remains valid as historical reference for architectural decisions.

# 관련 방법론 조사: 학습, fine-tuning, 상태 추적, 명세 활용

작성일: 2026-05-17

## 결론

현재 SSD TCG/Opal verifier 문제는 공개 라벨이 20개뿐이고, 입력 trajectory 전체가 주어진다. 따라서
DeepLog/LogBERT/LogGPT류처럼 public labels를 사용해 classifier를 학습하는 접근은 우선순위가 낮다.
더 가까운 계열은 RESTler/AFLNet/StateAFL/ChatAFL 쪽의 "상태 기반 protocol reasoning"이다.

**2026-05-18 업데이트**: 순수 rule engine이 71.50에서 plateau한 후, confidence-gated hybrid로 전환했다.
확신이 높은 case는 rule engine이 직접 판정하고, 확신이 낮은 case (`DEFAULT_PASS`)는 RAG (BM25 over
spec chunks) + LLM (Qwen3.5-27B-FP8)이 판정한다. 이것은 Lewis et al. (2020)의 Retrieval-Augmented
Generation 아키텍처를 적용한 것이다. LLM은 spec 원문을 직접 읽고 판단하므로 supervised fine-tuning이
아니며, 공개 라벨에 의존하지 않는다.

우리에게 필요한 것은 다음 구조다.

1. JSON command/response를 canonical event로 변환한다.
2. 마지막 record 이전까지 session/auth/SP/locking/key/data 상태를 추적한다.
3. 마지막 record 판단에 사용된 state 변수와 spec 근거를 trace로 남긴다.
4. 확신이 높은 case는 rule engine이 직접 판정한다.
5. 확신이 낮은 case는 RAG+LLM이 spec chunk를 검색하고 pass/fail을 판정한다.

## 조사 대상 분류

| 계열 | 대표 방법 | 학습/fine-tuning 방식 | 우리 문제 적용성 |
|---|---|---:|---|
| 로그 이상탐지 | DeepLog, LogAnomaly, LogBERT, LogGPT | 정상 sequence 학습, self-supervised, 일부 RL fine-tuning | 공개 데이터가 매우 작아 직접 적용 위험 |
| 상태 기반 API/protocol fuzzing | RESTler, AFLNet, StateAFL | 대부분 모델 학습 없음. spec, seed, response/state feedback 사용 | 매우 높음 |
| LLM-guided protocol fuzzing | ChatAFL, StatePre | 모델 weight fine-tuning이 아니라 prompt/RFC/code 분석 | 높음. LLM은 보조 도구로 적합 |

## 1. DeepLog

[EXTERNAL KNOWLEDGE] Du, M., Li, F., Zheng, G., & Srikumar, V. (2017). *DeepLog: Anomaly detection and diagnosis from system logs through deep learning*. Proceedings of the 2017 ACM SIGSAC Conference on Computer and Communications Security, 1285-1298. https://www2.cs.utah.edu/~lifeifei/papers/deeplog.pdf

[Original Text/Data] → DeepLog는 정상 실행 로그만으로 LSTM을 학습하고, 최근 `h`개 log key로 다음 log key의 확률분포를 예측한다. 실제 다음 key가 top `g` 후보 안에 없으면 anomaly로 본다. 논문은 정상 로그만으로 학습한다고 설명하고, `h`, `g`, layer 수, memory unit 수를 주요 parameter로 평가한다.

[Exact Interpretation] → DeepLog의 학습은 binary classifier가 아니다. 정상 sequence language model을 만든 뒤, 예측 가능한 정상 흐름에서 벗어나는지를 본다.

[Detailed Explanation/Example] → 로그를 parser로 `k22, k5, k11, k9, ...` 같은 token sequence로 바꾼다. `h=3`이면 `(k22,k5,k11)->k9`, `(k5,k11,k9)->k11` 같은 training pair를 만든다. 추론 때 `(k22,k5,k11)` 다음 실제 key가 모델의 top `g` 안에 있으면 정상, 없으면 이상이다.

우리 문제에 그대로 적용하기 어려운 이유:

- public labeled trajectory가 20개뿐이다.
- DeepLog는 "정상 실행 sequence가 충분히 많다"는 전제가 필요하다.
- SSD/Opal 문제의 fail은 단순히 드문 sequence가 아니라 "명세와 상태에 어긋나는 final response"다.
- `top-g` 같은 threshold는 leaderboard를 보고 맞추기 시작하면 데이터 누수 위험이 있다.

적용 가능한 아이디어:

- sliding window/receptive field 개념은 쓸 수 있다.
- 각 판단이 "직전 몇 step"만 보는지, "전체 state"를 보는지 trace로 남겨야 한다.
- W&B sweep을 한다면 `h`, `g`가 아니라 rule threshold, parser option, spec retrieval option을 sweep해야 한다.

## 2. LogAnomaly

[EXTERNAL KNOWLEDGE] Meng, W., Liu, Y., Zhu, Y., Zhang, S., Pei, D., Liu, Y., Chen, Y., Zhang, R., Tao, S., Sun, P., & Zhou, R. (2019). *LogAnomaly: Unsupervised detection of sequential and quantitative anomalies in unstructured logs*. Proceedings of the Twenty-Eighth International Joint Conference on Artificial Intelligence, 4739-4745. https://www.ijcai.org/proceedings/2019/658

[Original Text/Data] → LogAnomaly는 FT-Tree로 template를 추출하고, template2Vec으로 template semantics를 벡터화한 뒤 LSTM으로 sequential pattern과 quantitative count pattern을 함께 학습한다. 논문은 HDFS/BGL에서 timestamp 기준 앞 80%를 train, 뒤 20%를 test로 사용했다.

[Exact Interpretation] → LogAnomaly는 DeepLog의 약점인 "template id만 보면 의미가 비슷한 새 template를 오탐할 수 있음"을 semantic vector와 template approximation으로 줄이려 한다.

[Detailed Explanation/Example] → `link down`, `link up`처럼 단어가 비슷해도 의미는 반대일 수 있다. LogAnomaly는 synonym/antonym 정보를 써서 template vector를 만들고, 새 template가 생겨도 기존 template vector와의 유사도로 매칭한다.

우리 문제에 그대로 적용하기 어려운 이유:

- SSD command JSON은 자연어 로그 template라기보다 구조화 protocol event다.
- template2Vec보다 UID, method, authority, SP, status, payload를 정확히 parse하는 것이 우선이다.
- public sample 수가 작아 LSTM 학습이 안정적이지 않다.

적용 가능한 아이디어:

- "새 template approximation"은 hidden testcase의 JSON 표현 차이를 흡수하는 canonicalizer로 바꿔 적용한다.
- sequential anomaly와 quantitative anomaly를 나누듯, 우리도 `state legality`, `response payload consistency`, `status code legality`를 분리해야 한다.

## 3. LogBERT

[EXTERNAL KNOWLEDGE] Guo, H., Yuan, S., & Wu, X. (2021). *LogBERT: Log anomaly detection via BERT*. arXiv. https://arxiv.org/abs/2103.04475

[Original Text/Data] → LogBERT는 정상 log sequence만 사용해 Transformer encoder를 self-supervised로 학습한다. 학습 task는 masked log key prediction과 hypersphere minimization이다. 논문은 HDFS/BGL/Thunderbird 각각에서 약 5000개 정상 sequence를 train에 사용하고, mask ratio와 top candidate 크기 등을 validation set으로 조정했다.

[Exact Interpretation] → LogBERT의 "receptive field"는 LSTM의 고정 window보다 넓다. Transformer self-attention 때문에 sequence 내 다른 위치들을 양방향으로 볼 수 있다.

[Detailed Explanation/Example] → sequence 일부 key를 `[MASK]`로 가리고 맞히게 한다. 정상 sequence라면 가려진 key가 모델의 top candidate 안에 들어갈 가능성이 높다. 일정 개수 이상 벗어나면 anomaly로 판정한다.

우리 문제에 그대로 적용하기 어려운 이유:

- 정상 sequence 5000개 수준이 필요한데, public에는 pass 10개뿐이다.
- masked key prediction은 "명세상 final response가 맞는지"를 직접 학습하지 않는다.
- 모델이 어떤 TCG/Opal 조항을 근거로 판단했는지 설명하기 어렵다.

적용 가능한 아이디어:

- 만약 synthetic data를 많이 만들 수 있다면, LogBERT식 self-supervised pretraining을 고려할 수 있다.
- 하지만 현재 우선순위는 모델 attention 분석이 아니라 rule trace/evidence trace를 만드는 것이다.

## 4. LogGPT

[EXTERNAL KNOWLEDGE] Han, X., Yuan, S., & Trabelsi, M. (2023). *LogGPT: Log anomaly detection via GPT*. arXiv. https://arxiv.org/abs/2309.14482

[Original Text/Data] → LogGPT는 GPT-2 구조를 사용한다. 먼저 정상 log sequence에서 next log key prediction으로 pretrain하고, 이후 Top-K reward를 정의해 PPO 기반 reinforcement learning으로 fine-tune한다. 실험에서는 각 dataset에서 정상 sequence 5000개를 train으로 사용하고, GPT model은 6 layers, 6 heads, embedding/hidden dimension 60을 사용했다.

[Exact Interpretation] → LogGPT의 fine-tuning은 일반 supervised label fine-tuning이 아니라, "실제 next key가 Top-K 안에 있으면 보상, 아니면 벌점"을 주는 anomaly 목적 정렬이다.

[Detailed Explanation/Example] → GPT가 다음 key 후보를 낸다. 실제 next key가 top 50% 후보 안에 있으면 reward +1, 아니면 -1을 준다. 이렇게 anomaly detection에서 쓰는 decision rule과 training objective의 간극을 줄인다.

우리 문제에 그대로 적용하기 어려운 이유:

- 5000개 정상 sequence가 필요하다는 전제는 여전히 크다.
- PPO fine-tuning은 서버 L40S에서는 가능할 수 있지만, public 20개로 하면 과적합이 거의 확실하다.
- 로컬에는 Qwen/GPT류 대형 모델을 내려받지 않는다는 제약이 있다.

적용 가능한 아이디어:

- synthetic normal/invalid trajectory generator가 완성된 뒤에는 작은 decoder model로 "next event plausibility"를 보조 점수로 쓸 수 있다.
- 현재 단계에서는 제출 성능보다 복잡도를 먼저 늘리는 선택이라 권하지 않는다.

## 5. RESTler

[EXTERNAL KNOWLEDGE] Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API fuzzing*. 2019 IEEE/ACM 41st International Conference on Software Engineering. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf

[Original Text/Data] → RESTler는 Swagger/OpenAPI specification을 분석해 request grammar와 producer-consumer dependency를 자동으로 만든다. 이후 response feedback으로 invalid sequence를 줄이며 stateful request sequence를 생성한다.

[Exact Interpretation] → RESTler는 neural model을 학습하지 않는다. 핵심은 명세에서 dependency를 뽑고, response로 상태 탐색 공간을 pruning하는 것이다.

[Detailed Explanation/Example] → `POST /posts`가 `id`를 만들고, `GET /posts/{id}`가 그 id를 소비한다면, RESTler는 `GET` 전에 `POST`가 와야 한다는 dependency를 추론한다. 무작위로 id를 찍는 대신 이전 response에서 얻은 id를 다음 request에 넣는다.

우리 문제에 적용할 점:

- TCG/Opal spec에서 `StartSession -> session id -> authenticated commands` 같은 producer-consumer dependency를 추출해야 한다.
- `Set C_PIN -> StartSession HostChallenge -> authority state` 같은 dependency를 state tracker에 넣어야 한다.
- 리더보드 제출 solver는 RESTler처럼 "명세 기반 deterministic engine"이어야 한다.

## 6. AFLNet

[EXTERNAL KNOWLEDGE] Pham, V.-T., Böhme, M., & Roychoudhury, A. (2020). *AFLNET: A greybox fuzzer for network protocols*. 2020 IEEE 13th International Conference on Software Testing, Validation and Verification. https://www.comp.nus.edu.sg/~abhik/pdf/AFLNet-ICST20.pdf

[Original Text/Data] → AFLNet은 실제 client-server message exchange seed corpus에서 시작한다. message sequence를 mutation하고, server response code를 state feedback으로 사용해 code/state coverage가 늘어나는 sequence를 보존한다.

[Exact Interpretation] → AFLNet도 모델 학습이 아니다. recorded valid exchange를 seed로 쓰고, response code 기반 state machine을 동적으로 만든다.

[Detailed Explanation/Example] → FTP seed가 `USER -> PASS -> ...` 순서라면, AFLNet은 message 단위로 mutation한다. response code가 새 state/transition을 만들거나 code coverage를 늘리면 그 seed를 유지한다.

우리 문제에 적용할 점:

- public pass trajectories는 valid seed corpus로 볼 수 있다.
- fail trajectories는 mutation 결과가 아니라 "final response가 잘못된 counterexample"이다.
- 단, AFLNet의 response code만 state로 쓰는 방식은 우리 문제에 부족하다. `SUCCESS`만 봐서는 tc4/tc14 같은 차이를 못 잡는다.

## 7. StateAFL

[EXTERNAL KNOWLEDGE] Natella, R. (2022). *StateAFL: Greybox fuzzing for stateful network servers*. Empirical Software Engineering, 27, Article 191. https://link.springer.com/article/10.1007/s10664-022-10233-3

[Original Text/Data] → StateAFL은 response code만으로 state를 추론하는 한계를 지적하고, long-lived data snapshot을 instrumentation으로 수집한 뒤 fuzzy hashing으로 protocol state id를 만든다.

[Exact Interpretation] → "마지막 response code"는 실제 state의 poor proxy일 수 있다. 상태 변수 자체를 추적해야 한다.

[Detailed Explanation/Example] → HTTP에서 `GET`과 `POST`가 모두 200을 돌려도, `POST`는 server state를 바꿀 수 있다. response code가 같아도 state는 다르다.

우리 문제에 적용할 점:

- `SUCCESS`는 PASS와 동의어가 아니다.
- solver는 `session_open`, `authenticated_authority`, `activated_sp`, `locking_range`, `media_key_version`, `written_payload` 같은 state variable을 명시적으로 가져야 한다.
- 초기 낮은 점수와 leaderboard 60.50은 state variable coverage가 아직 부족하다는 뜻이다.

## 8. ChatAFL

[EXTERNAL KNOWLEDGE] Meng, R., Mirchev, M., Böhme, M., & Roychoudhury, A. (2024). *Large language model guided protocol fuzzing*. Network and Distributed System Security Symposium. https://www.ndss-symposium.org/ndss-paper/large-language-model-guided-protocol-fuzzing/

[Original Text/Data] → ChatAFL은 AFLNet에 LLM guidance를 붙인다. 핵심은 grammar extraction, seed enrichment, coverage plateau handler다. 논문은 model weight fine-tuning 대신 few-shot prompting과 prompt engineering을 사용한다. 실험은 ProFuzzBench의 text-based protocol implementations에서 AFLNet/NSFuzz와 비교한다.

[Exact Interpretation] → ChatAFL에서 LLM은 "최종 판정 classifier"가 아니다. protocol grammar와 next message 후보를 만들어 fuzzing engine을 돕는다.

[Detailed Explanation/Example] → RTSP에서 현재 history가 `SETUP -> 200 OK`라면, plateau에 빠졌을 때 LLM에게 다음 client request를 묻고 `PLAY`나 `RECORD` 같은 state transition 유도 message를 받는다. grammar는 한 번 추출해 mutation guidance로 계속 쓴다.

우리 문제에 적용할 점:

- LLM을 runtime solver로 쓰기보다, TCG/Opal 문서에서 rule 후보를 추출하는 도구로 써야 한다.
- "가이드북의 어디를 봤는지"는 LLM attention이 아니라 retrieval source와 rule evidence로 남겨야 한다.
- Qwen 같은 모델은 서버 shared cache에서만 쓰고, 로컬/GitHub에는 두지 않는다.

## 9. StatePre

[EXTERNAL KNOWLEDGE] Zhang, Y., Zhu, K., Peng, J., Lu, Y., Chen, Q., & Li, Z. (2025). *StatePre: A large language model-based state-handling method for network protocol fuzzing*. Electronics, 14(10), 1931. https://www.mdpi.com/2079-9292/14/10/1931

[Original Text/Data] → StatePre는 LLM의 code/text understanding을 사용해 RFC-defined state knowledge와 protocol program의 state annotation을 분석·정제하는 방법으로 소개된다.

[Exact Interpretation] → 이 방향은 ChatAFL보다 우리 문제와 더 직접적으로 맞다. 자연어 spec에서 state transition knowledge를 뽑아 state handler를 개선하는 방식이기 때문이다.

[Detailed Explanation/Example] → 우리 문제에서는 TCG/Opal guidebook chunk를 검색하고, `StartSession`, `EndSession`, `Activate`, `Set`, `Get`, `GenKey`, `Read/Write`별 precondition/effect를 structured rule로 뽑는 과정에 해당한다.

## "Receptive Field"를 우리 문제에 맞게 바꾸기

신경망 모델에서 receptive field는 prediction에 영향을 줄 수 있는 input 범위다.

- DeepLog: 최근 `h`개 log key.
- LogBERT: Transformer self-attention이 보는 sequence 전체.
- LogGPT: causal prefix 전체 또는 context window.

하지만 현재 solver는 neural model이 아니므로 attention map은 없다. 대신 다음을 만들어야 한다.

```text
decision_trace = {
  case_id,
  final_step_index,
  final_method,
  final_invoking_uid,
  final_status,
  state_reads: ["active_sessions", "authenticated", "known_secrets", ...],
  state_writes_from_steps: [
    {"step": 2, "effect": "known_secrets += C_PIN value"},
    {"step": 6, "effect": "active_sessions += SPSessionID"}
  ],
  rule_ids: ["STARTSESSION_CHALLENGE_FORMAT", "READ_AFTER_GENKEY_PAYLOAD"],
  spec_refs: ["opal/<chunk>.txt#section", "core/<chunk>.txt#section"],
  verdict,
  reason
}
```

이것이 우리 버전의 "evidence receptive field"다. 장점은 다음과 같다.

- 점수가 낮을 때 어떤 rule/state/parser가 틀렸는지 바로 보인다.
- report에 "AI가 guidebook 어디를 참고했는지"를 명시할 수 있다.
- leaderboard/test 데이터를 train에 섞지 않고도 개선할 수 있다.

## 현재 접근의 문제점

[Original Text/Data] → 서버 public evaluation에서 초기 deterministic solver는 55점이었다. parser/rule 보강 후 public train/dev는 100점이 됐지만, leaderboard 제출 점수는 60.50이었다.

[Exact Interpretation] → 낮은 점수의 1차 원인은 모델 크기 문제가 아니라 parser/state coverage 문제였다. leaderboard 60.50은 hidden scenario에 대한 rule coverage가 여전히 부족하다는 뜻이다.

[Detailed Explanation/Example] → 실제로 발견된 결함은 다음과 같다.

- `HostSessionID`/`SPSessionID` 같은 nested response key를 session id로 제대로 읽지 못했다.
- `command/result` 형태의 DATA_COMMAND `Read/Write`를 일반 `status_codes` 형식처럼 처리했다.
- `HostChallenge`를 저장된 PIN 원문과 동일 비교하는 잘못된 가정을 했다.
- `SUCCESS` status만 보고 `Activate` 대상 SP UID가 맞는지 충분히 검사하지 못했다.
- 어떤 spec chunk를 근거로 rule을 적용했는지 추적하는 기능이 부족했다. 현재는 trace mode가 추가됐지만 spec-backed coverage matrix는 아직 없다.

## 권장 구현 방향

1. `StatefulOpalVerifier`에 trace mode를 추가한다.
2. 각 rule에 `rule_id`, `state_reads`, `state_writes`, `spec_ref`를 붙인다.
3. `/dl2026/skeleton/artifacts/documents`의 core/opal chunk를 lightweight index로 검색한다.
4. LLM은 서버에서만 사용해 rule 후보와 spec_ref 후보를 만들고, solver runtime에는 deterministic rule만 넣는다.
5. public 20개는 train/dev로만 사용한다.
6. leaderboard 결과는 점수와 commit만 기록하고 sample-level label로 역추론하지 않는다.
7. W&B sweep은 learning rate가 아니라 parser/rule/retrieval 설정만 대상으로 한다.

## 사용하면 안 되는 방향

- public 20개를 그대로 외우는 filename-based rule.
- leaderboard score를 보고 개별 hidden case label을 추정해 rule에 박는 방식.
- 로컬에 Qwen/Gemma 같은 대형 모델 다운로드.
- public 20개로 LLM fine-tuning.
- final status만 보는 classifier.

## 최종 제안

지금은 "작은 SOTA 모델 압축"보다 "명세 근거가 달린 deterministic state verifier"가 맞다. 논문 계열로
표현하면 DeepLog/LogBERT보다 RESTler/StateAFL/ChatAFL/StatePre에 가깝다.

실험 우선순위:

1. public 20개 100점은 유지한다.
2. trace를 보고 rule이 sample memorization이 아닌지 검토한다.
3. guidebook chunk retrieval을 붙여 각 rule의 evidence를 문서화한다.
4. rule coverage matrix와 synthetic mutation으로 hidden coverage gap을 줄인다.
5. 필요할 때만 서버 shared cache의 Qwen 소형 모델로 spec extraction 보조 실험을 한다.

## 참고문헌

- Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API fuzzing*. 2019 IEEE/ACM 41st International Conference on Software Engineering. https://patricegodefroid.github.io/public_psfiles/icse2019.pdf
- Du, M., Li, F., Zheng, G., & Srikumar, V. (2017). *DeepLog: Anomaly detection and diagnosis from system logs through deep learning*. Proceedings of the 2017 ACM SIGSAC Conference on Computer and Communications Security, 1285-1298. https://www2.cs.utah.edu/~lifeifei/papers/deeplog.pdf
- Guo, H., Yuan, S., & Wu, X. (2021). *LogBERT: Log anomaly detection via BERT*. arXiv. https://arxiv.org/abs/2103.04475
- Han, X., Yuan, S., & Trabelsi, M. (2023). *LogGPT: Log anomaly detection via GPT*. arXiv. https://arxiv.org/abs/2309.14482
- Meng, R., Mirchev, M., Böhme, M., & Roychoudhury, A. (2024). *Large language model guided protocol fuzzing*. Network and Distributed System Security Symposium. https://www.ndss-symposium.org/ndss-paper/large-language-model-guided-protocol-fuzzing/
- Meng, W., Liu, Y., Zhu, Y., Zhang, S., Pei, D., Liu, Y., Chen, Y., Zhang, R., Tao, S., Sun, P., & Zhou, R. (2019). *LogAnomaly: Unsupervised detection of sequential and quantitative anomalies in unstructured logs*. Proceedings of the Twenty-Eighth International Joint Conference on Artificial Intelligence, 4739-4745. https://www.ijcai.org/proceedings/2019/658
- Natella, R. (2022). *StateAFL: Greybox fuzzing for stateful network servers*. Empirical Software Engineering, 27, Article 191. https://link.springer.com/article/10.1007/s10664-022-10233-3
- Pham, V.-T., Böhme, M., & Roychoudhury, A. (2020). *AFLNET: A greybox fuzzer for network protocols*. 2020 IEEE 13th International Conference on Software Testing, Validation and Verification. https://www.comp.nus.edu.sg/~abhik/pdf/AFLNet-ICST20.pdf
- Zhang, Y., Zhu, K., Peng, J., Lu, Y., Chen, Q., & Li, Z. (2025). *StatePre: A large language model-based state-handling method for network protocol fuzzing*. Electronics, 14(10), 1931. https://www.mdpi.com/2079-9292/14/10/1931
- Zhu, J., He, S., He, P., Liu, J., & Lyu, M. R. (2023). *Loghub: A large collection of system log datasets for AI-driven log analytics*. 2023 IEEE 34th International Symposium on Software Reliability Engineering. https://arxiv.org/abs/2008.06448
