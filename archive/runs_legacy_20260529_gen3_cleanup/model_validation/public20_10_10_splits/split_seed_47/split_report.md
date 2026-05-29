# Public20 Train/Val Split Report

- schema_version: `public20_train_val_split.v1`
- seed: `47`
- purpose: `public20_model_validation_only`
- hidden_test: `leaderboard`
- public20_test_split_created: `false`

## Warning

public20 labels are local model-validation references only; do not use these rows for synthetic generation prompts, synthetic judge prompts, or generated synthetic manifests

## Row Counts

- train: `10`
- val: `10`
- test: `0`

## Label Counts

- all: `{"fail": 10, "pass": 10}`
- train: `{"fail": 5, "pass": 5}`
- val: `{"fail": 5, "pass": 5}`

## Sample IDs

- train: `tc10, tc11, tc16, tc17, tc19, tc20, tc3, tc4, tc5, tc6`
- val: `tc1, tc12, tc13, tc14, tc15, tc18, tc2, tc7, tc8, tc9`
- test: ``

이 artifact는 public20-only 모델 후보 검증 전용이다. synthetic generation, synthetic judge, generated synthetic manifest target으로 사용하지 않는다.
