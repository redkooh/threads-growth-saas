"""AI content generation — produces Threads posts using OpenAI/Anthropic LLMs.

Driven by each account's content_style, topic_keywords, tone, length, format,
vibe, avoid_topics + live feed context for trend-aware content.
"""
import os, json, random, time
from pathlib import Path
import httpx
from setup_logging import get_logger

logger = get_logger(__name__)

# ── Load .env so ai.py works standalone (e.g. tests) ──
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            if val.strip():
                os.environ.setdefault(key.strip(), val.strip())

AI_PROVIDER = os.environ.get("AI_PROVIDER", "openrouter").lower()
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_MODEL = os.environ.get("AI_MODEL", "deepseek/deepseek-v4-flash")
AI_FALLBACK_MODEL = "xiaomi/mimo-v2.5"
OR_BASE_URL = "https://openrouter.ai/api/v1"

# ── Prompt Templates ──

SYSTEM_THREAD = """You are a social media copywriter creating authentic Threads posts. Write like a real person, not a bot.

RULES:
- Hook in the first 2 lines to stop the scroll
- Use 2-3 relevant emojis naturally (don't force them)
- Line breaks between sentences for skimmability
- End with a question or CTA to drive comments
- Never use hashtags
- Never exceed {max_chars} characters
- Output ONLY the post text — no quotes, no labels, no prefixes
- Sound like a real American on social media, not a marketing agency"""

SYSTEM_REPLY = """You reply to Threads posts naturally. Your reply should add value to the conversation.

RULES:
- Be conversational, not promotional
- Use 1 emoji where natural — keeps it human, not botty
- If the post is a question, answer it genuinely
- If it's a hot take, add your own spin
- Never mention "great point" or "totally agree" — be specific
- Match the OP's energy but don't mimic
- Keep it under 200 characters unless replying with a story
- Output ONLY the reply text — no quotes, no labels"""

THREAD_PROMPT = """Write a single viral Threads post.

TOPIC CONTEXT (what to post about):
{topics}

LIVE TREND CONTEXT (what's happening RIGHT NOW on Threads):
{feed_context}

Style: {style}
Tone: {tone}
Length: {length} ({length_guide})
Format: {format}
Vibe: {vibe}
AVOID mentioning: {avoid}
Theme: {theme}

When style or length is 'auto', choose what fits the topic best — don't force everything the same way. Mix it up naturally.

Post:"""

REPLY_PROMPT = """Reply to this Threads post naturally:

---
POST BY @{target_username} ({likes} likes, {replies} replies):
{parent_text}
---

Your reply tone: {tone}
Your reply length: {length}
Keywords to weave in naturally: {keywords}
Target's reply count: {replies} ({"high engagement post — add value" if isinstance(replies, int) and replies > 10 else "conversation starter — be friendly"})

When tone or length is 'auto', choose what fits the post best — match the post's vibe, don't force a formula. Mix it up naturally across replies.

Reply:"""

FUN_FACT_PROMPT = """Write a Threads post sharing an interesting fact, insight, or observation.

Topic context: {topics}
Tone: {tone}
Style: {style}
Vibe: {vibe}

Include 1-2 relevant emojis. Make it shareable and surprising.
Post:"""

# ── Length guides ──

LENGTH_GUIDE = {
    "auto": "Pick the right length for the topic — short punchy takes get 1-2 sentences, detailed insights get 3-5 sentences, deep dives up to 2200 chars",
    "short": "1-2 sentences, max 150 characters",
    "medium": "3-5 sentences, 150-500 characters",
    "long": "5+ sentences, 500-2200 characters (the Threads limit)",
}

# ── Theme emojis ──

THEME_EMOJI = {
    "hot_take": "🔥",
    "real_talk": "💬",
    "wild_card": "🎲",
    "nostalgia": "📼",
    "free_for_all": "🎉",
    "chill": "☕",
    "internet_culture": "📱",
}

TONE_EMOJIS = {
    "friendly": "😊",
    "professional": "💼",
    "sarcastic": "😏",
    "inspirational": "✨",
    "controversial": "🌶",
    "value_add": "💡",
    "agree": "👍",
    "disagree": "👎",
    "question": "❓",
    "humor": "😂",
}


def _build_chat_messages(system: str, user_prompt: str) -> list:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_prompt},
    ]


