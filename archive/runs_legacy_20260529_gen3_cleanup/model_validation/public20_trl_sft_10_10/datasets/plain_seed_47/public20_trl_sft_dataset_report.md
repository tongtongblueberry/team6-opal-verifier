# public20 TRL SFT 데이터셋 변환 리포트

- 학습 core: `trl.SFTTrainer`
- 데이터 형식: public20 input/labels JSONL
- loss 의도: `SFTConfig(completion_only_loss=True)`
- custom training loop 사용: `false`
- public20 test split 생성: `false`
- retrieved spec context 사용: `false`

## Outputs

| split | rows | pass | fail | path |
|---|---:|---:|---:|---|
| train | 10 | 5 | 5 | `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_47/train.jsonl` |
| validation | 10 | 5 | 5 | `runs/model_validation/public20_trl_sft_10_10/datasets/plain_seed_47/validation.jsonl` |
