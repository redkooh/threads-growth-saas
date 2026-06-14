"""Threads Login — Reverse-engineered from Instagram/Threads web auth flow.

The login flow hijacking the Instagram web API (which Threads shares):
  1. GET instagram.com → grab csrftoken from Set-Cookie
  2. POST /api/v1/web/accounts/login/ajax/ with encrypted password
  3. On success: receive sessionid, ds_user_id, csrftoken, ig_did, mid
  4. Return as a dict ready for ThreadsAuth.from_cookies()
"""
import json
import time
import hashlib
import re
import httpx
from setup_logging import get_logger

logger = get_logger(__name__)

LOGIN_URL = "https://www.instagram.com/api/v1/web/accounts/login/ajax/"
HOME_URL = "https://www.instagram.com/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://www.instagram.com",
    "Referer": "https://www.instagram.com/",
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


class ThreadsLoginError(Exception):
    pass


def _encrypt_password(password: str) -> str:
    """Instagram encrypts passwords as #PWD_INSTAGRAM_BROWSER:0:ts:raw_password"""
    ts = int(time.time())
    return f"#PWD_INSTAGRAM_BROWSER:0:{ts}:{password}"


MAX_LOGIN_RETRIES = 15  # PacketStream rotates IPs per connection


def _build_proxy_client(proxy: str | None) -> httpx.Client:
    """Build an httpx Client, optionally routing through a PacketStream proxy.
    
    A new client means a new TCP connection, which means a fresh proxy exit IP.
    """
    proxy_mounts = {}
    if proxy:
        if not (proxy.startswith("http://") or proxy.startswith("https://") or proxy.startswith("socks")):
            try:
                parts = proxy.split(":", 2)
                proxy_url = f"http://{parts[2]}@{parts[0]}:{parts[1]}"
            except (IndexError, ValueError):
                logger.warning(f"Could not parse proxy for login: {proxy[:40]}...")
                proxy_url = None
        else:
            proxy_url = proxy
        if proxy_url:
            proxy_mounts = {
                "http://": httpx.HTTPTransport(proxy=proxy_url),
                "https://": httpx.HTTPTransport(proxy=proxy_url),
            }
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30.0, mounts=proxy_mounts)


def login_threads(username: str, password: str, proxy: str = None) -> dict:
    """Log in to Threads/Instagram and return auth cookies.

    Args:
        username: Threads/Instagram username or email
        password: Account password
        proxy: Optional proxy string (PacketStream format: host:port:user:pass_country-X)

    Returns:
        dict with keys: sessionid, ds_user_id, csrftoken, ig_did, mid, rur

    Raises:
        ThreadsLoginError: on invalid credentials, 2FA required, or network error
    """
    last_error = None
    for attempt in range(1, MAX_LOGIN_RETRIES + 1):
        if attempt > 1:
            wait = min(0.5 * (attempt - 1), 5)  # 0.5s, 1s, 1.5s ... capped at 5s
            logger.info(f"Login retry {attempt}/{MAX_LOGIN_RETRIES} (wait {wait:.1f}s)")
            time.sleep(wait)

        client = _build_proxy_client(proxy)
        try:
            # Step 1: GET homepage to obtain initial csrftoken + rollout_hash
            resp = client.get(HOME_URL)
            if "csrftoken" not in client.cookies:
                last_error = ThreadsLoginError("Failed to obtain initial csrftoken from Instagram")
                continue

            initial_csrftoken = client.cookies["csrftoken"]
            logger.info(f"Got initial csrftoken: {initial_csrftoken[:10]}...")

            # Extract rollout_hash from response body if present
            rollout_hash = ""
            match = re.search(r'"rollout_hash":"([^"]+)"', resp.text)
            if match:
                rollout_hash = match.group(1)

            # Extract mid if set
            mid = client.cookies.get("mid", "")

            # Step 2: Build login payload
            enc_password = _encrypt_password(password)
            data = {
                "enc_password": enc_password,
                "username": username,
                "queryParams": "{}",
                "optIntoOneTap": "false",
                "stopDeletionNonce": "",
                "trustedDeviceRecords": "{}",
            }

            # Set CSRF header from the cookie we just got
            headers = {
                "X-CSRFToken": initial_csrftoken,
                "X-Instagram-AJAX": "1",
            }

            # Step 3: POST login
            resp = client.post(LOGIN_URL, data=data, headers=headers)

            try:
                result = resp.json()
            except json.JSONDecodeError:
                last_error = ThreadsLoginError(f"Invalid JSON response: {resp.text[:300]}")
                continue

            # Check for 2FA requirement — real 2FA, do NOT retry
            if result.get("two_factor_required"):
                raise ThreadsLoginError(
                    "Two-factor authentication is enabled on this account. "
                    "Please log in via browser first, then export cookies."
                )

            # Check for checkpoint (suspicious login) — proxy IP was flagged, RETRY
            if result.get("checkpoint_url"):
                logger.info(f"Attempt {attempt}: checkpoint_url (proxy flagged) — retrying with new IP")
                last_error = ThreadsLoginError(
                    "Login requires security checkpoint. "
                    "Please log in via browser first, then export cookies."
                )
                continue

            # Check for challenge errors — proxy IP was flagged, RETRY
            if not result.get("authenticated") and not result.get("status") == "ok":
                error_msg = result.get("message", "Unknown login error")
                if "challenge" in error_msg.lower() or "checkpoint" in str(result):
                    logger.info(f"Attempt {attempt}: challenge/checkpoint response — retrying with new IP")
                    last_error = ThreadsLoginError(
                        "Login requires security checkpoint. "
                        "Log in via browser first, then export cookies."
                    )
                    continue
                raise ThreadsLoginError(f"Login failed: {error_msg}")

            # Step 4: Extract cookies from the jar
            required = ["sessionid", "ds_user_id", "csrftoken", "ig_did", "mid", "rur"]
            auth_cookies = {}

            for name in required:
                if name in client.cookies:
                    auth_cookies[name] = client.cookies[name]

            # Verify we got the critical ones
            missing = [k for k in ["sessionid", "ds_user_id", "csrftoken"] if k not in auth_cookies]
            if missing:
                logger.info(f"Attempt {attempt}: missing critical cookies {missing} (proxy detected) — retrying with new IP")
                last_error = ThreadsLoginError(
                    f"Login succeeded but missing critical cookies: {missing}. "
                    f"Got: {list(auth_cookies.keys())}"
                )
                continue

            logger.info(f"Login success on attempt {attempt}! user_id={auth_cookies.get('ds_user_id')}")
            return auth_cookies

        except ThreadsLoginError:
            raise
        except Exception as e:
            # Network-level errors — could be proxy flaky, retry
            logger.info(f"Attempt {attempt}: network error ({e}) — retrying with new IP")
            last_error = e
        finally:
            try:
                client.close()
            except Exception:
                pass

    # All retries exhausted
    raise ThreadsLoginError(
        f"Login failed after {MAX_LOGIN_RETRIES} attempts"
        + (f": {last_error}" if last_error else "")
    )


def verify_cookies(cookies: dict) -> bool:
    """Verify that a set of cookies is valid by making a lightweight API call.

    Args:
        cookies: Dict with at least sessionid, ds_user_id, csrftoken

    Returns:
        True if cookies are valid
    """
    try:
        from threads import ThreadsAuth
        auth = ThreadsAuth.from_cookies(cookies)
        valid = auth.health_check()
        auth.close()
        return valid
    except Exception as e:
        logger.warning(f"Cookie validation failed: {e}")
        return False
