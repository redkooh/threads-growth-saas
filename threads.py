"""Threads API wrapper — uses captured Instagram cookies for authenticated requests.

Threads shares Instagram's API infrastructure. This module wraps httpx with
auth cookies to post threads, replies, fetch trending content, and get stats.
"""
import json, random, re, time
import httpx
from setup_logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://www.threads.net"
API_BASE = "https://www.threads.net/api/v1"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://www.threads.net",
    "Referer": "https://www.threads.net/",
    "X-Requested-With": "XMLHttpRequest",
    "X-Instagram-AJAX": "1",
    "X-ASBD-ID": "129477",
    "X-IG-App-ID": "936619743392459",
    "Content-Type": "application/x-www-form-urlencoded",
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}


class ThreadsAPIError(Exception):
    """Raised when a Threads API call fails."""
    pass


# ── Humanization delays ──

def human_delay(action_type: str = "post"):
    """Sleep a random human-like delay based on action type."""
    delays = {
        "post_thread": (8, 18),
        "post_text": (6, 14),
        "reply": (6, 16),
        "feed_read": (2, 5),
        "like": (3, 8),
    }
    lo, hi = delays.get(action_type, (4, 10))
    secs = random.uniform(lo, hi)
    time.sleep(secs)


def _is_low_quality(post: dict) -> bool:
    """Heuristic: skip non-English, spam, hashtag-dumps, ultra-short posts."""
    caption = (post.get("caption", "") or "").strip()
    if not caption or len(caption) < 15:
        return True
    # More than 30% hashtags
    hashtag_ratio = caption.count("#") / max(len(caption.split()), 1)
    if hashtag_ratio > 0.3:
        return True
    # Non-English heuristic: count non-ASCII chars
    non_ascii = sum(1 for c in caption if ord(c) > 127)
    if len(caption) > 20 and non_ascii / len(caption) > 0.4:
        return True
    # Spam patterns: too many emojis, "follow for follow", "link in bio"
    spam_patterns = ["follow for follow", "f4f", "link in bio", "check my bio", "dm me"]
    if any(p in caption.lower() for p in spam_patterns):
        return True
    return False


