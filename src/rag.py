# Changed: implement RAG-Sequence marginalization (Lewis et al., 2020) for trajectory classification.
# Why: naive chunk concatenation ignores retrieval uncertainty. RAG-Sequence marginalizes
# p(y|x) over individually scored documents, weighted by retrieval probability.
#
# Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.
# Wei, J. et al. (2022). Chain-of-Thought Prompting Elicits Reasoning in LLMs. NeurIPS.
#
# RAG-Sequence:
#   p(y|x) ≈ Σ_{z ∈ top-K} p_η(z|x) · p_θ(y|x, z)
#
# For binary classification (pass/fail):
#   p("pass"|x) = Σ_i w_i · p("pass"|x, z_i)
#   w_i = softmax(BM25(q, z_i))   [retrieval weight]
#   p("pass"|x, z_i) = softmax(logit_pass, logit_fail)   [single forward pass per doc]
#
# Constraints (project.pdf p.10):
#   - Evaluation: no network, 3-hour limit, L40S 48GB
#   - Pre-cached: Qwen/Qwen3.5-{0.8B,2B,4B,9B}, Qwen/Qwen3.5-27B-FP8, etc.

from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

Json = dict[str, Any]


# ── BM25 Index ────────────────────────────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


@dataclass
class BM25Index:
    """BM25 ranking. score(q,d) = Σ IDF(qi) · tf_norm(qi,d)."""

    k1: float = 1.5
    b: float = 0.75
    docs: list[str] = field(default_factory=list)
    _doc_tokens: list[list[str]] = field(default_factory=list)
    _doc_lens: list[int] = field(default_factory=list)
    _avgdl: float = 0.0
    _N: int = 0
    _df: dict[str, int] = field(default_factory=dict)

    def build(self, documents: list[str]) -> None:
        self.docs = documents
        self._doc_tokens = [_tokenize(doc) for doc in documents]
        self._doc_lens = [len(t) for t in self._doc_tokens]
        self._N = len(documents)
        self._avgdl = sum(self._doc_lens) / max(self._N, 1)
        self._df = {}
        for tokens in self._doc_tokens:
            for term in set(tokens):
                self._df[term] = self._df.get(term, 0) + 1

    def query(self, text: str, top_k: int = 5) -> list[tuple[int, float]]:
        """Return (doc_index, BM25_score) pairs."""
        qtokens = _tokenize(text)
        if not qtokens or not self.docs:
            return []
        scored = []
        for i, dtokens in enumerate(self._doc_tokens):
            s = self._score(qtokens, dtokens, self._doc_lens[i])
            if s > 0:
                scored.append((i, s))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def _score(self, qtokens: list[str], dtokens: list[str], dl: int) -> float:
        tf = Counter(dtokens)
        s = 0.0
        for qt in set(qtokens):
            nq = self._df.get(qt, 0)
            if nq == 0:
                continue
            idf = math.log((self._N - nq + 0.5) / (nq + 0.5) + 1.0)
            f = tf.get(qt, 0)
            s += idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * dl / self._avgdl))
        return s


# ── Spec Chunking ─────────────────────────────────────────────────────────────


@dataclass
class SpecChunk:
    text: str
    source_file: str
    chunk_index: int


def chunk_spec_documents(spec_root: Path, chunk_size: int = 1000, overlap: int = 200) -> list[SpecChunk]:
    """Load, chunk, and add contextual prefix to spec files.

    Changed: prepend source file path as context prefix to each chunk.
    Why: Anthropic (2024) "Contextual Retrieval" showed that adding document
    context to chunks significantly improves BM25 recall. The file path
    contains section names (e.g., "opal/locking_table.txt") that are
    critical keywords for retrieval.
    """
    chunks: list[SpecChunk] = []
    if not spec_root.exists():
        return chunks
    # Changed: load section titles if available, for richer context prefix.
    # Why: section_title.json maps filenames to human-readable titles.
    titles: dict[str, str] = {}
    for candidate in (spec_root / "section_title.json", spec_root.parent / "section_title.json"):
        if candidate.exists():
            try:
                import json as _json
                titles = _json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                pass
            break
    for path in sorted(spec_root.rglob("*.txt")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(spec_root))
        stem = path.stem
        title = str(titles.get(rel) or titles.get(stem) or "")
        # Changed: build contextual prefix from file path + title.
        # Why: "Source: opal/locking_table.txt | Locking Table Specification"
        # adds keywords like "locking", "table" that BM25 can match.
        prefix = f"[Source: {rel}]"
        if title:
            prefix += f" [{title}]"
        if len(text) <= chunk_size:
            if text.strip():
                contextualized = f"{prefix}\n{text.strip()}"
                chunks.append(SpecChunk(text=contextualized, source_file=rel, chunk_index=0))
        else:
            for i, piece in enumerate(_split_text(text, chunk_size, overlap)):
                contextualized = f"{prefix}\n{piece}"
                chunks.append(SpecChunk(text=contextualized, source_file=rel, chunk_index=i))
    logger.info("Chunked spec into %d chunks (with contextual prefix)", len(chunks))
    return chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 > chunk_size and current:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n" + para if overlap > 0 and len(current) > overlap else para
        else:
            current = current + "\n" + para if current else para
    if current.strip():
        chunks.append(current.strip())
    if not chunks and text.strip():
        chunks = [text.strip()]
    return chunks


