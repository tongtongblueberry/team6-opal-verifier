<!-- Added: public20 label 파일의 사용 범위를 명확히 제한하기 위해 작성했다. -->

# Public20 Local Reference

- `public20_input.jsonl`: 서버의 public20 input-only reference를 로컬로 복사한 파일이다.
- `public20_labels.local.jsonl`: local 검증, dimension 분포 비교, held-out metric 계산에만 쓰는 label reference다.

`public20_labels.local.jsonl`은 Self-Instruct generation prompt, judge prompt, training manifest 입력에 넣지 않는다. Public20 input은 데이터 구조와 dimension reference로만 사용한다.
