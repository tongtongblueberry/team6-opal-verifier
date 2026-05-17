<!-- Added: 이 문서는 project.pdf.pdf의 내용을 한국어로 정리하고, 외부 조사 내용을 근거와 함께 분리하기 위해 새로 작성했다. -->
# SSD TCG/Opal 프로토콜 검증 프로젝트 정리

작성일: 2026-05-17  
분석 대상: `project.pdf.pdf`  
현재 로컬 프로젝트 상태: 저장소 루트에는 `project.pdf.pdf`만 있음. 학습 데이터, `src/`, `setup.sh`, `pyproject.toml`, `uv.lock`은 아직 없음.

<!-- Added: 파일 분석의 전제와 구조를 명시해 뒤의 해석 범위를 분리했다. -->
## 0. 파일 구조 골격

분석한 PDF는 10쪽짜리 서울대학교 Introduction to Deep Learning 과목 Term Project 명세다.

- p. 1: `1 Task Overview`
- p. 1-3: `1.1 Key Concepts for This Task`, `1.2 What a Command-Response Record Looks Like`
- p. 3: `2 Formal Task Definition`
- p. 3-8: `3 Background: TCG Storage and Test Cases`
- p. 3-4: `3.1 Specification Documents at a Glance`
- p. 4-5: `3.2 How to Read a TCG Method Call`
- p. 5-7: `3.3 Reading Example Test Cases`
- p. 7: `3.4 Practical Remarks`
- p. 8: `3.5 Final Reminder: Verdict vs. Device Response`
- p. 8-9: `4 Evaluation Criteria`
- p. 8-9: `5 Practice Server Usage`
- p. 9-10: `6 Submission Policy`

<!-- Added: 과제 내용을 한국어로 번역 요약하고, PDF 근거 위치를 붙였다. -->
## 1. 프로젝트 내용 번역 요약

### 1.1 해결해야 하는 문제

[Original Text/Data] `project.pdf.pdf`, p. 1, Section 1, 추출 line 9-25: 입력은 SSD에서 수집된 command-response log이고, 모델은 전체 log를 보고 마지막 응답의 판정을 `PASS` 또는 `FAIL`로 출력해야 한다. 핵심 난점은 SSD가 stateful하다는 점이다.  
[Exact Interpretation] 주어진 JSON trajectory 전체를 읽고, 마지막 command-response pair의 실제 SSD 응답이 현재 프로토콜 상태에서 허용되는지 이진 분류해야 한다.  
[Detailed Explanation/Example] 마지막 명령만 보면 안 된다. 이전에 세션이 열렸는지, 어떤 권한으로 인증했는지, Locking range가 잠겼는지/풀렸는지에 따라 같은 `SUCCESS` 응답도 `PASS`가 될 수 있고 `FAIL`이 될 수 있다.

### 1.2 입력과 출력

[Original Text/Data] `project.pdf.pdf`, p. 3, Section 2, 추출 line 138-154: 테스트 케이스는 JSON command-response record의 시퀀스 `X=((c1,r1),...,(cN,rN))`이고, 목표는 `y in {PASS, FAIL}` 예측이다.  
[Exact Interpretation] 입력 단위는 하나의 SSD 실행 trajectory이며, 최종 record만 평가 대상이고 이전 record들은 상태 추론을 위한 context다.  
[Detailed Explanation/Example] Step 1-6에서 인증과 설정이 성공했으면 Step 7의 `StartSession` 성공은 정상일 수 있다. 반대로 인증 없이 보호 객체를 수정했는데 `SUCCESS`가 나오면 최종 응답은 실패 판정이다.

### 1.3 PASS/FAIL의 의미

[Original Text/Data] `project.pdf.pdf`, p. 2, 추출 line 75-79 및 p. 8, 추출 line 428-441: `PASS`는 SSD가 `SUCCESS`를 반환했다는 뜻이 아니라, 프로토콜 상태상 올바른 응답을 반환했다는 뜻이다.  
[Exact Interpretation] 모델은 device response 자체의 성공/실패가 아니라, specification compliance를 판정해야 한다.  
[Detailed Explanation/Example] 오류 응답도 올바른 거절이면 `PASS`다. 성공 응답도 거절해야 할 상황에서 성공했으면 `FAIL`이다.

