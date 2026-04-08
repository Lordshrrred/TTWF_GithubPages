#!/usr/bin/env python3
"""
Daily post generator for Towing Costs By City.
Reads the next unprocessed keyword from keywords.txt,
generates a Hugo post via Claude API, and saves it.
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
import anthropic

# Load environment variables from .env file (local dev only)
load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
KEYWORDS_FILE = REPO_ROOT / "scripts" / "keywords.txt"
POSTS_DIR = REPO_ROOT / "content" / "posts"

SYSTEM_PROMPT = (
    "You are writing a local SEO page for a site about towing costs by city. "
    "Write like a knowledgeable local who knows exactly what towing costs in that area. "
    "Include realistic cost ranges, what affects price, and practical advice. "
    "End every post with exactly this block: "
    "'Need more roadside emergency help? Visit "
    "[Tow With The Flow](https://towwiththeflow.com) "
    "for guides on what to do when your car breaks down.' "
    "Never use em dashes. Return only valid Hugo markdown with frontmatter "
    "including title, date, description under 155 chars, tags, slug, canonical. "
    "For canonical, use the matching primary Tow With The Flow URL in the form "
    "'https://towwiththeflow.com/towing-cost-city-state/' when the topic is a city towing cost page."
)

BACKLINK_BLOCK = (
    "\n\nNeed more roadside emergency help? "
    "Visit [Tow With The Flow](https://towwiththeflow.com) "
    "for guides on what to do when your car breaks down."
)


def slugify(text: str) -> str:
    """Convert keyword to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def find_next_keyword() -> tuple[int, str] | None:
    """
    Find the first keyword in keywords.txt that is not marked # DONE.
    Returns (line_index, keyword_text) or None if all are processed.
    """
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "# DONE" not in line:
            return i, stripped
    return None


def mark_keyword_done(line_index: int, keyword: str) -> None:
    """Mark a keyword as done and append variation keywords."""
    lines = KEYWORDS_FILE.read_text(encoding="utf-8").splitlines()
    lines[line_index] = f"{keyword} # DONE"

    # Append variation keywords if they don't already exist
    existing = set(l.split("# DONE")[0].strip() for l in lines)
    variations = []

    # Extract city name from keyword for variations
    city_match = re.search(r"towing cost in (.+)", keyword, re.IGNORECASE)
    if city_match:
        city = city_match.group(1).strip()
        candidates = [
            f"average towing cost {city}",
            f"cheap towing {city}",
            f"emergency towing cost {city} at night",
        ]
        for v in candidates:
            if v not in existing:
                variations.append(v)

    lines.extend(variations)
    KEYWORDS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_post(keyword: str) -> str:
    """Call Claude API to generate a post for the given keyword."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = (
        f"Write a 500-700 word Hugo markdown post about: {keyword}\n\n"
        "Requirements:\n"
        "- Realistic cost ranges: $75-$125 base fee, $3-5 per mile (vary by city cost of living)\n"
        "- Include: average total cost, hook-up fees, after-hours fees, highway vs local differences\n"
        "- Include a section on how to avoid getting ripped off\n"
        "- Direct, useful tone -- like a knowledgeable local\n"
        "- No em dashes\n"
        "- End with the required backlink block exactly as specified\n"
        "- Include valid Hugo frontmatter: title, date (today), description (under 155 chars), tags, slug, canonical\n"
        "- Return only the markdown content, no extra commentary"
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = message.content[0].text

    # Ensure the backlink block is present
    if "towwiththeflow.com" not in content:
        content = content.rstrip() + BACKLINK_BLOCK

    return content


def extract_slug_from_frontmatter(content: str, fallback_keyword: str) -> str:
    """Extract slug from Hugo frontmatter, or generate one from keyword."""
    match = re.search(r'^slug:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return slugify(fallback_keyword)


def save_post(slug: str, content: str) -> Path:
    """Save the post to the content/posts directory."""
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    post_path = POSTS_DIR / f"{slug}.md"

    if post_path.exists():
        print(f"WARNING: {post_path} already exists. Skipping write.")
        return post_path

    post_path.write_text(content, encoding="utf-8")
    return post_path


def main():
    result = find_next_keyword()
    if result is None:
        print("All keywords have been processed. Nothing to do.")
        sys.exit(0)

    line_index, keyword = result
    print(f"Processing keyword: {keyword}")

    content = generate_post(keyword)
    slug = extract_slug_from_frontmatter(content, keyword)
    post_path = save_post(slug, content)

    mark_keyword_done(line_index, keyword)

    print(f"Post saved: {post_path}")
    print(f"Keyword marked done: {keyword}")


if __name__ == "__main__":
    main()
