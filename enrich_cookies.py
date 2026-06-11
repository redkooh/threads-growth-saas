"""One-time browser refresh to enrich cookies with full session params.

Run this once per account after adding it to the DB. It uses Playwright 
(headless Chromium) to capture __dyn, __csr, __hsdp, etc. that the 
lightweight HTML parse misses. These are critical — without them, Instagram
sees an automated client and triggers robot detection checkpoints.
"""
import json, os, sys, sqlite3
sys.path.insert(0, '/home/ubuntu/threads-growth/threads-unofficial-api')
sys.path.insert(0, '/home/ubuntu/saas')

from threads.auth import ThreadsAuth

DB_PATH = "/home/ubuntu/saas/saas.db"


def enrich_account(account_id: int, proxy: str = None) -> bool:
    """Browser-refresh session for an account. Returns True on success."""
    
    # Load cookies from DB
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT cookies_encrypted FROM accounts WHERE id=?", (account_id,)
    ).fetchone()
    if not row or not row[0]:
        print(f"❌ Account {account_id}: no cookies found")
        conn.close()
        return False
    
    cookies_list = json.loads(row[0])
    cookies = {c["name"]: c["value"] for c in cookies_list 
               if isinstance(c, dict) and "name" in c and "value" in c}
    conn.close()
    
    if "sessionid" not in cookies:
        print(f"❌ Account {account_id}: missing sessionid cookie")
        return False
    
    # Set proxy in env (library reads it)
    if proxy:
        os.environ["THREADS_PROXY"] = proxy
    
    print(f"📡 Account {account_id}: launching browser for full session refresh...")
    
    try:
        auth = ThreadsAuth.from_cookies(cookies)
        
        # Step 1: Lightweight refresh to get fb_dtsg, lsd
        auth.refresh_tokens()
        
        # Step 2: Browser refresh to get __dyn, __csr, __hsdp, etc.
        if not auth.refresh_from_browser(headless=True, timeout_ms=45000):
            print(f"❌ Account {account_id}: browser refresh returned False")
            return False
        
        print(f"✅ Session params captured: {list(auth.session_params.keys())}")
        print(f"   __dyn = {auth.session_params.get('__dyn', '')[:40]}...")
        print(f"   __csr = {auth.session_params.get('__csr', '')[:40]}...")
        print(f"   fb_dtsg = {'✅' if auth.fb_dtsg else '❌'}")
        print(f"   lsd = {'✅' if auth.lsd else '❌'}")
        
        # Update cookies in DB with any fresh ones from the session
        enriched_cookies = []
        for name, value in auth.cookies.items():
            enriched_cookies.append({"name": name, "value": value})
        
        # Also store session params alongside cookies (as a special key)
        # This way ThreadsAuthWrapper.restore_session_params() can reload them
        enriched_cookies.append({
            "name": "__session_params",
            "value": json.dumps(auth.session_params),
        })
        enriched_cookies.append({
            "name": "__fb_dtsg",
            "value": auth.fb_dtsg or "",
        })
        enriched_cookies.append({
            "name": "__lsd",
            "value": auth.lsd or "",
        })
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "UPDATE accounts SET cookies_encrypted=? WHERE id=?",
            (json.dumps(enriched_cookies), account_id)
        )
        conn.commit()
        conn.close()
        print(f"✅ Account {account_id}: cookies updated ({len(enriched_cookies)} cookies)")
        print(f"✅ Account {account_id}: full browser fingerprint captured!")
        return True
        
    except Exception as e:
        print(f"❌ Account {account_id}: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: python3 enrich_cookies.py <account_id> [proxy]")
        print("Example: python3 enrich_cookies.py 1 \"http://user:pass@proxy:31112\"")
        _sys.exit(1)
    
    aid = int(_sys.argv[1])
    proxy = _sys.argv[2] if len(_sys.argv) > 2 else None
    
    success = enrich_account(aid, proxy)
    print(f"\n{'✅ Done!' if success else '❌ Failed'}")
