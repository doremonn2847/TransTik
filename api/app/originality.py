"""Similarity guard: how much of a draft is copied word-for-word from a source transcript.

Plain arithmetic, no model: the share of the draft's 5-word sequences that also appear
in the source, plus the longest copied phrases.
"""
from __future__ import annotations

import re

N = 5


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower(), flags=re.UNICODE)


def check(draft: str, source: str) -> dict:
    d, s = _words(draft), _words(source)
    if len(d) < N or len(s) < N:
        return {"overlap": 0.0, "verdict": "original", "copied_phrases": [],
                "note": "Draft or source is too short for a meaningful comparison."}
    source_grams = {tuple(s[i:i + N]) for i in range(len(s) - N + 1)}
    hits = [tuple(d[i:i + N]) in source_grams for i in range(len(d) - N + 1)]
    overlap = sum(hits) / len(hits)

    phrases: list[str] = []
    i = 0
    while i < len(hits):
        if hits[i]:
            j = i
            while j + 1 < len(hits) and hits[j + 1]:
                j += 1
            phrases.append(" ".join(d[i:j + N]))
            i = j + 1
        else:
            i += 1
    phrases.sort(key=lambda p: -len(p.split()))

    verdict = "original" if overlap < 0.05 else "borrowed" if overlap < 0.20 else "too_similar"
    advice = {"original": "No meaningful word-for-word reuse.",
              "borrowed": "Some phrases are lifted from the source. Rewrite the listed phrases.",
              "too_similar": "This reads as a near-copy. Rewrite it in your own words before publishing."}[verdict]
    return {"overlap": round(overlap, 3), "verdict": verdict, "copied_phrases": phrases[:8], "note": advice}
