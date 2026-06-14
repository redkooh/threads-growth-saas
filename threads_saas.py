"""Threads API wrapper — uses the official threads-unofficial-api library.

The library uses GraphQL endpoints (same as webapp), sends all required internal
headers (X-FB-DTSG, X-FB-LSD, X-BLOKS-Version-ID, session params), and
auto-refreshes tokens when they expire. No more "robot detection" checkpoints.
"""
import json, random, os, time, sys
import importlib
from setup_logging import get_logger

logger = get_logger(__name__)

# Import the real library — use absolute import to avoid conflict with our module name
_LIB_PATH = "/home/ubuntu/threads-growth/threads-unofficial-api"
if _LIB_PATH not in sys.path:
    sys.path.insert(0, _LIB_PATH)

_threads_client_mod = importlib.import_module("threads.client")
_threads_auth_mod = importlib.import_module("threads.auth")
ThreadsClient = _threads_client_mod.ThreadsClient
ThreadsAuth = _threads_auth_mod.ThreadsAuth

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class ThreadsAPIError(Exception):
    """Raised when a Threads API call fails."""
    pass


def _convert_proxy(raw_proxy: str) -> str:
    """Convert PacketStream raw format to httpx-compatible URL.

    PacketStream format:    host:port:user:pass_country-X
    httpx expects:          http://user:pass_country-X@host:port

    Also handles city-level: host:port:user:pass_country-X-CityName
    """
    if not raw_proxy:
        return raw_proxy
    # Already a proper URL — pass through
    if raw_proxy.startswith("http://") or raw_proxy.startswith("https://") or raw_proxy.startswith("socks"):
        return raw_proxy
    try:
        parts = raw_proxy.split(":", 2)
        host = parts[0]
        port = parts[1]
        auth = parts[2]
        return f"http://{auth}@{host}:{port}"
    except (IndexError, ValueError):
        logger.warning(f"Could not parse proxy string: {raw_proxy[:40]}... — using raw value")
        return raw_proxy


def _convert_cookies(cookies_input) -> dict:
    """Convert various cookie formats to the {name: value} dict the library expects.
    
    Handles both:
    - List of {name, value} dicts (from browser export / SaaS DB)
    - Flat {name: value} dict (from Hermes/bot sessions)
    """
    if isinstance(cookies_input, dict):
        return {k: v for k, v in cookies_input.items()}
    
    if isinstance(cookies_input, list):
        result = {}
        for c in cookies_input:
            if isinstance(c, dict) and "name" in c and "value" in c:
                result[c["name"]] = c["value"]
            elif isinstance(c, dict) and "key" in c and "value" in c:
                result[c["key"]] = c["value"]
        return result
    
    return {}


def human_delay(action_type: str = "post"):
    """Sleep a random human-like delay based on action type."""
    delays = {
        "post_thread": (40, 90),    # 5x: slower, safer
        "post_text": (20, 50),      # 5x: slower, safer
        "reply": (60, 160),         # 10x: safer
        "feed_read": (10, 25),      # 5x: slower, safer
        "like": (15, 40),           # 5x: slower, safer
    }
    lo, hi = delays.get(action_type, (4, 10))
    secs = random.uniform(lo, hi)
    time.sleep(secs)


def _is_low_quality(post) -> bool:
    """Heuristic: skip non-English, spam, hashtag-dumps, ultra-short posts."""
    caption = ""
    if hasattr(post, "caption"):
        caption = (post.caption or "").strip()
    elif isinstance(post, dict):
        caption = (post.get("caption", "") or "").strip()
    
    if not caption or len(caption) < 15:
        return True
    
    # More than 30% hashtags
    hashtag_ratio = caption.count("#") / max(len(caption.split()), 1)
    if hashtag_ratio > 0.3:
        return True
    
    # Non-English heuristic
    non_ascii = sum(1 for c in caption if ord(c) > 127)
    if len(caption) > 20 and non_ascii / len(caption) > 0.4:
        return True
    
    # Spam patterns
    spam_patterns = ["follow for follow", "f4f", "link in bio", "check my bio", "dm me"]
    if any(p in caption.lower() for p in spam_patterns):
        return True
    
    return False


# ── Auth ──

