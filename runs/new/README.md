# Self-Instruct Output-First Pipeline v2

## 접근법

Self-Instruct (Wang et al. 2023 ACL) output-first 적용:
- 우리 task는 classification (pass/fail) → output-first 사용
- 마지막 record + label을 먼저 생성, 앞쪽 trajectory를 이후 생성
- 생성 모델: Qwen 0.9B (서버, Self-Instruct는 same model로 생성+학습)
- 86 spec rules 기반으로 rule 선택 → label 결정 → LM 생성
- 기존 7단계 필터링 파이프라인 재사용

## 파일 구조

```
runs/new/
├── README.md              # 이 문서
├── generate_server.py     # 서버 생성 스크립트 (Qwen 0.9B)
├── watch.sh               # 로컬 watcher (증분 pull + 필터링)
├── latest_run.txt         # 최신 서버 run 경로 포인터
└── run_YYYYMMDD_HHMMSS/   # 서버 생성 출력 (자동 생성)
    ├── raw_outputs.jsonl
    └── generation_requests.jsonl
```

## 실행

### 서버에서 생성
```bash
ssh team6
cd /workspace/sinjeongmin_opal_verifier/repo
python3 runs/new/generate_server.py \
  --model Qwen/Qwen3.5-0.8B \
  --num-per-rule 5 \
  --max-new-tokens 4096 \
  --temperature 0.7
```

### 로컬에서 watcher
```bash
bash runs/new/watch.sh
```

### 로컬 one-shot 필터링 (watcher 없이)
```bash
WATCH_COMBINE_ONCE=1 bash runs/new/watch.sh
```

## 필터링 파이프라인 (7단계)

1. Parse 유효성 (`parse_self_instruct_outputs.py`)
2. Final-response 불변식 (`self_instruct_invariants.py`)
3. 중복 제거 ROUGE-L 0.7 (`dedup_self_instruct_candidates.py`)
4. LLM Judge 독립 재판정 (`filter_self_instruct_judge.py`)
5. Adversarial rule-book gate (`adversarial_rulebook_quality_gate.py`)
6. Public20 정량 비교 (watcher 내장)
7. 정성적 감사 Gate A (`audit_self_instruct_quality.py`)
