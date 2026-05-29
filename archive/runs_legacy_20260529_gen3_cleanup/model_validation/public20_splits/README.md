# Public20 Model Validation Splits

이 디렉터리는 public20-only 모델 후보 검증용 deterministic train/val split artifact다.

- public20 labels는 local model-validation reference로만 사용한다.
- synthetic generation prompt, synthetic judge prompt, generated synthetic manifest target으로 사용하지 않는다.
- public20 `test` split은 만들지 않는다. test는 leaderboard hidden 평가다.
- 기본 split은 각 seed마다 `16 train / 4 val`이며 val은 `pass 2 / fail 2`다.

- generated seeds: `11, 29, 47`