### 1.4 왜 문제가 되는가

[Original Text/Data] `project.pdf.pdf`, p. 1-2, 추출 line 22-25, 108-128: 같은 명령의 정오답이 이전 상태에 의존하며, 모델은 session/authentication/locking state를 추론해야 한다.  
[Exact Interpretation] 단순 로그 분류가 아니라 상태 기계(state machine) 검증 문제다.  
[Detailed Explanation/Example] Self-Encrypting Drive(SED)의 인증, 접근제어, 잠금 상태가 잘못 구현되면 보호되어야 할 저장 영역이 열리거나, 키 재생성 후에도 이전 plaintext가 읽히는 식의 보안 결함이 생긴다.

### 1.5 왜 AI로 해결해야 하는가

[Original Text/Data] `project.pdf.pdf`, p. 3, 추출 line 153-154: deep learning, LLM, prompting, retrieval, fine-tuning, rule-based components 등 여러 전략을 허용한다. p. 8, 추출 line 444-447: private dataset에는 public dataset/leaderboard에 없는 scenario가 포함된다.  
[Exact Interpretation] 과제는 반드시 순수 딥러닝만 요구하지 않는다. 다만 unseen scenario 일반화를 위해 학습 기반 또는 LLM 기반 상태 추론을 결합할 수 있게 설계되어 있다.  
[Detailed Explanation/Example] 규칙 기반 verifier는 정확하지만 TCG/Opal 상태와 예외가 많으면 coverage가 부족할 수 있다. 반대로 순수 LLM은 느리고 환각 위험이 있다. 따라서 실전 전략은 `symbolic state tracker + learned classifier/LLM reranker`가 가장 합리적이다.

<!-- Added: 과제 제약사항을 제출 실패 위험과 바로 연결해 정리했다. -->
## 2. 평가와 환경 제약

### 2.1 평가 방식

[Original Text/Data] `project.pdf.pdf`, p. 8, Section 4, 추출 line 444-458: 최종 평가는 private dataset에서 accuracy로 측정되며 4-page report 제출이 필요하다.  
[Exact Interpretation] leaderboard 과최적화보다 unseen protocol scenario에 대한 일반화가 중요하다.  
[Detailed Explanation/Example] 특정 public JSON 파일 이름이나 public label 분포를 외우는 방식은 private set에서 깨질 가능성이 높다.

### 2.2 서버 자원

[Original Text/Data] `project.pdf.pdf`, p. 8-9, Section 5, 추출 line 460-489: practice server는 NVIDIA L40S 48GB GPU, 24 CPU cores, 60GB CPU memory를 제공한다. `/home/student`는 100GB, `/workspace`는 1TB이며 public dataset은 `/dl2026/dataset`에 있다.  
[Exact Interpretation] 48GB GPU 하나에서 학습/추론 가능한 모델이어야 하며, 큰 checkpoint와 데이터는 `/workspace`에 둬야 한다.  
[Detailed Explanation/Example] 20B급 sparse/quantized 모델은 실행 가능성이 있지만, evaluation time 3시간과 batch 처리량을 고려하면 모든 샘플에 긴 CoT prompt를 넣는 방식은 위험하다.

### 2.3 제출 구조

[Original Text/Data] `project.pdf.pdf`, p. 9, 추출 line 503-509: 제출 디렉터리는 `src/`, `setup.sh`, `pyproject.toml`, `uv.lock`을 포함해야 하며, 선택적으로 `artifacts/`를 포함할 수 있다.  
[Exact Interpretation] 최종 제출은 재현 가능한 Python project 형태여야 한다.  
[Detailed Explanation/Example] 학습 notebook만 있으면 안 된다. 평가 서버는 별도 evaluator와 dataset을 쓰므로 `evaluate.py`나 local `predictions.jsonl`에 의존하면 안 된다.

### 2.4 네트워크, 시간, 용량 제약

