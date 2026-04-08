#!/usr/bin/env python3
"""
Generate a variation post for the feeder blog based on a TowWithTheFlow source post.
Called by the GitHub Actions workflow when triggered from TowWithTheFlow.

Reads from environment:
    SOURCE_SLUG   - slug of the original TWTF post
    SOURCE_URL    - full canonical URL of the original post (specific post, not homepage)
    SOURCE_TITLE  - title of the original post
    ANTHROPIC_API_KEY
"""

import hashlib
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

# Rotate suffixes so feeder posts aren't all -guide
SUFFIXES = ["-tips", "-advice", "-help", "-guide"]


def pick_suffix(source_slug: str) -> str:
    """Deterministically pick a suffix from slug hash so it's stable on reruns."""
    idx = int(hashlib.md5(source_slug.encode()).hexdigest(), 16) % len(SUFFIXES)
    return SUFFIXES[idx]


def build_system_prompt(source_slug: str, source_url: str) -> str:
    # Backlink uses the exact post URL, never the homepage
    backlink = (
        f"For the complete guide on this topic, visit "
        f"[Tow With The Flow]({source_url}) "
        f"- real answers when your car breaks down."
    )
    return (
        "Rewrite this car breakdown/roadside help article as a unique variation "
        "for a feeder blog. Use the same information but completely different phrasing, "
        "different opening paragraph, different structure. Must not read as duplicate "
        "content. Never use em dashes in the body text. "
        f"End the post with EXACTLY this backlink block on its own line — "
        f"do not change it:\n\n{backlink}\n\n"
        "Return only valid Hugo markdown with frontmatter. "
        "Frontmatter fields: title (slightly varied from original), "
        "date (today's date), description (under 155 chars), "
        "tags (same or similar to original), "
        "slug (I will provide the target slug — use it exactly as given), "
        f'canonical (use exactly "{source_url}").'
    )


def fetch_source_post(source_slug: str) -> str:
    url = f"{TWTF_RAW}/{source_slug}.md"
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        sys.exit(f"ERROR: Could not fetch source post ({resp.status_code}): {url}")
    return resp.text


def generate_variation(
    source_content: str,
    source_slug: str,
    source_url: str,
    target_slug: str,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic(api_key=api_key)
    today  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    backlink = (
        f"For the complete guide on this topic, visit "
        f"[Tow With The Flow]({source_url}) "
        f"- real answers when your car breaks down."
    )

    system = build_system_prompt(source_slug, source_url)

    user_prompt = (
        f"Target feeder slug: {target_slug}\n"
        f"Today's date: {today}\n\n"
        f"Original article to rewrite:\n\n{source_content}"
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1800,
        system=system,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = message.content[0].text.strip()

    # Strip markdown code fences if the model wrapped the output
    if content.startswith("```"):
        content = re.sub(r'^```\w*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

    # Guarantee the specific-post backlink is present
    if source_url not in content:
        content = content.rstrip() + f"\n\n{backlink}\n"

    # Convert inherited local asset and post links to stable absolute URLs.
    content = re.sub(r'\]\(/images/', '](https://towwiththeflow.com/images/', content)
    content = re.sub(r'\]\(/posts/([^)/]+)/\)', r'](https://towwiththeflow.com/\1/)', content)

    # Enforce the target slug in frontmatter
    content = re.sub(
        r'^(slug:\s*)["\']?[^"\'\n]+["\']?\s*$',
        f'\\g<1>"{target_slug}"',
        content, count=1, flags=re.MULTILINE,
    )

    # Enforce canonical back to the source post.
    if re.search(r'^canonical:\s*', content, re.MULTILINE):
        content = re.sub(
            r'^(canonical:\s*)["\']?[^"\'\n]+["\']?\s*$',
            f'\\g<1>"{source_url}"',
            content, count=1, flags=re.MULTILINE,
        )
    else:
        content = re.sub(
            r'^(slug:\s*["\']?[^"\'\n]+["\']?\s*$)',
            r'\1' + f'\ncanonical: "{source_url}"',
            content, count=1, flags=re.MULTILINE,
        )

    return content


def extract_slug(content: str, fallback: str) -> str:
    match = re.search(r'^slug:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
    if match:
        return match.group(1).strip().strip("'\"")
    return fallback


def main():
    source_slug  = os.environ.get("SOURCE_SLUG", "").strip()
    source_url   = os.environ.get("SOURCE_URL", "").strip()
    source_title = os.environ.get("SOURCE_TITLE", "").strip()

    if not source_slug:
        sys.exit("ERROR: SOURCE_SLUG environment variable is required.")

    # Always use the specific post URL, never the homepage
    if not source_url:
        source_url = f"https://towwiththeflow.com/{source_slug}/"

    # Vary the suffix deterministically so reruns produce the same slug
    suffix      = pick_suffix(source_slug)
    target_slug = f"{source_slug}{suffix}"

    print(f"Fetching source post: {source_slug}")
    source_content = fetch_source_post(source_slug)

    print(f"Generating variation: {target_slug}  (source: {source_title or source_slug})")
    content = generate_variation(source_content, source_slug, source_url, target_slug)

    slug      = extract_slug(content, target_slug)
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    post_path = POSTS_DIR / f"{slug}.md"

    if post_path.exists():
        print(f"WARNING: {post_path} already exists. Skipping.")
        sys.exit(0)

    post_path.write_text(content, encoding="utf-8")
    print(f"Variation saved: {post_path}")
    print(f"Backlink points to: {source_url}")


if __name__ == "__main__":
    main()
