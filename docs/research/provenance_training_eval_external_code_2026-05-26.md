<!-- Changed: add provenance note for external verified training/eval code. -->
<!-- Why: internal manifest wrappers must be treated as custom preliminary code until compared against official sources. -->
# External Training/Eval Code Provenance Note

- 작성일: 2026-05-26 KST
- 작업 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team-cycle1-runtime-package-recovery-20260526-kst`
- 금지 root: `/Users/sinjeongmin/Desktop/SNU/26/26-1/DL/team`
- 범위: 코드 확보와 provenance 기록만 수행. 학습 실행, 의존성 설치, commit/push는 수행하지 않음.

## Structural Skeleton

- `third_party/hf_transformers_clm/`: Hugging Face Transformers CLM examples.
- `third_party/hf_trl_sft/`: Hugging Face TRL SFTTrainer script/doc snapshot.
- `third_party/hf_peft_sft_qlora/`: Hugging Face PEFT SFT/QLoRA examples.
- `third_party/gorilla_raft/`: Gorilla RAFT data generation/format/eval code snapshot.
- 내부 custom wrapper:
  - `tools/training/train_manifest_full.py`: `parse_args`, `build_messages`, `encode_example`, `run_training`, `run_dry_run`.
  - `tools/eval/eval_manifest_full_model.py`: `score_next_token_batch`, `binary_logprob`, `evaluate_rows`.

## External Sources

- [EXTERNAL KNOWLEDGE] Hugging Face. (2026). *Transformers* [Computer software]. GitHub. https://github.com/huggingface/transformers
  - URL: https://github.com/huggingface/transformers/tree/main/examples/pytorch/language-modeling
  - Pinned HEAD: `89c0c2edcf28d6511c707b7b108163403fa11b46`
  - License: Apache License 2.0.
  - Retrieved:
    - `LICENSE`
    - `examples/pytorch/language-modeling/README.md`
    - `examples/pytorch/language-modeling/requirements.txt`
    - `examples/pytorch/language-modeling/run_clm.py`
    - `examples/pytorch/language-modeling/run_clm_no_trainer.py`

- [EXTERNAL KNOWLEDGE] Hugging Face. (2026). *TRL* [Computer software]. GitHub. https://github.com/huggingface/trl
  - URL: https://github.com/huggingface/trl/tree/main/trl/scripts
  - Pinned HEAD: `a9993736c2250da0b3d2f206ec217f144b891e5a`
  - License: Apache License 2.0.
  - Retrieved:
    - `LICENSE`
    - `docs/source/sft_trainer.md`
    - `trl/scripts/sft.py`
    - `trl/scripts/utils.py`
    - `trl/scripts/_hf_argparser.py`

- [EXTERNAL KNOWLEDGE] Hugging Face. (2026). *PEFT* [Computer software]. GitHub. https://github.com/huggingface/peft
  - URL: https://github.com/huggingface/peft/tree/main/examples/sft
  - Pinned HEAD: `a106ff4c7061dd9e59609f88724e4770c3b37293`
  - License: Apache License 2.0.
  - Retrieved:
    - `LICENSE`
    - `examples/sft/README.md`
    - `examples/sft/requirements.txt`
    - `examples/sft/train.py`
    - `examples/sft/utils.py`
    - `examples/sft/run_peft.sh`
    - `examples/sft/run_peft_deepspeed.sh`
    - `examples/sft/run_peft_fsdp.sh`
    - `examples/sft/run_peft_qlora_deepspeed_stage3.sh`
    - `examples/sft/run_peft_qlora_fsdp.sh`
    - `examples/causal_language_modeling/requirements.txt`
    - `examples/causal_language_modeling/peft_lora_clm_accelerate_ds_zero3_offload.py`

- [EXTERNAL KNOWLEDGE] Patil, S. G. (2026). *Gorilla: RAFT code* [Computer software]. GitHub. https://github.com/ShishirPatil/gorilla/tree/main/raft
  - URL: https://github.com/ShishirPatil/gorilla/tree/main/raft
  - Pinned HEAD: `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`
  - License: Apache License 2.0.
  - Retrieved:
    - `LICENSE`
    - `raft/README.md`
    - `raft/requirements.txt`
    - `raft/raft.py`
    - `raft/raft_local.py`
    - `raft/format.py`
    - `raft/eval.py`
    - `raft/checkpointing.py`
    - `raft/client_utils.py`
    - `raft/env_config.py`
    - `raft/logconf.py`
    - `raft/logging.yaml`

- [EXTERNAL KNOWLEDGE] Zhang, T., Patil, S. G., Jain, N., Shen, S., Zaharia, M., Stoica, I., & Gonzalez, J. E. (2024). *RAFT: Adapting language model to domain specific RAG*. arXiv. https://arxiv.org/abs/2403.10131

## Candidate Assessment

1. Hugging Face Transformers `run_clm.py`

[Original Text/Data] `third_party/hf_transformers_clm/examples/pytorch/language-modeling/README.md:25` states that the first script set uses Trainer and the `no_trainer` scripts use Accelerate. `README.md:55-56` shows `--train_file` and `--validation_file`. `run_clm.py:174-189` accepts `train_file` and `validation_file` as text files, and `run_clm.py:232-239` asserts `csv`, `json`, or `txt`.
→ [Exact Interpretation] This is the most official baseline for causal LM full fine-tuning/eval-loss checks, but it is not SFT-specific.
→ [Detailed Explanation/Example] Convert public20 to a `text` JSONL or TXT where each row is the rendered prompt plus answer label. This route can evaluate loss/perplexity through official Trainer, but it does not natively mask prompt tokens or compute pass/fail validation metrics. A thin converter is needed; pass/fail metric evaluation should remain separate and clearly marked.

2. Hugging Face TRL `SFTTrainer`

[Original Text/Data] `third_party/hf_trl_sft/docs/source/sft_trainer.md:30-47` lists standard/conversational language modeling and prompt-completion formats. `sft_trainer.md:166-179` describes assistant-only and completion-only loss. `third_party/hf_trl_sft/trl/scripts/sft.py:66-119` loads a dataset and constructs `SFTTrainer`.
→ [Exact Interpretation] This is the best first-choice verified path for public20 SFT-style training because our task is input trajectory -> `pass`/`fail` completion, not raw CLM.
→ [Detailed Explanation/Example] Convert each public20 row from `{input,label,sample_id,split}` into prompt-completion JSONL:
  - `prompt`: `[{"role":"user","content": input}]`
  - `completion`: `[{"role":"assistant","content": label}]`
  Use public20 `train` as train and public20 `val` as validation/eval. Keep labels limited to `pass` and `fail`. The adapter should only perform format conversion and call official `SFTTrainer`; no custom optimizer/training loop should be added.

3. Hugging Face PEFT SFT/QLoRA examples

[Original Text/Data] `third_party/hf_peft_sft_qlora/examples/sft/README.md:4-8` describes single-GPU SFT with QLoRA and the gradient checkpointing note. `examples/sft/train.py:96-145` creates model/tokenizer, creates datasets, builds `SFTTrainer`, trains, and saves. `examples/sft/utils.py:48-80` loads Hub/local datasets and expects `train,test` split names.
→ [Exact Interpretation] This is the verified path for the 4B LoRA/QLoRA lane, but the stock example assumes `train,test`, not our `train,val` naming.
→ [Detailed Explanation/Example] Convert public20 `val` to a local dataset split named `test` only for the PEFT example interface, while documenting that it remains validation, not hidden test. Prefer `lora_target_modules="all-linear"` and 4-bit quantization for the 4B candidate. Avoid installing the full example requirements blindly because they include heavy optional packages such as Unsloth, flash-attn, deepspeed, and wandb.

4. Gorilla RAFT

[Original Text/Data] `third_party/gorilla_raft/raft/README.md:23-45` lists document input, output format, distractors, OpenAI/Azure/local generation arguments. `README.md:215-250` describes conversion to `completion` or `chat`. `raft/format.py:112-141` formats OpenAI completion/chat datasets from `instruction` and `cot_answer`.
→ [Exact Interpretation] RAFT is useful for the retrieval-augmented SFT candidate, but it is primarily a dataset-generation/formatting recipe, not a drop-in public20 trainer.
→ [Detailed Explanation/Example] For our RAFT-style lane, construct retrieved rulebook/spec context documents first, then generate or map `{question, answer, documents}`-style records into chat/prompt-completion SFT format. Do not call external OpenAI/Azure generation during this provenance step. RAFT dependencies and prompt generation should be evaluated separately from public20-only supervised training.

## Internal Wrapper Difference

[Original Text/Data] `tools/training/train_manifest_full.py:96-137` defines custom CLI args including `train-mode`, `last-n-layers`, `label-smoothing`, `min-tokenized-ratio`, and `torch-dtype`. `train_manifest_full.py:328-389` manually builds chat messages and masks prompt tokens with `IGNORE_INDEX`. `train_manifest_full.py:821-904` builds `TrainingArguments`, instantiates `Trainer`, trains, and saves a standalone model.
→ [Exact Interpretation] The current full/selective trainer is not an official script copy. It is a custom wrapper around Transformers Trainer with project-specific guards and freezing logic.
→ [Detailed Explanation/Example] Any result from this path, including the server seed11/public20 split result, must be recorded as `preliminary/custom wrapper result` until reproduced through TRL/Transformers/PEFT official examples plus a thin adapter.

[Original Text/Data] `tools/eval/eval_manifest_full_model.py:362-463` computes first-token `pass`/`fail` logits, normalizes them as a binary probability, and thresholds `p_fail`.
→ [Exact Interpretation] The current evaluator is custom metric code, not an official HF/TRL evaluator.
→ [Detailed Explanation/Example] Official scripts can provide eval loss/perplexity. Pass/fail accuracy, macro-F1, fail recall, pass recall, and calibration still require a thin metric adapter. That adapter should use official model loading/tokenization where possible and must be labeled separately from official training code.

[Original Text/Data] `docs/current_task.md:147-154` records 0.9B full FT epoch 5 validation no-go: accuracy `0.25`, fail recall `0.0`, pass recall `0.5`, confusion `TP=0 TN=1 FP=1 FN=2`.
→ [Exact Interpretation] This is not invalid evidence, but its provenance is custom-wrapper preliminary evidence.
→ [Detailed Explanation/Example] Future notes should write: `0.9B full FT epoch 5, seed/public20 validation split: preliminary/custom wrapper result; validation no-go; do not extend epoch 10/20 until official-code reproduction or replacement path exists.`

## Recommendation

1순위는 TRL `SFTTrainer` 공식 경로다.

[Original Text/Data] TRL supports prompt-completion and conversational formats, and completion-only/assistant-only loss is documented in `third_party/hf_trl_sft/docs/source/sft_trainer.md:30-47` and `:166-179`.
→ [Exact Interpretation] public20의 `{input -> pass/fail}` 구조와 가장 직접적으로 맞는다.
→ [Detailed Explanation/Example] 다음 작업은 adapter 한 개만 작성하는 것이다: public20 split JSONL을 TRL prompt-completion DatasetDict/JSONL로 변환하고, official `SFTTrainer`를 호출한다. 이 adapter는 데이터 변환, split 이름 매핑, run metadata 작성만 담당해야 한다.

## Dependency Notes

- Transformers CLM: `accelerate`, `torch`, `datasets`, `sentencepiece`, `protobuf`, `evaluate`, `scikit-learn`.
- TRL SFT: `trl`, `transformers`, `accelerate`, `datasets`; PEFT/quantization 사용 시 `peft`, `bitsandbytes`.
- PEFT QLoRA: `transformers`, `accelerate`, `peft`, `trl`, `datasets`, `bitsandbytes`; example requirements also list optional/heavy packages (`unsloth`, `deepspeed`, `flash-attn`, `wandb`, `xformers`), so minimal install spec should be written before server use.
- Gorilla RAFT: `datasets==2.16.1`, `openai==1.10.0`, `PyPDF2==3.0.1`, `transformers==4.37.2`, `langchain_*`, `python-dotenv`, `pyyaml`, `coloredlogs`, `mdc`, `pytest`. Its `requirements.txt` includes a shell-style `pip install torch...` line, so it should not be fed directly to `pip install -r` without review.

## Next Steps

1. Implement thin converter only: `public20 manifest -> TRL prompt-completion train/validation files`.
2. Add a small official-run launcher that calls TRL SFTTrainer or the copied TRL script without reimplementing training.
3. For 4B QLoRA, convert validation split name to `test` only at the PEFT example boundary and document it as validation.
4. Keep `tools/training/train_manifest_full.py` and `tools/eval/eval_manifest_full_model.py` as custom preliminary baselines until official-code reproduction is complete.
5. Do not run training until dependencies and server path are confirmed.
