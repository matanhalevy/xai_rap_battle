"""
Grok API integration for fetching X/Twitter data using x_search tool.

Uses the xAI Responses API with server-side x_search tool for real-time tweet fetching.
"""

import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("XAI_API_KEY")
API_BASE = "https://api.x.ai/v1"


def fetch_recent_tweets(handle: str, limit: int = 10) -> tuple[list[str], str]:
    """
    Fetch recent tweets from an X handle using Grok x_search.

    Args:
        handle: X/Twitter handle (with or without @)
        limit: Maximum number of tweets to fetch

    Returns:
        Tuple of (list of tweet texts, status_message)
    """
    if not API_KEY:
        return [], "Error: XAI_API_KEY not set in environment"

    if not handle:
        return [], "No handle provided"

    # Normalize handle (remove @ if present)
    clean_handle = handle.lstrip("@").strip()
    if not clean_handle:
        return [], "Invalid handle"

    prompt = f"""Find the {limit} most recent tweets from @{clean_handle}.
For each tweet, provide:
- The tweet text
- Key topics or themes mentioned

Format as a numbered list. Focus on tweets that reveal personality, opinions, or current interests."""

    try:
        response = requests.post(
            f"{API_BASE}/responses",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-4-1-fast",
                "input": [{"role": "user", "content": prompt}],
                "tools": [
                    {"type": "x_search", "allowed_x_handles": [clean_handle]}
                ],
            },
            timeout=60,
        )

        if response.status_code != 200:
            return [], f"API Error {response.status_code}: {response.text}"

        data = response.json()

        # Extract the output text from the response
        output_text = ""
        if "output" in data:
            for item in data["output"]:
                if item.get("type") == "message" and "content" in item:
                    for content_block in item["content"]:
                        if content_block.get("type") == "output_text":
                            output_text += content_block.get("text", "")

        if not output_text:
            # Fallback: try to get from choices if present
            if "choices" in data:
                output_text = data["choices"][0]["message"]["content"]

        # Parse tweets from the response
        tweets = _parse_tweet_list(output_text)

        return tweets, f"Found {len(tweets)} tweets from @{clean_handle}"

    except requests.exceptions.Timeout:
        return [], "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return [], f"Request error: {e}"
    except (KeyError, IndexError) as e:
        return [], f"Error parsing response: {e}"


def analyze_opponent_relationship(
    handle_a: str, handle_b: str
) -> tuple[dict, str]:
    """
    Check for interactions between two X handles - mentions, replies, beef.

    Args:
        handle_a: First X handle
        handle_b: Second X handle

    Returns:
        Tuple of (relationship_dict, status_message)
        relationship_dict contains:
        - has_interaction: bool
        - interaction_type: str (friendly, neutral, hostile, none)
        - summary: str
        - notable_exchanges: list[str]
    """
    if not API_KEY:
        return {"has_interaction": False}, "Error: XAI_API_KEY not set"

    clean_a = handle_a.lstrip("@").strip() if handle_a else ""
    clean_b = handle_b.lstrip("@").strip() if handle_b else ""

    if not clean_a or not clean_b:
        return {"has_interaction": False}, "Both handles required"

    prompt = f"""Analyze the relationship between @{clean_a} and @{clean_b} on X/Twitter.

Search for:
1. Direct mentions or replies between them
2. Quote tweets of each other
3. Any public disagreements or "beef"
4. Collaborative or supportive interactions
5. Common topics they both discuss

Provide a summary with:
- INTERACTION_TYPE: friendly / neutral / hostile / none
- SUMMARY: 1-2 sentence overview of their relationship
- NOTABLE_EXCHANGES: List any specific notable tweets between them
- COMMON_GROUND: Topics they both care about (for rap battle material)
- POINTS_OF_CONFLICT: Disagreements or opposing views (for rap battle material)"""

    try:
        response = requests.post(
            f"{API_BASE}/responses",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-4-1-fast",
                "input": [{"role": "user", "content": prompt}],
                "tools": [
                    {"type": "x_search", "allowed_x_handles": [clean_a, clean_b]}
                ],
            },
            timeout=90,
        )

        if response.status_code != 200:
            return {"has_interaction": False}, f"API Error {response.status_code}"

        data = response.json()

        # Extract output text
        output_text = ""
        if "output" in data:
            for item in data["output"]:
                if item.get("type") == "message" and "content" in item:
                    for content_block in item["content"]:
                        if content_block.get("type") == "output_text":
                            output_text += content_block.get("text", "")

        if not output_text and "choices" in data:
            output_text = data["choices"][0]["message"]["content"]

        # Parse the relationship analysis
        relationship = _parse_relationship_analysis(output_text)

        return relationship, f"Analyzed relationship between @{clean_a} and @{clean_b}"

    except requests.exceptions.Timeout:
        return {"has_interaction": False}, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return {"has_interaction": False}, f"Request error: {e}"
    except Exception as e:
        return {"has_interaction": False}, f"Error: {e}"


