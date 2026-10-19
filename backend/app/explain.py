"""Human-readable explanation of an assessment.

Deterministic text is always produced. If ANTHROPIC_API_KEY is set, Claude rewrites it into a short
auditor-style rationale. The model is given the finished decision and cannot change it.
"""
from __future__ import annotations

import httpx

from .scoring import Assessment


def rule_based(a: Assessment, name: str) -> str:
    failed = [c for c in a.checks if c.status == "fail"]
    warned = [c for c in a.checks if c.status == "warn"]
    if a.approved:
        txt = (f"{name} scored {a.score}/100 and is approved for {a.verified_tonnes:,} tCO2e. "
               f"Satellite evidence shows {a.metrics['canopy_fraction'] * 100:.0f}% canopy cover with no clearing.")
        if a.verified_tonnes < a.claimed_tonnes:
            txt += (f" The claim of {a.claimed_tonnes:,} t exceeded what the land can hold, "
                    f"so credits were capped at {a.verified_tonnes:,} t.")
        elif warned:
            txt += " Minor caveats: " + "; ".join(c.label.lower() for c in warned) + "."
        return txt
    reasons = "; ".join(f"{c.label.lower()} ({c.value})" for c in failed) or "overall score below the approval threshold"
    return f"{name} scored {a.score}/100 and is rejected. Reasons: {reasons}. No credits can be minted."


async def explain(a: Assessment, name: str, api_key: str | None, model: str) -> tuple[str, str]:
    """Returns (text, author) where author is 'rules' or the model name."""
    base = rule_based(a, name)
    if not api_key:
        return base, "rules"
    payload = {
        "model": model,
        "max_tokens": 300,
        "system": ("You are a carbon-credit auditor. Rewrite the verdict below as 3 to 4 plain sentences for a "
                   "project developer. Do not change the decision, the score or any number. No markdown."),
        "messages": [{"role": "user", "content": f"Verdict: {base}\nChecks: " +
                      "; ".join(f"{c.label}: {c.status} ({c.value})" for c in a.checks)}],
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post("https://api.anthropic.com/v1/messages", json=payload,
                                  headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", [])).strip()
            if text:
                return text, model
    except Exception:
        pass  # fall back silently: the decision never depends on the LLM
    return base, "rules"
