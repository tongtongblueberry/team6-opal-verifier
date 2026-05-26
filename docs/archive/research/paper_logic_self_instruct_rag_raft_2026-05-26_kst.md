# Self-Instruct/RAG/RAFT 논리 구조 기록 (2026-05-26 KST)

<!-- 변경: Self-Instruct, RAG, RAFT, RAGTruth의 논리 구조와 과제 적용 결론을 새 연구 기록으로 생성했다. 이유: spec 없이 생성된 text를 synthetic train data로 채택할 수 있는지 검증 가능한 근거로 남기기 위함이다. -->

## 범위

[Original Text/Data] → 사용자 질문: "논문은 읽어본 게 맞나?", "논문의 논리 구조가 뭐였나?", "spec 없이 Codex/Gemini가 그냥 text를 만드는 게 가능한가?", "논문에서 그게 가능하다고 하나?"

[Exact Interpretation] → 이 문서는 논문 전체 번역본이 아니라, TCG/Opal SSD command-response trajectory의 마지막 response pass/fail 판정 데이터 생성에 필요한 논리 구조와 한계를 정리하는 연구 기록이다.

[Detailed Explanation/Example] → 핵심 판단 대상은 synthetic label이다. accepted synthetic label은 final response entailment와 state transition 정합성을 동시에 만족해야 한다. Self-Instruct alone으로 폐쇄 명세 정합성을 보장한다는 주장은 금지한다. RAG/RAFT는 spec-grounded 생성 방향을 뒷받침하지만, RAGTruth가 지적하듯 retrieval이 있어도 unsupported 또는 contradictory claim이 생길 수 있으므로 offline data gate/validation이 필요하다. runtime rule engine은 금지한다.

## 외부 근거

<!-- 변경: 외부 논문 근거를 APA 형식과 링크로 기록했다. 이유: 사용자 지정 무결성 규칙에 따라 외부 지식의 출처를 명시하기 위함이다. -->

[EXTERNAL KNOWLEDGE] Wang, Y., Kordi, Y., Mishra, S., Liu, A., Smith, N. A., Khashabi, D., & Hajishirzi, H. (2023). Self-Instruct: Aligning language models with self-generated instructions. In A. Rogers, J. Boyd-Graber, & N. Okazaki (Eds.), Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 13484-13508). Association for Computational Linguistics. https://doi.org/10.18653/v1/2023.acl-long.754

[EXTERNAL KNOWLEDGE] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Küttler, H., Lewis, M., Yih, W.-T., Rocktäschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. In Advances in Neural Information Processing Systems 33. Curran Associates, Inc. https://papers.nips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html

[EXTERNAL KNOWLEDGE] Zhang, T., Patil, S. G., Jain, N., Shen, S., Zaharia, M., Stoica, I., & Gonzalez, J. E. (2024). RAFT: Adapting language model to domain specific RAG. arXiv. https://doi.org/10.48550/arXiv.2403.10131

[EXTERNAL KNOWLEDGE] Niu, C., Wu, Y., Zhu, J., Xu, S., Shum, K., Zhong, R., Song, J., & Zhang, T. (2024). RAGTruth: A hallucination corpus for developing trustworthy retrieval-augmented language models. In L.-W. Ku, A. Martins, & V. Srikumar (Eds.), Proceedings of the 62nd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 10862-10878). Association for Computational Linguistics. https://doi.org/10.18653/v1/2024.acl-long.585

## 질문별 결론

<!-- 변경: 사용자 질문 네 가지에 대한 직접 결론을 추가했다. 이유: 논문 근거와 과제 정책을 분리하지 않고 즉시 판정 가능하게 하기 위함이다. -->

[Original Text/Data] → Self-Instruct는 모델이 스스로 instruction/input/output을 만들고 필터링한 뒤 finetuning에 쓰는 방법이다.

[Exact Interpretation] → 논문은 "모델 생성 synthetic instruction data로 instruction-following 성능을 올릴 수 있다"는 구조를 보인다.

[Detailed Explanation/Example] → 따라서 "LLM이 text를 만들 수 있는가?"라는 좁은 질문에는 가능하다고 답할 수 있다. 그러나 "TCG/Opal 폐쇄 명세의 pass/fail label로 그대로 채택 가능한가?"라는 질문에는 아니다. Self-Instruct의 필터링은 invalid/similar sample 제거와 instruction tuning 품질 개선을 목표로 하며, domain spec truth, final response entailment, state transition 정합성 보장을 증명하지 않는다.