# ── Query Extraction ──────────────────────────────────────────────────────────


def _extract_field(record: Json, name: str) -> str:
    for key in (name, name.lower(), name.capitalize()):
        val = record.get(key)
        if isinstance(val, dict):
            return str(val.get("Name", val.get("name", val)))
        elif val is not None:
            return str(val)
    return ""


def extract_query(records: list[Json], trace: list[Json] | None = None) -> str:
    if not records:
        return ""
    final = records[-1] if isinstance(records[-1], dict) else {}
    cmd = final.get("input", {}) if isinstance(final, dict) else {}
    out = final.get("output", {}) if isinstance(final, dict) else {}
    parts: list[str] = []
    for key in ("method", "Method"):
        val = cmd.get(key)
        if isinstance(val, dict):
            n = val.get("Name", val.get("name", ""))
            if n:
                parts.append(str(n))
                break
        elif val:
            parts.append(str(val))
            break
    for key in ("invokingID", "InvokingID"):
        val = cmd.get(key)
        if isinstance(val, dict):
            n = val.get("Name", val.get("name", ""))
            if n:
                parts.append(str(n))
                break
        elif val:
            parts.append(str(val))
            break
    for key in ("status", "Status"):
        val = out.get(key)
        if isinstance(val, dict):
            n = val.get("Name", val.get("name", ""))
            if n:
                parts.append(str(n))
                break
        elif val:
            parts.append(str(val))
            break
    status_str = " ".join(parts).lower()
    if "notauthorized" in status_str or "not_authorized" in status_str:
        parts.extend(["authority", "authentication", "NOT_AUTHORIZED", "session", "ACL"])
    elif "invalidparameter" in status_str or "invalid_parameter" in status_str:
        parts.extend(["parameter", "validation", "INVALID_PARAMETER", "value", "range"])
    elif "fail" in status_str:
        parts.extend(["error", "failure", "FAIL", "status"])
    if trace:
        for event in trace[-3:]:
            detail = event.get("detail", "")
            if detail:
                parts.extend(re.findall(r"[a-zA-Z_]{4,}", detail))
    return " ".join(parts)


# Changed: add query expansion + RRF for higher BM25 recall.
# Why: Raudaschl (2024, Haystack) showed query expansion raises recall ~17% for BM25.
# RAG-Fusion (Rackauckas, 2024) uses multiple query variants + reciprocal rank fusion.

_SYNONYMS: dict[str, list[str]] = {
    "startsession": ["session", "open", "authentication", "HostChallenge"],
    "endsession": ["session", "close", "terminate"],
    "get": ["read", "retrieve", "column", "table", "Cellblock"],
    "set": ["write", "modify", "update", "column", "Values"],
    "activate": ["enable", "SP", "SecurityProvider", "Locking"],
    "genkey": ["key", "generation", "K_AES_256", "media", "encryption"],
    "properties": ["discovery", "SessionManager", "MaxMethods"],
    "read": ["data", "LBA", "range", "sector", "plaintext"],
    "write": ["data", "LBA", "range", "sector", "pattern"],
    "notauthorized": ["authority", "ACL", "permission", "credential", "PIN"],
    "invalidparameter": ["parameter", "range", "column", "value", "Cellblock"],
    "c_pin": ["credential", "PIN", "password", "secret"],
    "locking": ["range", "lock", "ReadLocked", "WriteLocked"],
    "authority": ["admin", "user", "ACL", "permission", "Enabled"],
    "mbrcontrol": ["MBR", "shadow", "boot", "DoneOnReset"],
}