[Original Text/Data] `project.pdf.pdf`, p. 10, 추출 line 543-566: setup phase는 network 가능, 20분 제한이다. evaluation phase는 network 없음, 3시간 제한이다. 제출 archive는 12GB를 넘으면 거부된다.  
[Exact Interpretation] 평가 중에는 모델 다운로드, API 호출, W&B online logging이 불가능하다. 필요한 weight는 staff cache, `setup.sh`, 또는 `artifacts/`로 준비해야 한다.  
[Detailed Explanation/Example] OpenAI API나 Hugging Face Hub 실시간 다운로드에 의존하는 solver는 evaluation phase에서 실패한다. W&B sweep은 개발/학습용이고 제출 solver 내부에는 넣으면 안 된다.

### 2.5 기본 제공 pretrained model

[Original Text/Data] `project.pdf.pdf`, p. 10, 추출 line 556-565: evaluation server의 shared Hugging Face cache에는 `openai/gpt-oss-20b`, `Qwen/Qwen3.5-{0.8B,2B,4B,9B}`, `Qwen/Qwen3.5-27B-FP8`, `Qwen/Qwen3.5-35B-A3B-FP8`, `google/gemma-4-26B-A4B-it`, `google/gemma-4-{E2B,E4B,31B}-it` 등이 있다.  
[Exact Interpretation] 이 목록 밖 모델을 쓰려면 `artifacts/`에 넣거나 setup phase 20분 안에 받아야 한다.  
[Detailed Explanation/Example] 현실적으로는 cache에 있는 Qwen/Gemma/gpt-oss 계열을 쓰고, fine-tuning 결과는 LoRA adapter처럼 작은 artifact만 제출하는 것이 안전하다.

<!-- Added: 사용자가 물은 모델 크기와 추론 제한을 제출 제약으로 환산했다. -->
## 3. 모델은 얼마나 작아야 하는가

[Original Text/Data] `project.pdf.pdf`, p. 10, 추출 line 547-553: evaluation phase는 3시간, archive는 12GB 제한이다. p. 10, 추출 line 556-566: 일부 pretrained model은 shared HF cache에 있다.  
[Exact Interpretation] 모델 크기 판단 기준은 `VRAM 48GB`, `3시간 내 전체 private set 추론`, `12GB archive`, `network 없음`이다.  
[Detailed Explanation/Example] cache에 있는 모델은 archive size를 차지하지 않지만, 추론 시간이 너무 길면 0점 위험이 있다. cache 밖 20B+ 모델을 직접 넣는 것은 12GB 제한 때문에 비현실적이다.

추천 크기:

- 1차 solver: 규칙/feature 기반 classifier. checkpoint 0-수백 MB.
- LLM 보조 solver: `Qwen3.5-4B` 또는 `Qwen3.5-9B` + LoRA adapter. adapter는 보통 수십-수백 MB라 제출이 쉽다.
- 고성능 teacher/분석용: `gpt-oss-20b` 또는 `Qwen3.5-27B-FP8`. 개발 중 pseudo-label/rationale 생성에는 유용하지만, 모든 evaluation sample에 직접 쓰는 것은 latency를 측정한 뒤 결정해야 한다.
- 피해야 할 기본 전략: private set 전체에 대해 긴 prompt + 긴 reasoning output을 매번 생성하는 zero-shot LLM-only 방식.

추론 속도 제한:

- 명세에 per-sample latency 제한은 없다.
- 명시된 제한은 전체 evaluation phase 3시간이다.
- 따라서 solver는 batch inference, cached tokenizer/model load, max_new_tokens 제한, deterministic output parsing을 기본으로 해야 한다.

<!-- Added: 외부 지식은 PDF와 구분하고 APA 출처를 먼저 제공했다. -->
## 4. [EXTERNAL KNOWLEDGE] 관련 대회/벤치마크와 연구 축

APA sources used in this section:

