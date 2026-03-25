#!/usr/bin/env python3
"""
Generate a variation post for the feeder blog based on a TowWithTheFlow source post.
Called by the GitHub Actions workflow when triggered from TowWithTheFlow.

Reads from environment:
    SOURCE_SLUG   - slug of the original TWTF post
    SOURCE_URL    - full canonical URL of the original post
    SOURCE_TITLE  - title of the original post
    ANTHROPIC_API_KEY
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

REPO_ROOT = Path(__file__).parent.parent
POSTS_DIR = REPO_ROOT / "content" / "posts"
TWTF_RAW  = "https://raw.githubusercontent.com/Lordshrrred/TowWithTheFlow/main/content/posts"

SYSTEM_PROMPT = (
    "You are writing a variation of a car breakdown help article for a feeder blog. "
    "Rewrite the provided article with: "
    "a different opening paragraph, "
    "the same core information but different phrasing, "
    "and a slightly different structure. "
    "Never use em dashes. "
    "Return only valid Hugo markdown with frontmatter. "
    "Frontmatter fields: title (slightly varied from the original), "
    "date (today's date), "
    "description (under 155 chars), "
    "tags (same or similar to original), "
    "slug (original slug with -guide appended)."
)


def fetch_source_post(source_slug: str) -> str:
    url = f"{TWTF_RAW}/{source_slug}.md"
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        sys.exit(f"ERROR: Could not fetch source post ({resp.status_code}): {url}")
    return resp.text


def generate_variation(source_content: str, source_slug: str, source_url: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    backlink = (
        f"For the full guide on this topic, visit "
        f"[Tow With The Flow]({source_url}) -- "
        f"real answers when your car breaks down."
    )

    user_prompt = (
        f"Here is the original article to rewrite as a variation:\n\n"
        f"{source_content}\n\n"
        f"Today's date: {today}\n"
        f"Target slug: {source_slug}-guide\n\n"
        f"End the post with exactly this block:\n"
        f"'{backlink}'\n\n"
        f"Return only the Hugo markdown with frontmatter. No extra commentary."
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = message.content[0].text.strip()

    # Strip markdown code fences if the model wrapped the output
    if content.startswith("```"):
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

    # Guarantee the backlink is present even if the model omitted it
    if source_url not in content:
        content = content.rstrip() + f"\n\n{backlink}"

    return content


def extract_slug(content: str, fallback: str) -> str:
    match = re.search(r'^slug:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return fallback


def main():
    source_slug  = os.environ.get("SOURCE_SLUG", "").strip()
    source_url   = os.environ.get("SOURCE_URL", "").strip()
    source_title = os.environ.get("SOURCE_TITLE", "").strip()

    if not source_slug:
        sys.exit("ERROR: SOURCE_SLUG environment variable is required.")
    if not source_url:
        source_url = f"https://towwiththeflow.com/{source_slug}/"

    print(f"Fetching source post: {source_slug}")
    source_content = fetch_source_post(source_slug)

    print(f"Generating variation for: {source_title or source_slug}")
    content = generate_variation(source_content, source_slug, source_url)

    slug = extract_slug(content, f"{source_slug}-guide")
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    post_path = POSTS_DIR / f"{slug}.md"

    if post_path.exists():
        print(f"WARNING: {post_path} already exists. Skipping.")
        sys.exit(0)

    post_path.write_text(content, encoding="utf-8")
    print(f"Variation saved: {post_path}")


if __name__ == "__main__":
    main()
