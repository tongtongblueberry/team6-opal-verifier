<!-- Changed: add metadata for imported Hugging Face PEFT SFT/QLoRA files. -->
<!-- Why: 4B LoRA/QLoRA candidates should be tied to verified PEFT examples and their license. -->
# Hugging Face PEFT SFT/QLoRA Provenance

- Source: https://github.com/huggingface/peft/tree/main/examples/sft
- Additional CLM example: https://github.com/huggingface/peft/tree/main/examples/causal_language_modeling
- Pinned HEAD: `a106ff4c7061dd9e59609f88724e4770c3b37293`
- License: Apache License 2.0, copied as `LICENSE`.
- Retrieved files:
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

Intended use: official 4B LoRA/QLoRA candidate path. The example expects `train,test` split names; public20 `val` must only be mapped to `test` at the example boundary and documented as validation.