- Trusted Computing Group. (n.d.). *TCG Storage Architecture Core Specification*. https://trustedcomputinggroup.org/resource/tcg-storage-architecture-core-specification/
- Trusted Computing Group. (n.d.). *TCG Storage Application Note: Encrypting Drives Compliant with Opal SSC*. https://trustedcomputinggroup.org/resource/storage-application-note-encrypting-drives-compliant-with-opal-ssc/
- Zhu, J., He, S., He, P., Liu, J., & Lyu, M. R. (2023). *Loghub: A large collection of system log datasets for AI-driven log analytics*. arXiv. https://arxiv.org/abs/2008.06448
- Ba, J., Bohme, M., Mirzamomen, Z., & Roychoudhury, A. (2022). *Stateful Greybox Fuzzing*. USENIX Security 22. https://www.usenix.org/conference/usenixsecurity22/presentation/ba
- Atlidakis, V., Godefroid, P., & Polishchuk, M. (2019). *RESTler: Stateful REST API Fuzzing*. ICSE. https://www.microsoft.com/en-us/research/publication/restler-stateful-rest-api-fuzzing/

[Original Text/Data] TCG Core page states that TCG Storage specifications define an architecture for policy-driven access control over storage devices. TCG Opal application note lists workflows such as taking ownership, activating Locking SP, configuring locking objects, unlocking ranges, erasing, and reverting.  
[Exact Interpretation] 이 과제는 일반 로그 이상 탐지보다 더 특수한 `스토리지 보안 프로토콜 상태 검증` 문제다.  
[Detailed Explanation/Example] 공개 검색 기준으로 이 과제와 동일한 "TCG Opal command-response compliance PASS/FAIL" 대회는 확인되지 않았다. 가장 가까운 공개 축은 두 가지다.

1. Log anomaly detection / AIOps:
   - LogHub의 HDFS, BGL, Thunderbird 같은 공개 로그 데이터셋이 널리 쓰인다.
   - 문제 형태는 sequence log에서 anomaly/normal을 판정한다는 점에서 유사하다.
   - 차이는 이 과제의 label이 통계적 이상 여부가 아니라 protocol specification compliance라는 점이다.

2. Stateful protocol testing / fuzzing:
   - Stateful Greybox Fuzzing, RESTler 같은 연구는 상태 의존 요청 sequence를 다룬다.
   - 문제 형태는 "이전 요청들이 만든 상태 때문에 다음 요청의 정오답이 달라진다"는 점에서 유사하다.
   - 차이는 fuzzing은 버그를 찾기 위해 sequence를 생성/변형하는 쪽이고, 이 과제는 주어진 sequence의 최종 응답을 판정하는 쪽이다.

관련 대회라고 부를 수 있는 것:

- 정확히 같은 공개 대회: 확인 못 함.
- 가장 유사한 대회/벤치마크: AIOps/log anomaly detection 계열, LogHub 기반 HDFS/BGL/Thunderbird benchmark.
- 논문 비교 관례: fastMRI에서 FI/VarNet 비교가 기본인 것처럼, 로그 이상 탐지에서는 `DeepLog`, `LogAnomaly`, `LogRobust`, `PLELog`, `LogBERT`, `LogFormer` 계열이 자주 baseline으로 등장한다.

<!-- Added: 모델 후보를 과제 적합성 기준으로 정리했다. -->
## 5. [EXTERNAL KNOWLEDGE] 관련 모델과 SOTA 판단

APA sources used in this section:

- Du, M., Li, F., Zheng, G., & Srikumar, V. (2017). *DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning*. ACM CCS. https://svivek.com/research/du2017deeplog.html
- Meng, W., Liu, Y., Zhu, Y., Zhang, S., Pei, D., Liu, Y., Chen, Y., Zhang, R., Tao, S., Sun, P., & Zhou, R. (2019). *LogAnomaly: Unsupervised Detection of Sequential and Quantitative Anomalies in Unstructured Logs*. IJCAI. https://www.ijcai.org/proceedings/2019/658
- Guo, H., Yuan, S., & Wu, X. (2021). *LogBERT: Log Anomaly Detection via BERT*. arXiv. https://arxiv.org/abs/2103.04475
- Patel, D. (2026). *LLM-Enhanced Log Anomaly Detection: A Comprehensive Benchmark of Large Language Models for Automated System Diagnostics*. arXiv. https://arxiv.org/abs/2604.12218
- Yang, Z., & Harris, I. G. (2025). *LogLLaMA: Transformer-based log anomaly detection with LLaMA*. arXiv. https://arxiv.org/abs/2503.14849
- Pospieszny, P., Mormul, W., Szyndler, K., & Kumar, S. (2025). *ADALog: Adaptive Unsupervised Anomaly detection in Logs with Self-attention Masked Language Model*. arXiv. https://arxiv.org/abs/2505.13496
- Yang, A., Li, A., Yang, B., Zhang, B., Hui, B., Zheng, B., Yu, B., Gao, C., Huang, C., Lv, C., et al. (2025). *Qwen3 Technical Report*. arXiv. https://arxiv.org/abs/2505.09388
- Gemma Team. (2025). *Gemma 3 Technical Report*. arXiv. https://arxiv.org/abs/2503.19786
- OpenAI. (2025, August 5). *Introducing gpt-oss*. https://openai.com/index/introducing-gpt-oss/