def expand_queries(primary_query: str, records: list[Json]) -> list[str]:
    """Generate expanded query variants for multi-query BM25 retrieval."""
    queries = [primary_query]
    tokens = primary_query.lower().split()
    # Variant 1: domain synonym expansion
    expanded = list(tokens)
    for t in tokens:
        expanded.extend(_SYNONYMS.get(t, [])[:3])
    if len(expanded) > len(tokens):
        queries.append(" ".join(expanded))
    # Variant 2: context from preceding steps
    if len(records) >= 2:
        ctx: list[str] = []
        for step in records[-3:-1]:
            if not isinstance(step, dict):
                continue
            c = step.get("input", {})
            m = _extract_field(c, "Method") or _extract_field(c, "method")
            inv = _extract_field(c, "InvokingID") or _extract_field(c, "invokingID")
            if m:
                ctx.append(m)
            if inv:
                ctx.append(inv)
        if ctx:
            queries.append(primary_query + " " + " ".join(ctx))
    return queries


def rrf_fuse(ranked_lists: list[list[tuple[int, float]]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion. RRF(d) = Σ 1/(k + rank_i).

    Cormack, G., Clarke, C., & Buettcher, S. (2009). Reciprocal Rank Fusion
    outperforms Condorcet and individual rank learning methods. SIGIR.
    """
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (doc_idx, _bm25) in enumerate(ranked):
            scores[doc_idx] = scores.get(doc_idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


# ── Trajectory Formatting ─────────────────────────────────────────────────────


def format_trajectory_context(records: list[Json], max_steps: int = 15) -> str:
    """Format trajectory with inferred protocol state summary.

    Changed: add protocol state summary (session, auth, operations) above the step list.
    Why: project.pdf p.2 says "the model must infer the current SSD state from the
    previous command-response history". Explicit state summary helps the LLM reason.
    """
    if not records:
        return "Empty trajectory"
    visible = records[-max_steps:] if len(records) > max_steps else records
    offset = len(records) - len(visible)

    # Changed: infer protocol state from trajectory for LLM context.
    # Why: Zheng et al. (2023, "Judging LLM-as-a-Judge") showed structured context improves accuracy.
    sessions_opened = 0
    authenticated = False
    operations: list[str] = []
    for step in records[:-1]:
        if not isinstance(step, dict):
            continue
        cmd = step.get("input", {})
        out = step.get("output", {})
        method = (_extract_field(cmd, "Method") or _extract_field(cmd, "method")).lower()
        status = (_extract_field(out, "Status") or _extract_field(out, "status")).lower()
        if status != "success":
            continue
        if method == "startsession":
            sessions_opened += 1
            # Check for authentication indicators
            cmd_str = json.dumps(cmd, default=str).lower()
            if "hostsigningauthority" in cmd_str or "hostchallenge" in cmd_str:
                authenticated = True
        elif method == "endsession":
            sessions_opened = max(0, sessions_opened - 1)
        elif method in ("set", "get", "activate", "genkey", "read", "write"):
            inv = _extract_field(cmd, "InvokingID") or _extract_field(cmd, "invokingID")
            operations.append(f"{method}({inv})")

    state_lines = ["## Inferred Protocol State"]
    state_lines.append(f"- Sessions opened: {sessions_opened}")
    state_lines.append(f"- Authenticated: {'yes' if authenticated else 'no'}")
    if operations:
        state_lines.append(f"- Prior operations: {', '.join(operations[-5:])}")

    lines = state_lines + ["", "## Step History"]
    if offset > 0:
        lines.append(f"[... {offset} earlier steps omitted ...]")
    for i, step in enumerate(visible):
        if not isinstance(step, dict):
            continue
        cmd = step.get("input", {}) if isinstance(step, dict) else {}
        out = step.get("output", {}) if isinstance(step, dict) else {}
        method = _extract_field(cmd, "Method") or _extract_field(cmd, "method")
        inv = _extract_field(cmd, "InvokingID") or _extract_field(cmd, "invokingID")
        st = _extract_field(out, "Status") or _extract_field(out, "status")
        abs_i = offset + i
        prefix = "[FINAL] " if abs_i == len(records) - 1 else ""
        lines.append(f"{prefix}Step {abs_i}: {method}({inv}) -> {st}")
    return "\n".join(lines)


# ── Prompt Templates ──────────────────────────────────────────────────────────

# Changed: improve system prompt with explicit judgment criteria from project.pdf.
# Why: Kadavath et al. (2022) showed explicit rubrics improve LLM calibration.
_SYSTEM_PROMPT = """\
You are a TCG Storage/Opal protocol compliance checker. Determine if the FINAL \
response in an SSD command-response trajectory is consistent with the specification.

Judgment criteria:
1. SUCCESS is PASS if the operation should succeed given the current state \
(correct session, authentication, permissions, parameters).
2. SUCCESS is FAIL if the operation should have been rejected \
(e.g., unauthenticated access to a protected object, writing to a locked range).
3. An error (NOT_AUTHORIZED, INVALID_PARAMETER, FAIL) is PASS if the specification \
requires that error for the given state (e.g., no session, wrong credentials, \
locked range, invalid column).
4. An error is FAIL if the operation should have succeeded \
(e.g., valid credentials but got NOT_AUTHORIZED, valid parameters but got INVALID_PARAMETER).

Key state factors:
- Is there an active session?
- Is the host authenticated with the required authority?
- Is the target locking range locked or unlocked?
- Are the command parameters valid (column ranges, values)?

When uncertain, lean towards "pass" — most error responses are intentional.
Answer with EXACTLY one word: pass or fail"""

# Changed: separate template for per-document scoring (RAG-Sequence).
# Why: each document z_i gets its own prompt for independent p(y|x, z_i) scoring.
_SINGLE_DOC_TEMPLATE = """\
## Specification Excerpt
{spec_chunk}

## Trajectory
{trajectory_summary}

## Final Command
```json
{final_command}
```

## Final Response
```json
{final_response}
```

Is the "{status}" response for {method} on {invoking} consistent with the specification?
Answer: pass or fail"""

_DEFAULT_MODEL = "Qwen/Qwen3.5-27B-FP8"


# ── LLM Judge (RAG-Sequence marginalization) ──────────────────────────────────


class LLMJudge:
    """Implements RAG-Sequence marginalization for binary classification.

    Lewis et al. (2020): p(y|x) ≈ Σ_z p_η(z|x) · p_θ(y|x, z)

    For each retrieved document z_i:
      1. Build prompt with (trajectory, z_i)
      2. Single forward pass → logits at generation position
      3. Extract p("pass"|x, z_i) from softmax over pass/fail token logits
    Then marginalize with BM25 retrieval weights.
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_MODEL,
        device: str = "auto",
        max_new_tokens: int = 4096,
    ) -> None:
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.model: Any = None
        self.tokenizer: Any = None
        self._pass_token_ids: list[int] = []
        self._fail_token_ids: list[int] = []
        self._load_model(device)

    def _load_model(self, device: str) -> None:
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info("Loading LLM %s ...", self.model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name, trust_remote_code=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype="auto",
                device_map=device,
                trust_remote_code=True,
            )
            self.model.eval()
            self._cache_token_ids()
            logger.info("LLM loaded. pass_ids=%s fail_ids=%s",
                        self._pass_token_ids, self._fail_token_ids)
        except Exception as exc:
            logger.warning("Failed to load LLM: %s — disabled.", exc)
            self.model = None
            self.tokenizer = None

    def _cache_token_ids(self) -> None:
        """Cache token IDs for 'pass' and 'fail' answer tokens."""
        pass_ids: set[int] = set()
        fail_ids: set[int] = set()
        for word in ["pass", "Pass", "PASS", " pass", " Pass"]:
            ids = self.tokenizer.encode(word, add_special_tokens=False)
            if ids:
                pass_ids.add(ids[0])
        for word in ["fail", "Fail", "FAIL", " fail", " Fail"]:
            ids = self.tokenizer.encode(word, add_special_tokens=False)
            if ids:
                fail_ids.add(ids[0])
        self._pass_token_ids = sorted(pass_ids)
        self._fail_token_ids = sorted(fail_ids)

    @property
    def available(self) -> bool:
        return (
            self.model is not None
            and self.tokenizer is not None
            and bool(self._pass_token_ids)
            and bool(self._fail_token_ids)
        )

    # ── Core: per-document logit scoring ──────────────────────────────────

    def _build_prompt(self, records: list[Json], spec_chunk: str) -> str:
        """Build a prompt for scoring one (trajectory, document) pair."""
        final = records[-1] if records else {}
        cmd = final.get("input", {})
        out = final.get("output", {})
        method = _extract_field(cmd, "Method") or _extract_field(cmd, "method") or "unknown"
        inv = _extract_field(cmd, "InvokingID") or _extract_field(cmd, "invokingID") or "unknown"
        status = _extract_field(out, "Status") or _extract_field(out, "status") or "unknown"

        user_msg = _SINGLE_DOC_TEMPLATE.format(
            spec_chunk=spec_chunk,
            trajectory_summary=format_trajectory_context(records),
            final_command=json.dumps(cmd, indent=2, default=str)[:3000],
            final_response=json.dumps(out, indent=2, default=str)[:3000],
            status=status,
            method=method,
            invoking=inv,
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        # Changed: disable thinking for logit-based scoring.
        # Why: we need the first generated token to be "pass"/"fail", not "<think>".
        try:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )

    def score_document(self, records: list[Json], spec_chunk: str) -> tuple[float, float]:
        """Compute p(pass|x, z) and p(fail|x, z) via single forward pass.

        Returns (p_pass, p_fail) from softmax over answer token logits.
        """
        import torch

        prompt = self._build_prompt(records, spec_chunk)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model(**inputs)

        # Changed: extract logits at the last position (where generation starts).
        # Why: this is where the model predicts the first response token = "pass" or "fail".
        last_logits = outputs.logits[0, -1, :]

        pass_logit = max(last_logits[tid].item() for tid in self._pass_token_ids)
        fail_logit = max(last_logits[tid].item() for tid in self._fail_token_ids)

        # Softmax over just pass/fail
        max_logit = max(pass_logit, fail_logit)
        exp_pass = math.exp(pass_logit - max_logit)
        exp_fail = math.exp(fail_logit - max_logit)
        total = exp_pass + exp_fail
        return exp_pass / total, exp_fail / total

    # ── RAG-Sequence marginalization ──────────────────────────────────────

    def judge_marginalized(
        self,
        records: list[Json],
        spec_chunks: list[str],
        bm25_scores: list[float],
    ) -> str:
        """RAG-Sequence: p(y|x) ≈ Σ_z p_η(z|x) · p_θ(y|x, z).

        Args:
            records: trajectory records
            spec_chunks: list of retrieved spec texts
            bm25_scores: BM25 scores for each chunk (used as p_η(z|x))

        Returns:
            "pass" or "fail"
        """
        if not self.available or not spec_chunks:
            return "pass"

        # Changed: softmax over BM25 scores → retrieval weights p_η(z_i|x).
        # Why: Lewis et al. use p_η(z|x) = softmax(MIPS score). We substitute BM25 score.
        max_score = max(bm25_scores) if bm25_scores else 0.0
        exp_scores = [math.exp(s - max_score) for s in bm25_scores]
        total_exp = sum(exp_scores)
        weights = [e / total_exp for e in exp_scores]

        # Changed: score each document independently, then marginalize.
        # Why: this is the core RAG-Sequence formula. Each z_i contributes
        # p_θ(y|x, z_i) weighted by p_η(z_i|x).
        p_pass_marginal = 0.0
        p_fail_marginal = 0.0
        for chunk_text, w_i in zip(spec_chunks, weights):
            p_pass_i, p_fail_i = self.score_document(records, chunk_text)
            p_pass_marginal += w_i * p_pass_i
            p_fail_marginal += w_i * p_fail_i
            logger.debug("  doc w=%.3f p_pass=%.3f p_fail=%.3f", w_i, p_pass_i, p_fail_i)

        logger.info("Marginalized: p_pass=%.4f p_fail=%.4f", p_pass_marginal, p_fail_marginal)

        # Changed: use asymmetric threshold instead of 0.5.
        # Why: the rule engine already defaults to "pass" for these cases. The LLM
        # should only override to "fail" with sufficient confidence to avoid regression.
        # Threshold 0.6 means: LLM needs >60% confidence to flip to "fail".
        # This is conservative and can be tuned based on server validation.
        fail_threshold = float(os.environ.get("RAG_FAIL_THRESHOLD", "0.6"))
        if p_fail_marginal > fail_threshold:
            return "fail"
        return "pass"

    # ── Fallback: generation-based judge (with thinking mode) ─────────────

    def judge_generate(self, records: list[Json], spec_chunks: list[str]) -> str:
        """Fallback: concatenate chunks, generate with thinking mode, parse answer."""
        if not self.available:
            return "pass"
        import torch

        final = records[-1] if records else {}
        cmd = final.get("input", {})
        out = final.get("output", {})
        method = _extract_field(cmd, "Method") or _extract_field(cmd, "method") or "unknown"
        inv = _extract_field(cmd, "InvokingID") or _extract_field(cmd, "invokingID") or "unknown"
        status = _extract_field(out, "Status") or _extract_field(out, "status") or "unknown"

        spec_context = "\n\n---\n\n".join(spec_chunks[:8]) if spec_chunks else "None available."
        user_msg = _SINGLE_DOC_TEMPLATE.format(
            spec_chunk=spec_context,
            trajectory_summary=format_trajectory_context(records),
            final_command=json.dumps(cmd, indent=2, default=str)[:3000],
            final_response=json.dumps(out, indent=2, default=str)[:3000],
            status=status,
            method=method,
            invoking=inv,
        )
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
        try:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
                enable_thinking=True,
            )
        except TypeError:
            text = self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs, max_new_tokens=self.max_new_tokens,
                do_sample=False, temperature=None, top_p=None,
            )
        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        response = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip().lower()
        words = response.split()
        tail = words[-5:] if len(words) >= 5 else words
        if "fail" in tail:
            return "fail"
        if "pass" in tail:
            return "pass"
        head = words[:5] if len(words) >= 5 else words
        if "fail" in head:
            return "fail"
        if "pass" in head:
            return "pass"
        logger.warning("Generation ambiguous: %r — defaulting to pass", response[-200:])
        return "pass"


