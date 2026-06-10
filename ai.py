"""AI content generation — produces Threads posts using OpenAI/Anthropic LLMs.

Driven by each account's content_style, topic_keywords, tone, length, format,
vibe, avoid_topics — all stored in the Account model.
"""
import os
import json
import httpx
from setup_logging import get_logger

logger = get_logger(__name__)

AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai").lower()  # openai | anthropic
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "")  # defaults set per-provider below

# ── Prompt Templates ──

SYSTEM_PROMPT = (
    "You are a social media copywriter creating authentic Threads posts. "
    "Write like a real person, not a robot. Match the requested tone, length, and format exactly. "
    "Never use hashtags unless specifically asked. Never use emoji overuse. "
    "Output ONLY the post text — no quotes, no labels, no prefix."
)

THREAD_PROMPT = """Write a single Threads post.

Topic context: {topics}
Tone: {tone}
Length: {length} ({length_guide})
Format: {format}
Vibe: {vibe}
Avoid mentioning: {avoid}

Post:"""

REPLY_PROMPT = """Reply to this Threads post naturally:

---
{parent_text}
---

Your reply should add value, agree, disagree respectfully, or ask a thoughtful question.
Tone: {tone}
Length: {length}
Keywords to weave in: {keywords}

Reply:"""

FUN_FACT_PROMPT = """Write a Threads post sharing an interesting fact, insight, or observation.

Topic niche: {topics}
Tone: {tone}
Vibe: {vibe}

Post:"""

# ── Length guides ──

LENGTH_GUIDE = {
    "short": "1-2 sentences, max 150 characters",
    "medium": "3-5 sentences, 150-500 characters",
    "long": "5+ sentences, 500-2200 characters (the Threads limit)",
}


def _build_chat_messages(system: str, user_prompt: str) -> list:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _call_openai(messages: list, model: str = None) -> str:
    if not AI_API_KEY:
        raise ValueError("AI_API_KEY not set")

    model = model or AI_MODEL or "gpt-4o-mini"
    url = "https://api.openai.com/v1/chat/completions"

    with httpx.Client(timeout=45.0) as client:
        resp = client.post(
            url,
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.85,
                "max_tokens": 512,
            },
        )
        if resp.status_code != 200:
            logger.error(f"OpenAI error {resp.status_code}: {resp.text[:300]}")
            raise RuntimeError(f"OpenAI API error: {resp.status_code}")

        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


def _call_anthropic(messages: list, model: str = None) -> str:
    if not AI_API_KEY:
        raise ValueError("AI_API_KEY not set")

    model = model or AI_MODEL or "claude-3-haiku-20240307"
    url = "https://api.anthropic.com/v1/messages"

    system_content = None
    filtered = []
    for m in messages:
        if m["role"] == "system":
            system_content = m["content"]
        else:
            filtered.append({"role": m["role"], "content": m["content"]})

    body = {
        "model": model,
        "max_tokens": 512,
        "temperature": 0.85,
        "messages": filtered,
    }
    if system_content:
        body["system"] = system_content

    with httpx.Client(timeout=45.0) as client:
        resp = client.post(
            url,
            headers={
                "x-api-key": AI_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if resp.status_code != 200:
            logger.error(f"Anthropic error {resp.status_code}: {resp.text[:300]}")
            raise RuntimeError(f"Anthropic API error: {resp.status_code}")

        data = resp.json()
        return data["content"][0]["text"].strip()


def _call_ai(messages: list) -> str:
    """Route to the configured AI provider."""
    if AI_PROVIDER == "anthropic":
        return _call_anthropic(messages)
    return _call_openai(messages)


# ── Helpers ──

def _safe_json_list(val) -> list:
    """Parse a JSON array from a Text column, returning list or empty."""
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _comma_list(topics: list) -> str:
    if not topics:
        return "general interest, trending topics, personal insights"
    return ", ".join(str(t) for t in topics[:8])


# ── Public API ──

def generate_thread(account) -> str:
    """Generate a thread post based on account's content settings.

    Args:
        account: Account ORM instance with content_style, topic_keywords, etc.
    """
    topics = _comma_list(_safe_json_list(account.topic_keywords))
    avoid = _comma_list(_safe_json_list(account.avoid_topics)) or "nothing specific"

    prompt = THREAD_PROMPT.format(
        topics=topics,
        tone=account.post_tone or "friendly",
        length=account.post_length or "medium",
        length_guide=LENGTH_GUIDE.get(account.post_length, LENGTH_GUIDE["medium"]),
        format=account.post_format or "text",
        vibe=account.vibe or "authentic and relatable",
        avoid=avoid,
    )

    messages = _build_chat_messages(SYSTEM_PROMPT, prompt)
    content = _call_ai(messages)
    logger.info(f"Generated thread ({account.post_length or 'medium'}, {len(content)} chars)")
    return content


def generate_reply(account, parent_text: str) -> str:
    """Generate a reply to an existing thread.

    Args:
        account: Account ORM instance
        parent_text: The text of the thread to reply to
    """
    keywords = _comma_list(_safe_json_list(account.reply_keywords)) or "any relevant"

    prompt = REPLY_PROMPT.format(
        parent_text=parent_text[:1000],
        tone=account.reply_tone or "value_add",
        length=account.reply_length or "medium",
        keywords=keywords,
    )

    messages = _build_chat_messages(SYSTEM_PROMPT, prompt)
    content = _call_ai(messages)
    logger.info(f"Generated reply ({len(content)} chars)")
    return content


def generate_fun_fact(account) -> str:
    """Generate a fun-fact / insight post based on niche."""
    topics = _comma_list(_safe_json_list(account.topic_keywords))

    prompt = FUN_FACT_PROMPT.format(
        topics=topics,
        tone=account.post_tone or "friendly",
        vibe=account.vibe or "interesting and engaging",
    )

    messages = _build_chat_messages(SYSTEM_PROMPT, prompt)
    content = _call_ai(messages)
    logger.info(f"Generated fun-fact ({len(content)} chars)")
    return content