### 5.1 로그 이상 탐지 쪽 baseline

[Original Text/Data] DeepLog는 LSTM으로 log를 자연어 sequence처럼 모델링한다. LogAnomaly는 sequential anomaly와 quantitative anomaly를 함께 탐지한다. LogBERT는 BERT 기반 self-supervised log anomaly detection이다.  
[Exact Interpretation] 이 과제 보고서에서 "관련 연구와 비교"를 쓴다면 위 모델들을 기본 baseline으로 언급하는 것이 자연스럽다.  
[Detailed Explanation/Example] 다만 이 과제는 일반 log anomaly가 아니라 TCG/Opal protocol state compliance다. 그래서 DeepLog/LogBERT를 그대로 가져오면 최종 `PASS/FAIL` 설명력은 부족할 수 있고, state feature를 추가해야 한다.

### 5.2 2025-2026 기준 SOTA 경향

[Original Text/Data] 2026년 LLM log anomaly benchmark는 fine-tuned transformer가 F1 0.96-0.99로 가장 높은 성능을 보였고, prompt-based LLM은 label 없이도 F1 0.82-0.91 수준의 zero/few-shot 성능을 보인다고 보고한다. LogLLaMA는 LLaMA 기반 생성+RL 방식이 HDFS/BGL/Thunderbird에서 기존 SOTA를 넘었다고 주장한다. ADALog는 masked language model 기반 unsupervised log anomaly detection을 제안한다.  
[Exact Interpretation] "순수 SOTA 하나"를 고르는 것보다, 데이터/latency/label availability에 따라 fine-tuned small transformer 또는 compressed LLM을 고르는 것이 맞다.  
[Detailed Explanation/Example] 이 프로젝트에서는 private evaluation과 3시간 제한이 있으므로, 최신 거대 LLM을 그대로 쓰는 것보다 2025년 안정화된 소형/중형 모델을 task-specific하게 압축하는 접근이 더 안전하다.

### 5.3 이 과제에 맞는 모델 선택 결론

추천 순위:

1. `Symbolic state tracker + feature classifier`
   - 이유: 문제의 핵심 상태가 명세에 명시되어 있다. session/auth/locking/key state를 직접 추적하면 일반화가 강하다.
   - 모델 후보: logistic regression, LightGBM/XGBoost, small MLP, shallow transformer encoder.

2. `Qwen3.5-4B` 또는 `Qwen3.5-9B` fine-tuning/LoRA
   - 이유: PDF상 evaluation server cache에 있고, 48GB L40S에서 충분히 다루기 쉬운 크기다.
   - 사용 방식: JSON trajectory를 compact textual trace로 변환하고, 최종 label만 출력하도록 instruction fine-tuning.
   - 압축 방식: 4-bit QLoRA 또는 adapter-only submission.

3. `gpt-oss-20b` zero/few-shot 또는 distillation teacher
   - 이유: OpenAI에 따르면 20B 총 parameter, token당 active parameter 3.6B, 16GB memory 실행을 목표로 한 open-weight reasoning model이다.
   - 사용 방식: 모든 sample 직접 추론보다는 teacher로 rationale/pseudo-label을 만들고 작은 모델에 distill하는 편이 안전하다.

4. `Qwen3.5-27B-FP8` 또는 `Qwen3.5-35B-A3B-FP8`
   - 이유: cache에 있으므로 archive 부담은 없지만, evaluation latency와 memory fragmentation 위험이 있다.
   - 사용 방식: fallback verifier 또는 validation-time analysis에는 좋지만 primary solver로 쓰려면 실제 dataset 크기에서 속도 측정이 필요하다.