class ThreadsAuth:
    """Authenticated HTTP client for Threads/Instagram API.

    Usage:
        auth = ThreadsAuth.from_cookies({"sessionid": "...", "csrftoken": "...", ...})
        auth.post_thread("Hello world")
    """

    def __init__(self, cookies: dict, proxy: str = None):
        """Initialize with auth cookies dict.

        Args:
            cookies: Dict with sessionid, csrftoken, ds_user_id (required)
            proxy: Optional proxy URL string
        """
        required = ["sessionid", "csrftoken"]
        missing = [k for k in required if k not in cookies]
        if missing:
            raise ValueError(f"Missing required cookies: {missing}")

        self.cookies = dict(cookies)
        self.ds_user_id = cookies.get("ds_user_id", "")

        client_kwargs = {
            "headers": {**DEFAULT_HEADERS, "X-CSRFToken": cookies["csrftoken"]},
            "cookies": self.cookies,
            "follow_redirects": True,
            "timeout": 30.0,
        }
        if proxy:
            client_kwargs["proxy"] = proxy

        self.http = httpx.Client(**client_kwargs)

    @classmethod
    def from_cookies(cls, cookies: dict, proxy: str = None) -> "ThreadsAuth":
        return cls(cookies, proxy)

    def close(self):
        self.http.close()

    def _post_json(self, url: str, data: dict) -> dict:
        """POST to Threads API and return parsed JSON."""
        resp = self.http.post(url, data=data)
        if resp.status_code >= 400:
            logger.error(f"API error {resp.status_code} from {url}: {resp.text[:300]}")
            raise ThreadsAPIError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        try:
            result = resp.json()
        except json.JSONDecodeError:
            raise ThreadsAPIError(f"Invalid JSON response from {url}")
        if result.get("status") == "fail":
            raise ThreadsAPIError(result.get("message", "Unknown API error"))
        return result

    # ── Posting ──

    def post_thread(self, text: str, link: str = None) -> dict:
        """Create a new thread (text post)."""
        data = {
            "publish_mode": "text_post",
            "text_post_app_info": json.dumps({
                "reply_control": 0,
                "is_auto_reply": False,
            }),
            "caption": text,
        }
        if link:
            data["link_attachment_url"] = link

        csrf = self.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf}
        resp = self.http.post(
            f"{API_BASE}/text_feed/create/",
            data=data,
            headers=headers,
        )
        if resp.status_code != 200:
            raise ThreadsAPIError(f"Post failed: HTTP {resp.status_code} {resp.text[:200]}")
        result = resp.json()
        thread_code = result.get("code", "")
        thread_id = result.get("id", "")
        logger.info(f"Thread posted: {thread_code[:20]}")
        human_delay("post_thread")
        return {"thread_code": thread_code, "thread_id": thread_id, "raw": result}

    def post_reply(self, parent_thread_code: str, text: str) -> dict:
        """Reply to an existing thread."""
        data = {
            "publish_mode": "text_post",
            "text_post_app_info": json.dumps({
                "reply_control": 0,
                "is_auto_reply": True,
            }),
            "caption": text,
            "parent_thread": parent_thread_code,
        }
        csrf = self.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf}
        resp = self.http.post(
            f"{API_BASE}/text_feed/create/",
            data=data,
            headers=headers,
        )
        if resp.status_code != 200:
            raise ThreadsAPIError(f"Reply failed: HTTP {resp.status_code} {resp.text[:200]}")
        result = resp.json()
        reply_code = result.get("code", "")
        logger.info(f"Reply posted: {reply_code[:20]}")
        human_delay("reply")
        return {"reply_code": reply_code, "raw": result}

    # ── Discovery / Feed ──

    def get_trending_posts(self, count: int = 10) -> list:
        """Fetch trending/recommended threads."""
        csrf = self.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf}
        resp = self.http.get(
            f"{API_BASE}/text_feed/recommended/",
            headers=headers,
            params={"count": count},
        )
        if resp.status_code != 200:
            raise ThreadsAPIError(f"Trending fetch failed: HTTP {resp.status_code}")
        result = resp.json()
        posts = []
        for item in result.get("media_items", result.get("items", [])):
            posts.append({
                "thread_code": item.get("code", ""),
                "username": item.get("user", {}).get("username", ""),
                "caption": (item.get("caption", "") or "")[:300],
                "like_count": item.get("like_count", 0),
                "reply_count": item.get("reply_count", 0),
            })
        return posts

    def get_feed(self, count: int = 20) -> list:
        """Fetch the For You feed — returns raw post dicts."""
        csrf = self.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf}
        resp = self.http.get(
            f"{API_BASE}/text_feed/feed/",
            headers=headers,
            params={"count": count, "feed_type": "top"},
        )
        if resp.status_code != 200:
            raise ThreadsAPIError(f"Feed fetch failed: HTTP {resp.status_code}")
        result = resp.json()
        items = result.get("media_items", result.get("items", []))
        feed = []
        for item in items:
            feed.append({
                "thread_code": item.get("code", ""),
                "pk": item.get("pk", ""),
                "id": item.get("id", ""),
                "username": item.get("user", {}).get("username", ""),
                "user_id": item.get("user", {}).get("pk", ""),
                "caption": (item.get("caption", "") or ""),
                "like_count": item.get("like_count", 0),
                "reply_count": item.get("reply_count", 0),
                "taken_at": item.get("taken_at", 0),
            })
        human_delay("feed_read")
        return feed

    def find_reply_targets(self, count: int = 15, min_likes: int = 0) -> list:
        """Get feed posts, filter quality, return sorted by engagement.

        Args:
            count: How many posts to fetch
            min_likes: Minimum like count to consider (viral threshold)

        Returns:
            List of dicts with thread_code, username, caption, like_count, reply_count
        """
        feed = self.get_feed(count=count)
        targets = []
        seen_codes = set()

        for post in feed:
            code = post.get("thread_code", "")
            if not code or code in seen_codes:
                continue
            if _is_low_quality(post):
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
        csrf = self.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf}
        resp = self.http.get(
            f"{API_BASE}/text_feed/search/",
            headers=headers,
            params={"q": query, "count": count},
        )
        if resp.status_code != 200:
            raise ThreadsAPIError(f"Search failed: HTTP {resp.status_code}")
        result = resp.json()
        posts = []
        for item in result.get("items", []):
            posts.append({
                "thread_code": item.get("code", ""),
                "username": item.get("user", {}).get("username", ""),
                "caption": (item.get("caption", "") or "")[:300],
                "like_count": item.get("like_count", 0),
                "reply_count": item.get("reply_count", 0),
            })
        human_delay("feed_read")
        return posts

    # ── Stats ──

    def get_post_stats(self, thread_code: str) -> dict:
        """Get like/reply counts for a thread we posted."""
        csrf = self.cookies.get("csrftoken", "")
        headers = {"X-CSRFToken": csrf}
        resp = self.http.get(
            f"{API_BASE}/text_feed/{thread_code}/",
            headers=headers,
        )
        if resp.status_code != 200:
            raise ThreadsAPIError(f"Stats fetch failed: HTTP {resp.status_code}")
        result = resp.json()
        item = result.get("item", result)
        return {
            "likes": item.get("like_count", 0),
            "replies": item.get("reply_count", 0),
            "thread_code": thread_code,
        }

    def health_check(self) -> bool:
        """Verify cookies are still valid."""
        try:
            resp = self.http.get(f"{BASE_URL}/", timeout=15.0)
            return resp.status_code == 200 and "login" not in resp.url.path.lower()
        except Exception:
            return False