[Original Text/Data] → RAG는 parametric model과 non-parametric retrieved memory를 결합한다.

[Exact Interpretation] → 지식 intensive task에서는 모델 내부 파라미터만 믿지 않고, 외부 source를 retrieval해 generation 조건으로 넣는다.

[Detailed Explanation/Example] → 우리 문제에서는 TCG/Opal spec chunk가 non-parametric memory 역할을 해야 한다. command-response trajectory의 마지막 response가 pass/fail인지 판단하려면, generator가 그럴듯한 문장을 만드는 것이 아니라 관련 spec chunk를 근거로 final response entailment를 보여야 한다.

[Original Text/Data] → RAFT는 domain docs retrieval context와 answer generation을 결합해 open-book in-domain setting에 맞게 모델을 학습시키는 방향이다.

[Exact Interpretation] → RAFT의 논리 구조는 domain-specific RAG에 적응시키는 post-training recipe다.

[Detailed Explanation/Example] → 우리 문제에 대응하면, spec chunks + trajectory reasoning을 함께 넣고, 관련 chunk는 사용하고 distractor chunk는 무시하도록 학습 데이터를 만들어야 한다. 즉 "spec 없이 생성"이 아니라 "spec-grounded prompt + reasoning trace/evidence + answer" 방향이다.

[Original Text/Data] → RAGTruth는 RAG를 써도 retrieved contents에 대해 "unsupported or contradictory claims"가 생길 수 있다고 보고한다.

[Exact Interpretation] → retrieval은 hallucination 완전 방지 장치가 아니다.

[Detailed Explanation/Example] → 따라서 RAG/RAFT 방향을 채택해도 offline gate가 필요하다. gate는 train data 채택 전에 final response entailment, state transition consistency, contradiction/unsupported 여부, evidence provenance를 검사한다. 이 gate는 데이터 생성/검수 단계의 offline validation이며, inference-time runtime rule engine이 아니다.

## 논리 구조

<!-- 변경: 각 방법론의 bottom-up 논리 구조를 정리했다. 이유: seed, retrieval, validation의 역할을 혼동하지 않도록 하기 위함이다. -->

### Self-Instruct

[Original Text/Data] → [EXTERNAL KNOWLEDGE] Wang et al. (2023)는 Self-Instruct pipeline이 모델에서 instruction/input/output sample을 생성하고, invalid 또는 similar sample을 필터링한 뒤 원 모델 finetuning에 사용한다고 설명한다.

[Exact Interpretation] → Self-Instruct의 핵심 흐름은 seed tasks -> model-generated instruction/input/output -> filtering -> finetuning이다.

[Detailed Explanation/Example] → 이 구조의 장점은 human-written instruction data 의존도를 줄이고 instruction diversity를 늘리는 것이다. 한계는 명확하다. 필터링을 거친 generated text가 특정 폐쇄 명세의 참/거짓, 상태 전이, protocol invariant를 만족한다는 보증은 논리적으로 나오지 않는다. TCG/Opal SSD trajectory label에서는 "모델이 그럴듯하게 pass라고 썼다"와 "spec상 pass가 entail된다"가 다르다.

### RAG

[Original Text/Data] → [EXTERNAL KNOWLEDGE] Lewis et al. (2020)는 RAG를 pretrained parametric seq2seq model과 dense vector index의 non-parametric memory를 결합하는 language generation model로 제시한다.

[Exact Interpretation] → RAG의 핵심 흐름은 query/task -> retrieve source passages -> condition generation on retrieved passages -> answer이다.

[Detailed Explanation/Example] → 지식 intensive task에서 source grounding을 제공하는 방향이다. 우리 과제에서는 source passages가 일반 웹 문서나 Wikipedia가 아니라 TCG/Opal SSD spec chunk여야 한다. 따라서 accepted label은 "retrieved spec chunk가 final response를 지지한다"는 entailment를 가져야 하며, state transition도 동일 spec evidence와 충돌하면 안 된다.

### RAFT