최종 추천:

- 첫 제출 목표: `rule/state tracker + Qwen3.5-4B LoRA classifier`.
- 성능 여유 목표: `Qwen3.5-9B LoRA`를 주 모델로, rule-based sanity check를 후처리로 사용.
- 연구 보고서 포지션: `DeepLog/LogBERT-style sequence modeling`과 `stateful protocol reasoning`의 차이를 명확히 설명하고, baseline은 classical classifier, compact transformer, LLM few-shot을 비교.

<!-- Added: 구현 전략을 데이터 흐름 중심으로 정리했다. -->
## 6. 권장 시스템 설계

[Original Text/Data] `project.pdf.pdf`, p. 7, 추출 line 403-414: 최종 target record를 식별하고, 성공한 operation 이후에만 state를 갱신하며, symbolic name을 사용하고, TCG command가 non-TCG Read에도 영향을 줄 수 있다고 설명한다.  
[Exact Interpretation] 모델 입력 전처리에서 state transition과 symbolic normalization을 해줘야 한다.  
[Detailed Explanation/Example] UID/byte string을 그대로 LLM에 던지기보다 `StartSession(AdminSP, SID, Write=1) -> SUCCESS` 같은 canonical event로 바꾸는 것이 안정적이다.

추천 data flow:

1. JSON trajectory load
2. 각 record를 canonical event로 변환
3. symbolic state tracker 실행
   - session open/closed
   - active SP
   - authenticated authority
   - C_PIN credential update
   - Locking range enabled/locked/unlocked
   - GenKey 이후 media key changed
4. 최종 record feature 생성
   - target method/command
   - invoking object/table/SP
   - actual status/output
   - expected status 후보
   - state snapshot
5. classifier 또는 LLM에 compact input 제공
6. `PASS`/`FAIL`만 출력
7. rule-based post-check
   - 출력이 둘 중 하나가 아니면 fallback
   - 명백한 protocol violation이면 override

권장 ablation:

- A0: majority/random baseline
- A1: final command only classifier
- A2: full trajectory text classifier
- A3: symbolic state feature classifier
- A4: symbolic state + compact LLM LoRA
- A5: A4 + rule-based post-check

<!-- Added: W&B sweep 준비안을 문서에 포함했다. 실제 파일 생성은 데이터/코드 scaffold가 생긴 뒤 해야 한다. -->
## 7. W&B parameter sweep 준비안

현재 로컬에는 데이터와 solver 코드가 없으므로 실행 가능한 W&B sweep 파일을 확정할 수 없다. 하지만 준비해야 할 sweep 축은 명확하다.

### 7.1 sweep에서 바꿀 parameter

[Original Text/Data] `project.pdf.pdf`, p. 8-10: accuracy가 최종 metric이고, evaluation은 private set에서 수행되며, 시간/용량 제약이 있다.  
[Exact Interpretation] sweep은 public validation accuracy만 보지 말고 inference latency, model size, invalid output rate를 함께 기록해야 한다.  
[Detailed Explanation/Example] private set에서 일반화하려면 overfit된 prompt보다 state feature와 compact model의 조합을 비교해야 한다.

필수 기록 metric:

- `val/accuracy`
- `val/f1_pass`
- `val/f1_fail`
- `val/confusion_pass_fail`
- `val/invalid_output_rate`
- `speed/samples_per_second`
- `speed/p95_latency_ms`
- `model/num_parameters_trainable`
- `model/artifact_size_mb`

추천 sweep parameter:

- preprocessing:
  - `canonicalize_uid`: true/false
  - `include_raw_json`: false/true
  - `max_context_records`: 32/64/128/all
  - `state_features`: none/basic/full
- model:
  - `model_family`: feature_mlp/qwen3_5_4b/qwen3_5_9b
  - `lora_rank`: 4/8/16/32
  - `lora_alpha`: 16/32/64
  - `learning_rate`: 1e-5/2e-5/5e-5/1e-4
  - `batch_size`: 1/2/4/8
  - `grad_accum`: 1/2/4/8
  - `max_seq_len`: 2048/4096/8192
  - `class_weight`: none/balanced
