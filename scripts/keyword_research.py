#!/usr/bin/env python3
"""
Weekly keyword researcher for Towing Costs By City.
Uses Claude API to generate 20 new towing cost keywords
and appends them to keywords.txt (deduped).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import anthropic

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
KEYWORDS_FILE = REPO_ROOT / "scripts" / "keywords.txt"

SYSTEM_PROMPT = (
    "You are a local SEO keyword researcher specializing in automotive and towing services. "
    "Generate practical, search-intent keywords that real drivers would type when looking for "
    "towing costs. Focus on city/location-based keywords and practical towing scenarios. "
    "Return only a plain list of keywords, one per line, no numbering, no extra text."
)


def load_existing_keywords() -> set[str]:
    """Load all existing keywords (done or pending) from keywords.txt."""
    if not KEYWORDS_FILE.exists():
        return set()
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    existing = set()
    for line in lines:
        # Strip done markers and comments
        clean = line.split("# DONE")[0].split("#")[0].strip()
        if clean:
            existing.add(clean.lower())
    return existing


def generate_new_keywords(existing: set[str]) -> list[str]:
    """Use Claude to generate 20 new towing cost keywords."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)

    existing_sample = "\n".join(list(existing)[:30])

    user_prompt = (
        "Generate 20 new towing cost keywords for a local SEO blog about towing prices. "
        "Mix of: city-specific (e.g., 'towing cost in [city] [state]'), "
        "scenario-based (e.g., 'towing cost after accident'), "
        "and vehicle-specific (e.g., 'towing cost SUV'). "
        "Make them realistic search queries that drivers would actually use.\n\n"
        f"Existing keywords to avoid duplicating:\n{existing_sample}\n\n"
        "Return exactly 20 keywords, one per line, no numbering or bullets."
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text
    keywords = [line.strip() for line in raw.splitlines() if line.strip()]
    return keywords


def append_new_keywords(new_keywords: list[str], existing: set[str]) -> int:
    """Append new keywords to keywords.txt, skipping duplicates."""
    added = 0
    with KEYWORDS_FILE.open("a", encoding="utf-8") as f:
        for kw in new_keywords:
            if kw.lower() not in existing:
                f.write(f"{kw}\n")
                existing.add(kw.lower())
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