[Original Text/Data] → [EXTERNAL KNOWLEDGE] Zhang et al. (2024)는 RAFT를 retrieved documents가 있는 open-book in-domain setting에서 answer 능력을 높이는 Retrieval Augmented FineTuning recipe로 제시한다.

[Exact Interpretation] → RAFT의 핵심 흐름은 question/task -> retrieved domain docs including relevant and distractor docs -> model learns to cite/use relevant docs and ignore distractors -> domain-specific RAG answer이다.

[Detailed Explanation/Example] → TCG/Opal SSD 문제에는 "trajectory + candidate final response + retrieved spec chunks"를 입력으로 두고, label이 spec chunk와 state transition에 의해 지지되는지 판정하는 형식이 맞다. RAFT는 "문서 없이 아무 text나 생성해도 된다"는 근거가 아니라, domain docs를 retrieval context로 결합해야 한다는 근거다.

### RAGTruth / Hallucination

[Original Text/Data] → [EXTERNAL KNOWLEDGE] Niu et al. (2024)는 RAG 환경에서도 retrieved contents에 대해 unsupported 또는 contradictory claim이 발생할 수 있음을 분석한다.

[Exact Interpretation] → source grounding을 넣어도 generation output은 신뢰 대상이 아니라 검증 대상이다.

[Detailed Explanation/Example] → synthetic data 생성에서는 generator output을 draft로 취급한다. accepted로 승격하려면 offline gate가 필요하다. gate는 최소한 (1) spec chunk provenance 존재, (2) final response entailment, (3) state transition consistency, (4) unsupported/contradictory claim 부재, (5) reject 사유 기록을 확인해야 한다.

## 과제 적용 정책

<!-- 변경: 논문 근거를 TCG/Opal SSD synthetic label 정책으로 변환했다. 이유: 연구 메모가 실제 데이터 채택 기준으로 이어지게 하기 위함이다. -->

[Original Text/Data] → 과제는 TCG/Opal SSD command-response trajectory의 마지막 response pass/fail 판정이다.

[Exact Interpretation] → label은 자유 생성 text가 아니라 closed spec-grounded judgment여야 한다.

[Detailed Explanation/Example] → Gemini/Codex는 generator로 draft를 만들 수 있다. 하지만 spec 없이 생성한 text는 train data로 채택할 수 없다. accepted synthetic sample의 데이터 흐름은 다음과 같아야 한다.

```text
TCG/Opal spec chunks
  -> spec-grounded prompt
  -> generator draft
  -> offline data gate:
       final response entailment check
       state transition consistency check
       unsupported/contradictory claim check
       provenance/reject reason logging
  -> accepted synthetic train data
```

[Original Text/Data] → runtime rule engine 금지, offline data gate/validation 가능.

[Exact Interpretation] → inference 시점에 규칙 엔진으로 pass/fail을 대신 판정하면 안 된다. 반면 학습 데이터 생성 단계에서 부정확한 synthetic sample을 거르는 validation은 허용된다.

[Detailed Explanation/Example] → 모델 학습용 sample을 만들 때 spec-grounded gate를 통과하지 못한 sample은 rejected로 남긴다. 통과한 sample만 train data로 채택한다. 이 정책은 Self-Instruct의 synthetic generation 가능성, RAG/RAFT의 source-grounded 방향, RAGTruth의 hallucination 경고를 동시에 만족한다.

## 최종 답

<!-- 변경: 결론을 단문으로 고정했다. 이유: 이후 문서나 발표에서 같은 주장을 반복할 때 해석 변동을 줄이기 위함이다. -->

[Original Text/Data] → "spec 없이 Codex/Gemini가 그냥 text를 만드는 게 가능한가?"

[Exact Interpretation] → text 생성 자체는 가능하지만, closed spec label로서의 validity는 보장되지 않는다.

[Detailed Explanation/Example] → 논문들이 지지하는 결론은 "generator는 draft를 만들 수 있다"이지, "spec 없이 만든 text를 TCG/Opal pass/fail train label로 채택할 수 있다"가 아니다. 최종 정책은 다음 한 문장이다.

**Spec 없이 생성한 Gemini/Codex text는 train data로 채택 불가하다. generator는 draft만 만들고, spec-grounded prompt와 offline gate를 통과한 sample만 synthetic accepted로 승격한다.**
