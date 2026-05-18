# Changed: add a helper to pre-download the LLM before evaluation.
# Why: downloading during Solver.__init__ may hit evaluator timeouts.
# Run this once on the server: python3 tools/download_model.py

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-download LLM for RAG solver")
    parser.add_argument(
        "--model",
        default=os.environ.get("RAG_MODEL", "Qwen/Qwen3.5-27B-FP8"),
        help="HuggingFace model ID",
    )
    args = parser.parse_args()

    print(f"Downloading {args.model} ...")
    from huggingface_hub import snapshot_download
    path = snapshot_download(args.model)
    print(f"Cached at: {path}")

    # Verify the model loads
    print("Verifying model loads ...")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )
    print(f"Model loaded: {model.dtype}, device={model.device}")
    print(f"Vocab size: {len(tokenizer)}")
    print("Done.")


if __name__ == "__main__":
    main()
