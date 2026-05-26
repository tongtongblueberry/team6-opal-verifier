<!-- Changed: add metadata for imported Hugging Face TRL SFT files. -->
<!-- Why: public20 SFT reproduction should use a pinned official source rather than internal trainer logic. -->
# Hugging Face TRL SFT Provenance

- Source: https://github.com/huggingface/trl/tree/main/trl/scripts
- Documentation: https://huggingface.co/docs/trl
- Pinned HEAD: `a9993736c2250da0b3d2f206ec217f144b891e5a`
- License: Apache License 2.0, copied as `LICENSE`.
- Retrieved files:
  - `docs/source/sft_trainer.md`
  - `trl/scripts/sft.py`
  - `trl/scripts/utils.py`
  - `trl/scripts/_hf_argparser.py`

Intended use: first-choice official SFT path. public20 should be converted to prompt-completion or conversational prompt-completion format, then passed to `SFTTrainer` through a thin adapter.