class ThreadsAuthWrapper:
    """Threads API auth — wraps ThreadsAuth from the official library.
    
    Sets THREADS_PROXY env var for proxy support (the library reads it from
    the environment automatically).
    
    Usage:
        auth = ThreadsAuthWrapper.from_cookies(cookies, proxy="...")
        auth.post_thread("Hello world")
        auth.get_feed(count=20)
    """
    
    def __init__(self, cookies: dict, proxy: str = None):
        # Build auth from cookies dict
        self.auth = ThreadsAuth.from_cookies(cookies, user_agent=USER_AGENT)
        # Store proxy on the auth object so every request uses the right one
        self.proxy_url = _convert_proxy(proxy) if proxy else None
        if self.proxy_url:
            self.auth._proxy_url = self.proxy_url
        
        # Step 1: Lightweight token refresh — grace on failure
        refresh_ok = True
        try:
            self.auth.refresh_tokens()
        except Exception as e:
            logger.warning(f"Token refresh skipped ({e}) — continuing with base cookies")
            refresh_ok = False
            # The client may work anyway if cookies are still valid
        
        if not refresh_ok:
            # Prevent ThreadsClient.__init__ from calling refresh_tokens again
            original_refresh = self.auth.refresh_tokens
            self.auth.refresh_tokens = lambda: None
        
        # ── Restore full browser session params if enriched ──
        # The enrich_cookies.py script stores __session_params, __fb_dtsg,
        # and __lsd as special cookie entries captured via Playwright.
        # These contain __dyn, __csr, __hsdp etc that HTML parse misses.
        restored_params = []
        if "__session_params" in cookies:
            try:
                sp = json.loads(cookies["__session_params"])
                # Merge into session_params (don't overwrite if already set)
                for k, v in sp.items():
                    if k not in self.auth.session_params:
                        self.auth.session_params[k] = v
                        restored_params.append(k)
            except (json.JSONDecodeError, TypeError):
                pass
        if "__fb_dtsg" in cookies and cookies["__fb_dtsg"]:
            self.auth.fb_dtsg = cookies["__fb_dtsg"]
        if "__lsd" in cookies and cookies["__lsd"]:
            self.auth.lsd = cookies["__lsd"]
        if restored_params:
            logger.info(f"✅ Restored browser session params: {restored_params}")
        
        # Create the client
        self.client = ThreadsClient(
            self.auth,
            rate_limit_rps=1.0,
            max_retries=3,
            timeout=30.0,
        )
        logger.info(f"✅ Auth ready: session_params={list(self.auth.session_params.keys())}")
    
    @classmethod
    def from_cookies(cls, cookies_input, proxy: str = None) -> "ThreadsAuthWrapper":
        cookies = _convert_cookies(cookies_input)
        return cls(cookies, proxy)
    
    def close(self):
        """Clean up HTTP client."""
        try:
            self.client.http._client.close()
        except Exception:
            pass
    
    def _call_with_proxy_fallback(self, fn_name: str, *args, **kwargs):
        """Call a library method with up to 10 proxy retries, then fall back to no proxy."""
        import time
        from threads import ThreadsClient
        max_attempts = 10
        last_exc = None

        for attempt in range(1, max_attempts + 1):
            try:
                fn = getattr(self.client, fn_name)
                return fn(*args, **kwargs)
            except Exception as e:
                last_exc = e
                if attempt < max_attempts:
                    wait = min(0.5 * attempt, 5)
                    logger.warning(f"{fn_name} attempt {attempt}/{max_attempts} via proxy failed ({e}) — retrying in {wait:.1f}s")
                    time.sleep(wait)
                else:
                    logger.warning(f"{fn_name} failed {max_attempts}x with proxy — trying without proxy")

        # Fallback: rebuild client WITHOUT proxy, retry once
        try:
            self.auth._proxy_url = None
            self.client.http._client.close()
        except Exception:
            pass
        # Recreate the ThreadsClient (which rebuilds http from scratch)
        self.client = ThreadsClient(
            self.auth,
            rate_limit_rps=1.0,
            max_retries=3,
            timeout=30.0,
        )
        try:
            fn = getattr(self.client, fn_name)
            result = fn(*args, **kwargs)
            logger.warning(f"{fn_name} succeeded after falling back to no proxy")
            # Restore proxy for subsequent calls
            if self.proxy_url:
                self.auth._proxy_url = self.proxy_url
            return result
        except Exception as e:
            if self.proxy_url:
                self.auth._proxy_url = self.proxy_url
            raise last_exc or e
    
    # ── Posting ──
    
    def post_thread(self, text: str, link: str = None) -> dict:
        """Create a new thread (text post)."""
        _rc_mod = importlib.import_module("threads.constants")
        ReplyControl = _rc_mod.ReplyControl
        try:
            result = self._call_with_proxy_fallback(
                "create_text_post",
                caption=text,
                reply_control=ReplyControl.EVERYONE,
                link_attachment_url=link,
            )
            thread_code = getattr(result, "code", "")
            thread_id = getattr(result, "pk", "")
            logger.info(f"Thread posted: {thread_code[:20]}")
            human_delay("post_thread")
            return {"thread_code": thread_code, "thread_id": thread_id}
        except Exception as e:
            raise ThreadsAPIError(f"Post failed: {e}")
    
    def post_reply(self, parent_thread_code: str, text: str) -> dict:
        """Reply to an existing thread."""
        try:
            result = self._call_with_proxy_fallback("reply", post_id=parent_thread_code, text=text)
            thread_code = getattr(result, "code", "")
            logger.info(f"Reply posted to {parent_thread_code[:20]}: {thread_code[:20]}")
            human_delay("reply")
            return {"thread_code": thread_code}
        except Exception as e:
            raise ThreadsAPIError(f"Reply failed: {e}")
    
    # ── Feed ──
    
    def get_feed(self, count: int = 15) -> list:
        """Get the For You feed with humanized delay."""
        try:
            feed_page = self._call_with_proxy_fallback("get_feed")
            posts = list(feed_page.posts)[:count]
            logger.info(f"Feed: got {len(posts)} posts")
            human_delay("feed_read")
            
            result = []
            for p in posts:
                result.append({
                    "thread_code": getattr(p, "code", ""),
                    "pk": getattr(p, "pk", ""),
                    "id": getattr(p, "id", ""),
                    "username": getattr(p.user, "username", "") if hasattr(p, "user") else "",
                    "user_id": getattr(p.user, "pk", "") if hasattr(p, "user") else "",
                    "caption": (getattr(p, "caption", "") or ""),
                    "like_count": getattr(p, "like_count", 0),
                    "reply_count": getattr(p, "reply_count", 0),
                    "taken_at": getattr(p, "taken_at", 0),
                })
            return result
        except Exception as e:
            logger.warning(f"Feed fetch failed: {e}")
            return []
    
    def get_user_posts(self, count: int = 70) -> list:
        """Fetch the authenticated user's own recent posts for style learning."""
        try:
            user_id = self.auth.user_id
            if not user_id:
                logger.warning("No user_id available for profile fetch")
                return []
            profile_page = self._call_with_proxy_fallback("get_profile", user_id, first=count)
            posts = list(profile_page.posts)[:count]
            logger.info(f"Profile: got {len(posts)} own posts")
            human_delay("feed_read")
            result = []
            for p in posts:
                caption = (getattr(p, "caption", "") or "").strip()
                if len(caption) < 20:
                    continue
                result.append({
                    "caption": caption,
                    "like_count": getattr(p, "like_count", 0),
                    "reply_count": getattr(p, "reply_count", 0),
                })
            return result
        except Exception as e:
            logger.warning(f"Profile fetch failed: {e}")
            return []
    
    def find_reply_targets(self, count: int = 15, min_likes: int = 0) -> list:
        """Get feed posts, filter quality, return sorted by engagement."""
        feed = self.get_feed(count=count)
        targets = []
        seen_codes = set()
        
        for post in feed:
            code = post.get("thread_code", "")
            if not code or code in seen_codes:
                continue
            if min_likes > 0 and post.get("like_count", 0) < min_likes:
                continue
            
            seen_codes.add(code)
            targets.append({
                "thread_code": code,
                "pk": post.get("pk", ""),
                "username": post.get("username", ""),
                "caption": (post.get("caption", "") or "")[:300],
                "like_count": post.get("like_count", 0),
                "reply_count": post.get("reply_count", 0),
            })
        
        # Sort by engagement score
        targets.sort(key=lambda t: t["like_count"] + t["reply_count"] * 2, reverse=True)
        return targets[:count]
    
    def search_posts(self, query: str, count: int = 20) -> list:
        """Search Threads posts by keyword."""
        try:
            results = self._call_with_proxy_fallback("search_posts", query)
            posts = []
            for p in results[:count]:
                posts.append({
                    "thread_code": getattr(p, "code", ""),
                    "username": getattr(p.user, "username", "") if hasattr(p, "user") else "",
                    "caption": (getattr(p, "caption", "") or "")[:300],
                    "like_count": getattr(p, "like_count", 0),
                    "reply_count": getattr(p, "reply_count", 0),
                })
            human_delay("feed_read")
            return posts
        except Exception as e:
            logger.warning(f"Search failed: {e}")
            return []
    
    # ── Stats ──
    
    def get_post_stats(self, thread_code: str) -> dict:
        """Get like/reply counts for a thread we posted."""
        try:
            post = self._call_with_proxy_fallback("get_post", thread_code)
            if post and post.post:
                p = post.post
                return {
                    "likes": getattr(p, "like_count", 0),
                    "replies": getattr(p, "reply_count", 0),
                    "thread_code": thread_code,
                }
        except Exception as e:
            logger.warning(f"Stats fetch failed for {thread_code}: {e}")
        return {"likes": 0, "replies": 0, "thread_code": thread_code}
    
    def health_check(self) -> bool:
        """Verify auth is still valid."""
        try:
            self.auth.check_and_warn()
            return self.auth.is_valid()
        except Exception:
            return False
