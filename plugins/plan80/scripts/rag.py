#!/usr/bin/env python3
"""Plan80 retrieval: BM25 over the planning rules and PRD. No embeddings, no network.

Splits each references/*.md file and docs/PRD.md into sections on '## ' headings,
expands the query with synonym groups, and returns the best-matching sections.

Usage:
    python3 scripts/rag.py "my kid is sick, what do I cut?" -k 3
"""
from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = sorted((ROOT / "references").glob("*.md")) + [ROOT / "docs" / "PRD.md"]

K1 = 1.5
B = 0.75
HEADING_WEIGHT = 3

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "be", "i", "my", "it", "this", "that", "what", "how", "do", "does", "if", "when",
    "should", "can", "about", "at", "by", "me", "we", "you", "so", "as",
}

# Synonym groups: a query word pulls in every word in its group.
SYNONYM_GROUPS = [
    {"sick", "ill", "illness", "fever", "cold"},
    {"kid", "kids", "child", "children", "school"},
    {"deadline", "due", "homework", "exam", "assignment"},
    {"trading", "trade", "market", "investing"},
    {"health", "workout", "exercise", "weight"},
    {"youtube", "video", "content", "github"},
    {"hours", "capacity", "time", "budget"},
    {"priority", "tier", "drop", "dropped", "conflict"},
    {"calendar", "calendars", "privacy", "hold"},
    {"rest", "recovery", "buffer", "slack"},
]


def stem(word: str) -> str:
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS]


SYNONYM_WEIGHT = 0.5


def expand(tokens: list[str]) -> list[tuple[str, float]]:
    """The user's own words count fully; synonyms count half, so they can't swamp the query."""
    out: list[tuple[str, float]] = [(t, 1.0) for t in tokens]
    for token in tokens:
        for group in SYNONYM_GROUPS:
            if token in {stem(w) for w in group}:
                out.extend((stem(w), SYNONYM_WEIGHT) for w in group if stem(w) != token)
    return out


def load_sections() -> list[dict]:
    sections = []
    for path in SOURCES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for part in re.split(r"(?m)^## ", text)[1:]:
            heading, _, body = part.partition("\n")
            sections.append({"doc": path.name, "heading": heading.strip(), "text": body.strip()})
    return sections


def search(query: str, k: int = 3, sections: list[dict] | None = None) -> list[dict]:
    sections = sections if sections is not None else load_sections()
    if not sections:
        return []
    docs = []
    for s in sections:
        heading_tokens = tokenize(s["heading"]) * HEADING_WEIGHT
        docs.append(heading_tokens + tokenize(s["text"]))

    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n
    df: Counter = Counter()
    for d in docs:
        df.update(set(d))

    query_terms = expand(tokenize(query))
    scored = []
    for section, doc in zip(sections, docs):
        tf = Counter(doc)
        score = 0.0
        for term, weight in query_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            norm = tf[term] * (K1 + 1) / (tf[term] + K1 * (1 - B + B * len(doc) / avgdl))
            score += weight * idf * norm
        if score > 0:
            scored.append((score, section))
    scored.sort(key=lambda x: -x[0])
    return [dict(section, score=round(score, 3)) for score, section in scored[:k]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=3)
    args = ap.parse_args()
    results = search(args.query, args.k)
    if not results:
        print("no matching sections")
        return 1
    for r in results:
        print(f"[{r['score']}] {r['doc']} :: {r['heading']}")
        print("   " + r["text"][:200].replace("\n", " ") + "...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