def _call_openrouter(messages: list, model: str = None, max_tokens: int = 512) -> str:
    """Call OpenRouter with retry + fallback.
    
    Tries primary model first (DeepSeek V4 Flash by default).
    On 429/5xx: retries once with backoff, then falls back to fallback model (Mimo V2.5).
    On 4xx: raises immediately (bad request, auth error, etc).
    """
    primary = model or AI_MODEL
    fallback = AI_FALLBACK_MODEL
    url = f"{OR_BASE_URL}/chat/completions"
    last_error = None

    models_to_try = [(primary, "primary"), (fallback, "fallback")]

    for model_name, label in models_to_try:
        for attempt in range(2):  # retry once per model
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {AI_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://threads-growth-saas.local",
                            "X-Title": "Threads Growth SaaS",
                        },
                        json={
                            "model": model_name,
                            "messages": messages,
                            "temperature": 0.85,
                            "max_tokens": max_tokens,
                        },
                    )
                    # 429/5xx: retry or fallback
                    if resp.status_code in (429,) or (500 <= resp.status_code < 600):
                        logger.warning(f"OpenRouter {label} ({model_name}) error {resp.status_code} (attempt {attempt+1}): {resp.text[:200]}")
                        if attempt == 0:
                            time.sleep(2 ** attempt)  # 1s then skip to fallback
                            continue
                        break  # skip to fallback after 1 retry
                    if resp.status_code != 200:
                        logger.error(f"OpenRouter {label} ({model_name}) non-retryable error {resp.status_code}: {resp.text[:300]}")
                        raise RuntimeError(f"OpenRouter API error {resp.status_code}: {resp.text[:200]}")
                    data = resp.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if label == "fallback":
                        logger.info(f"Used fallback model {fallback} (primary {primary} failed)")
                    return text
            except httpx.TimeoutException:
                logger.warning(f"OpenRouter {label} ({model_name}) timeout (attempt {attempt+1})")
                if attempt == 0:
                    continue  # retry once per model
                break
            except httpx.ConnectError as e:
                logger.warning(f"OpenRouter {label} ({model_name}) connect error (attempt {attempt+1}): {e}")
                if attempt == 0:
                    continue
                break
            except Exception as e:
                last_error = e
                if attempt == 0:
                    continue
                break

    raise RuntimeError(f"All LLM calls failed (primary={primary}, fallback={fallback}): {last_error or 'unknown'}")


def _call_ai(messages: list, max_tokens: int = 512) -> str:
    return _call_openrouter(messages, max_tokens=max_tokens)


# ── Helpers ──

def _safe_json_list(val) -> list:
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        # Treat as comma-separated
        if "," in str(val):
            return [t.strip() for t in str(val).split(",") if t.strip()]
        return [str(val)]


def _comma_list(topics: list) -> str:
    if not topics:
        return "general interest, trending topics, personal insights"
    return ", ".join(str(t) for t in topics[:8])


def _parse_feed_context(feed_posts: list = None, max_items: int = 4) -> str:
    """Extract trends from feed posts for trend-aware content generation."""
    if not feed_posts:
        return "No specific trends detected — write evergreen content"
    lines = []
    for p in feed_posts[:max_items]:
        cap = (p.get("caption", "") or "")[:150]
        if cap:
            lines.append(f'- @{p.get("username","?")}: "{cap}" ({p.get("like_count",0)}❤️)')
    if not lines:
        return "Feed is quiet — write something universally relatable"
    return "\n".join(lines)


STYLES = {
    "auto": "Choose the best style naturally — casual for lifestyle, professional for business, educational for how-tos, viral for hot topics, controversial for debates. Match the topic.",
    "casual": "Friendly, conversational, like talking to a friend",
    "viral": "Bold takes, hooks, engagement bait, controversial edge",
    "professional": "Polished, informed, expert voice with data",
    "educational": "Teach something surprising, explain concepts simply",
    "controversial": "Unpopular opinions, debate starters, hot takes",
}


def _get_style_desc(style: str) -> str:
    return STYLES.get(style, STYLES["auto"])


# ── Public API ──

def generate_thread(
    account,
    feed_posts: list = None,
    theme: str = "",
) -> tuple:
    """Generate a thread post based on account settings + live feed context.

    Args:
        account: Account ORM instance
        feed_posts: Optional list of feed post dicts for trend awareness
        theme: Optional theme day string (e.g. "Hot Take Monday")

    Returns:
        tuple of (post_text, source_info) where source_info describes what influenced it
    """
    topics = _comma_list(_safe_json_list(account.topic_keywords))
    avoid = _comma_list(_safe_json_list(account.avoid_topics)) or "nothing specific"
    feed_context = _parse_feed_context(feed_posts)
    style = _get_style_desc(account.content_style or "auto")
    theme_str = theme or "general"

    post_len = account.post_length or "auto"
    max_chars = 2200 if post_len == "long" else 500

    prompt = THREAD_PROMPT.format(
        topics=topics,
        feed_context=feed_context,
        style=style,
        tone=account.post_tone or "friendly",
        length=post_len,
        length_guide=LENGTH_GUIDE.get(post_len, LENGTH_GUIDE["auto"]),
        format=account.post_format or "text",
        vibe=account.vibe or "authentic and relatable",
        avoid=avoid,
        theme=theme_str,
    )

    system = SYSTEM_THREAD.format(max_chars=max_chars)
    system = inject_style(system, account.writing_style or "")
    messages = _build_chat_messages(system, prompt)
    content = _call_ai(messages)
    logger.info(f"Generated thread ({post_len}, {len(content)} chars)")

    # Determine source
    source = "trend-aware" if feed_posts else "topic-based"
    return content, source