- inference:
  - `max_new_tokens`: 2/4/8
  - `temperature`: 0.0
  - `use_rule_override`: true/false

### 7.2 W&B sweep YAML 초안

```yaml
program: train.py
method: bayes
metric:
  name: val/accuracy
  goal: maximize
parameters:
  seed:
    values: [1, 2, 3]
  canonicalize_uid:
    values: [true]
  include_raw_json:
    values: [false, true]
  max_context_records:
    values: [32, 64, 128]
  state_features:
    values: ["basic", "full"]
  model_family:
    values: ["feature_mlp", "qwen3_5_4b"]
  lora_rank:
    values: [8, 16]
  lora_alpha:
    values: [16, 32]
  learning_rate:
    distribution: log_uniform_values
    min: 0.00001
    max: 0.0001
  batch_size:
    values: [1, 2, 4]
  grad_accum:
    values: [1, 2, 4]
  max_seq_len:
    values: [2048, 4096]
  class_weight:
    values: ["none", "balanced"]
  use_rule_override:
    values: [true, false]
early_terminate:
  type: hyperband
  min_iter: 3
command:
  - ${env}
  - python
  - ${program}
  - --config
  - configs/train.yaml
  - ${args}
```

### 7.3 W&B 운용 방식

- 개발 서버에서만 online W&B 사용.
- evaluation 제출 코드에서는 W&B import 자체를 optional 처리하거나 비활성화.
- 재현성을 위해 sweep best run의 config를 `artifacts/best_config.json` 또는 `configs/best.yaml`로 고정.
- evaluation phase에서는 `WANDB_MODE=disabled` 또는 logging 제거.

권장 명령:

```bash
wandb login
wandb sweep sweeps/ssd_verifier.yaml
wandb agent <entity>/<project>/<sweep_id>
```

제출용 환경 변수:

```bash
export WANDB_MODE=disabled
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

<!-- Added: 작업 우선순위를 바로 실행 가능한 형태로 정리했다. -->
## 8. 바로 해야 할 일

1. 서버에서 `/dl2026/dataset` 구조 확인
   - train/validation label 존재 여부
   - JSON schema
   - 제출 evaluator가 solver를 호출하는 interface

2. baseline 구현
   - `src/solver.py`
   - JSON loader
   - final target record 식별
   - canonicalizer
   - simple rule baseline

3. validation split 구성
   - test case family 단위 split이 가능하면 family leakage 방지
   - 단순 random split만 쓰면 private scenario 일반화가 과대평가될 수 있음

4. state tracker 구현
   - session/auth/locking/key state를 명시적으로 추적
   - 실패한 command는 state update 금지

5. model sweep
   - feature classifier 먼저 sweep
   - 그 다음 Qwen3.5-4B LoRA sweep
   - 마지막에 Qwen3.5-9B 또는 gpt-oss-20b teacher distillation 검토

6. 제출 안정성 확인
   - `bash setup.sh`
   - `python evaluate.py`
   - network off simulation
   - archive size 확인
   - cold-start model load time 확인

<!-- Added: 최종 결론을 의사결정 중심으로 요약했다. -->
## 9. 결론

[Original Text/Data] `project.pdf.pdf`는 이 과제를 "stateful protocol reasoning" 문제로 명시하고, private dataset unseen scenario와 3시간 offline evaluation을 제약으로 둔다.  
[Exact Interpretation] 순수 SOTA LLM을 크게 쓰는 문제라기보다, TCG/Opal 상태를 잘 추적하고 compact model로 최종 compliance를 판정하는 문제다.  
[Detailed Explanation/Example] 가장 합리적인 전략은 `state tracker + compact classifier/LoRA LLM + rule post-check`다. 모델은 `Qwen3.5-4B`부터 시작하고, validation에서 context가 길거나 reasoning이 부족하면 `Qwen3.5-9B`로 올리는 것이 안전하다. `gpt-oss-20b`는 teacher나 fallback으로 검토하되, primary solver로 쓰기 전에는 private-size 추론 시간을 반드시 측정해야 한다.
