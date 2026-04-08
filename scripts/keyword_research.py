#!/usr/bin/env python3
"""
Weekly keyword researcher for Towing Costs By City.
Uses Claude API to generate 20 new towing cost keywords,
scores them, and appends them to keywords.txt in priority order.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
KEYWORDS_FILE = REPO_ROOT / "scripts" / "keywords.txt"

SYSTEM_PROMPT = """You are a local SEO keyword researcher specializing in automotive and towing services. Generate 20 practical towing cost keywords for a support site.

Score each keyword across four dimensions:
1. Search demand likelihood (1-10)
2. Intent strength (1-10)
3. Low competition likelihood (1-10)
4. Canonical support value (1-10): does this topic strengthen the main Tow With The Flow site through a useful supporting page?

Average the four scores and round to the nearest integer for the final score.

Prioritize:
- towing cost scenarios with strong commercial intent
- cost modifiers that materially change price, like distance, after-hours, vehicle type, accident, no insurance
- broad support topics that can canonically reinforce the main site

Avoid:
- duplicate city pages that already exist
- weak keyword variants with little standalone value
- vague "near me" phrases unless paired with a strong cost angle

Return only a JSON array of 20 objects using exactly these keys: "score" and "keyword"."""


def strip_score_prefix(text: str) -> str:
    clean = text.strip()
    if clean.startswith("[") and "]" in clean:
        close = clean.find("]")
        maybe_score = clean[1:close]
        if maybe_score.isdigit():
            return clean[close + 1:].strip()
    return clean


def load_existing_keywords() -> set[str]:
    """Load all existing keywords (done or pending) from keywords.txt."""
    if not KEYWORDS_FILE.exists():
        return set()
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    existing = set()
    for line in lines:
        clean = line.split("# DONE")[0].split("#")[0].strip()
        if clean:
            existing.add(strip_score_prefix(clean).lower())
    return existing


def generate_new_keywords(existing: set[str]) -> list[tuple[int, str]]:
    """Use Claude to generate 20 scored towing cost keywords."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)

    existing_sample = "\n".join(list(existing)[:30])

    user_prompt = (
        "Generate 20 new towing cost keywords for a support SEO site. "
        "Mix of scenario-based, vehicle-specific, distance-based, insurance-based, and after-hours towing cost queries. "
        "Favor keywords that a smaller site could plausibly rank for and that can support a canonical strategy back to the main site.\n\n"
        f"Existing keywords to avoid duplicating:\n{existing_sample}\n\n"
        "Return only the JSON array."
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    try:
        import json
        payload = json.loads(raw)
    except Exception as exc:
        sys.exit(f"ERROR: Could not parse Claude response as JSON: {exc}")

    results: list[tuple[int, str]] = []
    for item in payload:
        if not isinstance(item, dict) or "keyword" not in item:
            continue
        keyword = str(item["keyword"]).strip()
        try:
            score = int(item.get("score", 5))
        except (TypeError, ValueError):
            score = 5
        score = max(1, min(10, score))
        if keyword:
            results.append((score, keyword))
    return results


def append_new_keywords(new_keywords: list[tuple[int, str]], existing: set[str]) -> int:
    """Append new scored keywords to keywords.txt, skipping duplicates."""
    added = 0
    new_keywords = sorted(new_keywords, key=lambda item: item[0], reverse=True)
    with KEYWORDS_FILE.open("a", encoding="utf-8") as f:
        for score, kw in new_keywords:
            bare = kw.lower()
            if bare not in existing:
                f.write(f"[{score}] {kw}\n")
                existing.add(bare)
                added += 1
    return added


def main():
    print("Loading existing keywords...")
    existing = load_existing_keywords()
    print(f"Found {len(existing)} existing keywords.")

    print("Generating new keywords via Claude API...")
    new_keywords = generate_new_keywords(existing)
    print(f"Generated {len(new_keywords)} candidate keywords.")

    added = append_new_keywords(new_keywords, existing)
    print(f"Added {added} new unique keywords to {KEYWORDS_FILE}.")


if __name__ == "__main__":
    main()