def generate_reply(
    account,
    target_post: dict,
    feed_posts: list = None,
) -> str:
    """Generate a reply to a target post.

    Args:
        account: Account ORM instance
        target_post: Dict with thread_code, username, caption, like_count, reply_count
        feed_posts: Optional — helps the AI understand current feed vibe

    Returns:
        Reply text string
    """
    keywords = _comma_list(_safe_json_list(account.reply_keywords)) or "any relevant"
    parent_text = (target_post.get("caption", "") or "")[:1000]
    target_username = target_post.get("username", "unknown")
    likes = target_post.get("like_count", 0)
    replies = target_post.get("reply_count", 0)

    reply_len = account.reply_length or "auto"
    max_tokens = 384 if reply_len == "auto" else (256 if reply_len == "short" else 384)

    prompt = REPLY_PROMPT.format(
        parent_text=parent_text,
        target_username=target_username,
        likes=likes,
        replies=replies,
        tone=account.reply_tone or "auto",
        length=reply_len,
        keywords=keywords,
    )

    system = inject_style(SYSTEM_REPLY, account.writing_style or "")
    messages = _build_chat_messages(system, prompt)
    content = _call_ai(messages, max_tokens=max_tokens)
    logger.info(f"Generated reply to @{target_username} ({len(content)} chars)")
    return content


def generate_fun_fact(account, feed_posts: list = None) -> str:
    """Generate a fun-fact / insight post, optionally trend-aware."""
    topics = _comma_list(_safe_json_list(account.topic_keywords))

    # If we have feed context, inject it
    extra = ""
    if feed_posts:
        ctx = _parse_feed_context(feed_posts, max_items=3)
        extra = f"\n\nLive feed context (use for inspiration):\n{ctx}"

    prompt = FUN_FACT_PROMPT.format(
        topics=topics + extra,
        tone=account.post_tone or "friendly",
        style=_get_style_desc(account.content_style or "auto"),
        vibe=account.vibe or "interesting and engaging",
    )

    messages = _build_chat_messages(
        inject_style(SYSTEM_THREAD.format(max_chars=500), account.writing_style or ""),
        prompt,
    )
    content = _call_ai(messages, max_tokens=384)
    logger.info(f"Generated fun-fact ({len(content)} chars)")
    return content


# ── Style Learning ──

STYLE_ANALYSIS_SYSTEM = "You analyze a user's Threads posts and extract their unique writing style signature. Be specific and actionable — quote patterns, mention specific punctuation habits, emoji placement, sentence structure. Keep it under 400 words. Output only the style profile, no labels."

STYLE_ANALYSIS_PROMPT = """Analyze these {count} Threads posts from the same user and extract their writing style signature.

For each dimension, be SPECIFIC — reference actual patterns from their posts:

1. Tone & Voice — Sarcastic? Inspirational? Blunt? Friendly? Baseline energy?
2. Sentence Structure — Short punchy lines? Run-on? Paragraphs? One-liners?
3. Punctuation & Capitalization — All lowercase? No periods? Ellipsis ... or em-dash —? Caps for emphasis?
4. Emoji Usage — Which emojis? Start/mid/end? How many per post?
5. Vocabulary & Slang — Repeated words/phrases ("honestly", "unpopular opinion", "hot take")? Dialect markers?
6. Hooks & Openers — How do they start? Questions? Statements? "Hot take:"? Quotes?
7. Structure — Line breaks? Thread format (1/n)? Dots? Lists?
8. Engagement Patterns — What gets the most likes/replies? Long thoughtful or short hot takes?

POSTS (highest engagement first):
{posts}

Output a complete writing style signature in 3-4 paragraphs. Be specific."""


def learn_writing_style(posts: list) -> str:
    """Analyze a user's own posts and return a style signature."""
    if not posts or len(posts) < 5:
        return ""

    # Sort by engagement
    sorted_posts = sorted(posts, key=lambda p: p.get("like_count", 0) + p.get("reply_count", 0), reverse=True)

    # Format posts for analysis
    lines = []
    for i, p in enumerate(sorted_posts[:70], 1):
        caption = p.get("caption", "")[:500]
        likes = p.get("like_count", 0)
        replies = p.get("reply_count", 0)
        lines.append(f"[Post {i}] (❤️{likes} 💬{replies})\n{caption}\n")

    posts_text = "\n---\n".join(lines)
    prompt = STYLE_ANALYSIS_PROMPT.format(count=len(sorted_posts[:70]), posts=posts_text)

    messages = [
        {"role": "system", "content": STYLE_ANALYSIS_SYSTEM},
        {"role": "user", "content": prompt},
    ]

    try:
        style = _call_ai(messages, max_tokens=600)
        logger.info(f"Learned writing style ({len(style)} chars)")
        return style
    except Exception as e:
        logger.warning(f"Style learning failed: {e}")
        return ""


def inject_style(system_prompt: str, style: str) -> str:
    """Inject a learned writing style into a system prompt."""
    if not style:
        return system_prompt
    return system_prompt.replace(
        "Write like a real person, not a bot.",
        f"Write like a real person, not a bot. MATCH THIS USER'S WRITING STYLE:\n{style}",
    )