# ── RAG Solver ────────────────────────────────────────────────────────────────


class RAGSolver:
    """RAG-Sequence solver for trajectory pass/fail classification.

    Lewis et al. (2020): p(y|x) ≈ Σ_{z ∈ top-K} p_η(z|x) · p_θ(y|x, z)

    - Retriever: BM25 over spec chunks (FEVER ablation: BM25 > DPR for fact verification)
    - Generator: Qwen3.5-27B-FP8 (pre-cached, project.pdf p.10)
    - Scoring: per-document logit marginalization (fast: K forward passes per case)
    """

    def __init__(
        self,
        spec_root: Path | None = None,
        model_name: str | None = None,
        chunk_size: int = 1000,
        overlap: int = 200,
        top_k: int = 8,
    ) -> None:
        self.top_k = top_k
        self.chunks: list[SpecChunk] = []
        self.index = BM25Index()
        self.llm: LLMJudge | None = None

        if spec_root is None:
            spec_root = Path(os.environ.get(
                "RAG_SPEC_ROOT", "/dl2026/skeleton/artifacts/documents",
            ))
        if model_name is None:
            model_name = os.environ.get("RAG_MODEL", _DEFAULT_MODEL)

        if spec_root.exists():
            self.chunks = chunk_spec_documents(spec_root, chunk_size, overlap)
            if self.chunks:
                self.index.build([c.text for c in self.chunks])
                logger.info("BM25 index ready: %d chunks", len(self.chunks))
        else:
            logger.warning("Spec root %s not found — RAG disabled", spec_root)

        try:
            self.llm = LLMJudge(model_name=model_name)
            if not self.llm.available:
                self.llm = None
        except Exception as exc:
            logger.warning("LLM init failed: %s", exc)
            self.llm = None

    @property
    def available(self) -> bool:
        return bool(self.chunks) and self.llm is not None and self.llm.available

    def predict(self, records: list[Json], trace: list[Json] | None = None) -> str:
        """Predict pass/fail using RAG-Sequence marginalization with query expansion + RRF."""
        if not self.available:
            return "pass"

        primary_query = extract_query(records, trace)
        if not primary_query:
            return "pass"

        # Changed: multi-query retrieval with RRF fusion (Cycle 1).
        # Why: query expansion + RRF raises BM25 recall ~17% (Haystack 2024, RAG-Fusion).
        queries = expand_queries(primary_query, records)
        ranked_lists = [self.index.query(q, self.top_k * 2) for q in queries]
        fused = rrf_fuse(ranked_lists)
        top_results = fused[: self.top_k]
        if not top_results:
            return "pass"

        # Changed: retrieve original BM25 scores from primary query for marginalization weights.
        # Why: RRF gives rank-based scores; we need BM25 scores for p_η(z|x) softmax.
        primary_scores = {idx: score for idx, score in ranked_lists[0]}
        spec_texts: list[str] = []
        bm25_scores: list[float] = []
        for idx, _rrf_score in top_results:
            if idx < len(self.chunks):
                spec_texts.append(self.chunks[idx].text)
                bm25_scores.append(primary_scores.get(idx, 0.1))

        if not spec_texts:
            return "pass"

        return self.llm.judge_marginalized(records, spec_texts, bm25_scores)