def get_tweet_context_for_battle(
    char1_handle: str | None,
    char2_handle: str | None,
) -> tuple[str, str]:
    """
    Fetch tweet context for both fighters to enhance lyric generation.

    Args:
        char1_handle: X handle for character 1
        char2_handle: X handle for character 2

    Returns:
        Tuple of (context_string, status_message)
    """
    context_parts = []
    statuses = []

    # Fetch tweets for character 1
    if char1_handle:
        tweets1, status1 = fetch_recent_tweets(char1_handle, limit=5)
        statuses.append(status1)
        if tweets1:
            clean_handle = char1_handle.lstrip("@")
            context_parts.append(f"RECENT TWEETS FROM @{clean_handle}:")
            for tweet in tweets1[:5]:
                context_parts.append(f"  - {tweet}")
            context_parts.append("")

    # Fetch tweets for character 2
    if char2_handle:
        tweets2, status2 = fetch_recent_tweets(char2_handle, limit=5)
        statuses.append(status2)
        if tweets2:
            clean_handle = char2_handle.lstrip("@")
            context_parts.append(f"RECENT TWEETS FROM @{clean_handle}:")
            for tweet in tweets2[:5]:
                context_parts.append(f"  - {tweet}")
            context_parts.append("")

    # Analyze relationship if both handles provided
    if char1_handle and char2_handle:
        relationship, rel_status = analyze_opponent_relationship(
            char1_handle, char2_handle
        )
        statuses.append(rel_status)

        if relationship.get("has_interaction"):
            context_parts.append("RELATIONSHIP BETWEEN OPPONENTS:")
            context_parts.append(f"  Type: {relationship.get('interaction_type', 'unknown')}")
            context_parts.append(f"  Summary: {relationship.get('summary', 'No summary')}")

            if relationship.get("common_ground"):
                context_parts.append(f"  Common Ground: {relationship.get('common_ground')}")
            if relationship.get("points_of_conflict"):
                context_parts.append(f"  Points of Conflict: {relationship.get('points_of_conflict')}")

            notable = relationship.get("notable_exchanges", [])
            if notable:
                context_parts.append("  Notable Exchanges:")
                for exchange in notable[:3]:
                    context_parts.append(f"    - {exchange}")

    context = "\n".join(context_parts) if context_parts else ""
    status = " | ".join(statuses) if statuses else "No handles provided"

    return context, status


def _parse_tweet_list(text: str) -> list[str]:
    """Parse a numbered or bulleted list of tweets from text."""
    tweets = []
    lines = text.strip().split("\n")

    current_tweet = []
    for line in lines:
        line = line.strip()
        if not line:
            if current_tweet:
                tweets.append(" ".join(current_tweet))
                current_tweet = []
            continue

        # Check if this is a new numbered item
        if re.match(r"^\d+[\.\)]\s*", line):
            if current_tweet:
                tweets.append(" ".join(current_tweet))
            # Remove the number prefix
            cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
            current_tweet = [cleaned] if cleaned else []
        elif re.match(r"^[-*]\s*", line):
            if current_tweet:
                tweets.append(" ".join(current_tweet))
            cleaned = re.sub(r"^[-*]\s*", "", line)
            current_tweet = [cleaned] if cleaned else []
        else:
            current_tweet.append(line)

    if current_tweet:
        tweets.append(" ".join(current_tweet))

    return tweets


def _parse_relationship_analysis(text: str) -> dict:
    """Parse the relationship analysis response into a structured dict."""
    result = {
        "has_interaction": False,
        "interaction_type": "none",
        "summary": "",
        "notable_exchanges": [],
        "common_ground": "",
        "points_of_conflict": "",
    }

    text_lower = text.lower()

    # Detect interaction type
    if "hostile" in text_lower or "beef" in text_lower or "conflict" in text_lower:
        result["interaction_type"] = "hostile"
        result["has_interaction"] = True
    elif "friendly" in text_lower or "supportive" in text_lower or "collaborate" in text_lower:
        result["interaction_type"] = "friendly"
        result["has_interaction"] = True
    elif "neutral" in text_lower or "professional" in text_lower:
        result["interaction_type"] = "neutral"
        result["has_interaction"] = True
    elif "no interaction" in text_lower or "haven't interacted" in text_lower:
        result["interaction_type"] = "none"
    else:
        # Check for any mentions of interaction
        if "mention" in text_lower or "replied" in text_lower or "quote" in text_lower:
            result["interaction_type"] = "neutral"
            result["has_interaction"] = True

    # Extract summary (first paragraph or SUMMARY: section)
    summary_match = re.search(r"SUMMARY:\s*(.+?)(?:\n\n|\n[A-Z]|$)", text, re.IGNORECASE | re.DOTALL)
    if summary_match:
        result["summary"] = summary_match.group(1).strip()
    else:
        # Use first non-empty paragraph
        paragraphs = text.split("\n\n")
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("INTERACTION") and len(p) > 20:
                result["summary"] = p[:200]
                break

    # Extract common ground
    common_match = re.search(r"COMMON.?GROUND:\s*(.+?)(?:\n\n|\n[A-Z]|$)", text, re.IGNORECASE | re.DOTALL)
    if common_match:
        result["common_ground"] = common_match.group(1).strip()

    # Extract points of conflict
    conflict_match = re.search(r"POINTS?.?OF.?CONFLICT:\s*(.+?)(?:\n\n|\n[A-Z]|$)", text, re.IGNORECASE | re.DOTALL)
    if conflict_match:
        result["points_of_conflict"] = conflict_match.group(1).strip()

    # Extract notable exchanges
    exchanges_match = re.search(r"NOTABLE.?EXCHANGES?:\s*(.+?)(?:\n\n|$)", text, re.IGNORECASE | re.DOTALL)
    if exchanges_match:
        exchanges_text = exchanges_match.group(1)
        result["notable_exchanges"] = _parse_tweet_list(exchanges_text)

    return result
