"""SaaS App — Multi-Tenant Threads Growth Manager"""
import json, os, sys, secrets, hashlib, asyncio
from pathlib import Path
# Load .env before anything else
_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = val.strip()
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
# Load .env before anything else
_env_path = Path("/home/ubuntu/saas/.env")
if _env_path.exists():
    for line in _env_path.read_text().strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if "=" in line and not line.strip().startswith("#"):
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if val and not val.startswith("YOUR_") and not val.startswith("change"):
                os.environ.setdefault(key, val)
from fastapi import FastAPI, Request, Depends, HTTPException, Cookie
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from jose import jwt, JWTError
try:
    import stripe
except ImportError:
    stripe = None
import urllib.request
import time
from collections import defaultdict
from sqlalchemy import func, text
from database import User, Account, Schedule, Post, ContentPreset, ActivityLog, UsernameLock, init_db, get_db
from threads_login import login_threads, verify_cookies, ThreadsLoginError
from setup_logging import init_logging, get_logger
from ai import generate_thread, generate_reply, generate_fun_fact, learn_writing_style
from email_utils import send_verification_email, send_reset_email, BASE_URL
logger = get_logger(__name__)
# Sentry
SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN:
    import sentry_sdk
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=0.1)
    logger.info("✅ Sentry initialized")
else:
    logger.warning("⚠️  SENTRY_DSN not configured — error monitoring disabled")
logger = get_logger(__name__)
BASE_DIR = Path(os.path.dirname(__file__) or ".")
SECRET_KEY = os.environ.get("SAAS_SECRET", secrets.token_hex(32))
JWT_ALGO = "HS256"
COOKIE_NAME = "saas_token"
STRIPE_KEY = os.environ.get("STRIPE_KEY", "")
# ── PacketStream Proxy Config ──
PROXY_USER = "redkoohh"
PROXY_PASS = "f2f6ef17346136e8"
PROXY_HOST = "proxy.packetstream.io"
PROXY_PORT = "31112"
PROXY_BY_COUNTRY = {
    "United States": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-UnitedStates",
    "Canada": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-Canada",
    "United Kingdom": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-UnitedKingdom",
    "Australia": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-Australia",
    "Germany": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-Germany",
    "France": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-France",
    "Netherlands": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-Netherlands",
    "Singapore": f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-Singapore",
}
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logging()
    init_db()
    # ── DB health check ──
    try:
        db = next(get_db())
        row = db.execute(text("SELECT 1")).scalar()
        if row != 1:
            logger.error("❌ DB health check failed — SELECT 1 returned unexpected value")
        else:
            logger.info("✅ DB health check passed")
        db.close()
    except Exception as e:
        logger.error(f"❌ DB health check failed: {e}")
    logger.info("Threads SaaS starting up")
    from scheduler import scheduler_loop
    task = asyncio.create_task(scheduler_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Threads SaaS shutting down")
app = FastAPI(title="Threads Growth SaaS", lifespan=lifespan)
# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
# ── Auth Helpers ──
def create_token(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=30)}, SECRET_KEY, algorithm=JWT_ALGO)
def verify_password(password: str, stored: str) -> bool:
    try:
        salt, pwd_hash = stored.split("$", 1)
        return hashlib.sha256((password + salt).encode()).hexdigest() == pwd_hash
    except Exception:
        return False
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401)
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
        user = db.query(User).filter(User.id == int(data["sub"])).first()
        if not user:
            raise HTTPException(401)
        return user
    except JWTError:
        raise HTTPException(401)
# ── Serve static HTML (no Jinja2) ──
TEMPLATES = {
    "/terms": "terms.html",
    "/privacy": "privacy.html",
    "/": "dashboard.html",
    "/login": "login.html",
    "/signup": "signup.html",
    "/pricing": "pricing.html",
    "/billing/success": "billing_success.html",
}
def serve_html(name: str) -> HTMLResponse:
    path = BASE_DIR / "templates" / name
    if not path.exists():
        return HTMLResponse("Not found", 404)
    return HTMLResponse(path.read_text(encoding="utf-8"))
VERIFY_RESULT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Email Verification — Threads Growth</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f0f13;display:flex;align-items:center;justify-content:center;min-height:100vh;color:#e0e0e0;padding:20px}}
.card{{background:#1a1a24;border-radius:20px;padding:48px 40px;width:420px;max-width:100%;box-shadow:0 25px 80px rgba(0,0,0,0.5);border:1px solid #2a2a3a;text-align:center}}
.icon{{font-size:48px;margin-bottom:12px}}
.title{{font-size:20px;font-weight:700;margin-bottom:8px}}
.msg{{color:#888;font-size:14px;line-height:1.6}}
.btn{{display:inline-block;margin-top:20px;padding:12px 28px;border-radius:10px;background:linear-gradient(135deg,#a855f7,#ec4899);color:white;text-decoration:none;font-weight:600;font-size:14px}}
</style>
</head>
<body>
<div class="card">
  <div class="icon">{icon}</div>
  <div class="title" style="color:{color}">{title}</div>
  <div class="msg">{message}</div>
  {btn_html}
</div>
</body>
</html>"""
# ── Rate limiting (in-memory, per-IP) ──
@app.get("/api/me/geo")
async def api_geo(request: Request):
    """Detect client country from IP for proxy pre-selection."""
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    # Split x-forwarded-for chain, take first public IP
    ip = ip.split(",")[0].strip() if ip else "unknown"
    try:
        import urllib.request, json as _json
        req = urllib.request.Request(f"https://ipapi.co/{ip}/json/",
            headers={"User-Agent": "ThreadsSaaS/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read())
        return {"country_name": data.get("country_name", ""), "country_code": data.get("country_code", "")}
    except Exception:
        return {"country_name": "", "country_code": ""}
# ── Plan Config ──
PLANS = {
    "owner": {
        "name": "Owner", "price": "$0/mo",
        "max_accounts": 999, "max_schedules": 999, "max_posts_day": 99999,
        "feature_replies": True, "feature_style": True,
        "feature_audience": True, "feature_link_promo": True,
    },
    "starter": {
        "name": "Starter", "price": "$10/mo",
        "max_accounts": 1, "max_schedules": 12, "max_posts_day": 60,
        "feature_replies": True, "feature_style": True,
        "feature_audience": True, "feature_link_promo": True,
    },
    "growth": {
        "name": "Growth", "price": "$25/mo",
        "max_accounts": 3, "max_schedules": 12, "max_posts_day": 180,
        "feature_replies": True, "feature_style": True,
        "feature_audience": True, "feature_link_promo": True,
    },
    "agency": {
        "name": "Agency", "price": "$80/mo",
        "max_accounts": 15, "max_schedules": 12, "max_posts_day": 900,
        "feature_replies": True, "feature_style": True,
        "feature_audience": True, "feature_link_promo": True,
    },
}
# ── Pages ──
@app.get("/")
async def index(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
            db = next(get_db())
            user = db.query(User).filter(User.id == int(data["sub"])).first()
            db.close()
            if user and user.status == "active":
                return serve_html("dashboard.html")
        except Exception:
            pass
    return serve_html("landing.html")
@app.get("/login")
async def login_page():
    return serve_html("login.html")
@app.get("/signup")
async def signup_page():
    return serve_html("signup.html")
@app.get("/pricing")
async def pricing_page():
    return serve_html("pricing.html")
@app.get("/billing/success")
async def billing_success_page():
    return serve_html("billing_success.html")
@app.get("/terms")
async def terms_page():
    return serve_html("terms.html")
@app.get("/privacy")
async def privacy_page():
    return serve_html("privacy.html")
@app.get("/forgot-password")
async def forgot_password_page():
    return serve_html("forgot_password.html")
@app.get("/logout")
async def logout():
    resp = RedirectResponse("/")
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp
# ── SEO & Static ──
@app.get("/robots.txt")
async def robots():
    return FileResponse("static/robots.txt")
@app.get("/favicon.ico")
async def favicon_ico():
    return FileResponse("static/favicon.svg")
@app.get("/favicon.svg")
async def favicon_svg():
    return FileResponse("static/favicon.svg")
# ── Admin Panel ──
ADMIN_EMAIL = "growpilotgpt@gmail.com"
def require_admin(request: Request):
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401)
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGO])
        db = next(get_db())
        user = db.query(User).filter(User.id == int(data["sub"])).first()
        db.close()
        if not user or user.email != ADMIN_EMAIL:
            raise HTTPException(403)
        return user
    except (JWTError, HTTPException):
        raise HTTPException(403)
@app.get("/admin")
async def admin_page(request: Request):
    try:
        require_admin(request)
        return serve_html("admin.html")
    except HTTPException:
        return RedirectResponse("/login")
@app.get("/api/admin/users")
async def admin_users(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return {"users": [{"id": u.id, "email": u.email, "name": u.name,
        "plan": u.plan, "status": u.status, "email_verified": bool(u.email_verified),
        "account_count": len(u.accounts) if u.accounts else 0,
        "created_at": u.created_at.isoformat() if u.created_at else None} for u in users]}
@app.get("/api/admin/accounts")
async def admin_accounts(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    return {"accounts": [{"id": a.id, "username": a.username, "niche": a.niche,
        "active": a.active, "today_threads": a.today_threads, "today_replies": a.today_replies,
        "user_email": a.user.email if a.user else None} for a in accounts]}
@app.get("/api/admin/activity")
async def admin_activity(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    logs = db.query(ActivityLog).order_by(ActivityLog.posted_at.desc()).limit(500).all()
    return {"logs": [{"id": l.id, "account_id": l.account_id, "action": l.action,
        "detail": l.detail, "thread_code": l.thread_code,
        "posted_at": l.posted_at.isoformat() if l.posted_at else None} for l in logs]}
@app.post("/api/admin/users/{user_id}/toggle")
async def admin_toggle_user(user_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    u.status = "paused" if u.status == "active" else "active"
    db.commit()
    return {"ok": True, "status": u.status}
@app.post("/api/admin/users/{user_id}/plan")
async def admin_change_plan(user_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    body = await request.json()
    plan = body.get("plan", "starter")
    if plan not in PLANS: return JSONResponse({"error": "Invalid plan"}, 400)
    u.plan = plan
    db.commit()
    return {"ok": True, "plan": plan}
@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u: raise HTTPException(404)
    if u.email == ADMIN_EMAIL: return JSONResponse({"error": "Cannot delete admin"}, 403)
    db.delete(u)
    db.commit()
    return {"ok": True}
@app.post("/api/admin/accounts/{account_id}/toggle")
async def admin_toggle_account(account_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a: raise HTTPException(404)
    a.active = not a.active
    db.commit()
    return {"ok": True, "active": a.active}
# ── Auth API ──
LOGIN_ATTEMPTS = defaultdict(list)  # ip -> [timestamps]
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW = 300  # 5 minutes in seconds
def check_login_rate_limit(ip: str):
    now = time.time()
    attempts = LOGIN_ATTEMPTS[ip]
    # Prune old entries
    LOGIN_ATTEMPTS[ip] = [t for t in attempts if now - t < LOGIN_WINDOW]
    if len(LOGIN_ATTEMPTS[ip]) >= LOGIN_MAX_ATTEMPTS:
        retry_after = int(LOGIN_WINDOW - (now - LOGIN_ATTEMPTS[ip][0]))
        raise HTTPException(429, detail=f"Too many attempts. Try again in {retry_after}s")
    LOGIN_ATTEMPTS[ip].append(now)
# ── Auth API ──
@app.post("/api/auth/signup")
async def api_signup(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "").strip()
    # Force all new signups to Starter trial (free). Upgrade from dashboard.
    plan = "starter"
    check_login_rate_limit(request.client.host)
    if not email or not password:
        return JSONResponse({"error": "Email and password required"}, 400)
    if len(password) < 6:
        return JSONResponse({"error": "Password must be 6+ characters"}, 400)
    if db.query(User).filter(User.email == email).first():
        return JSONResponse({"error": "Email already registered"}, 400)
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    stored = f"{salt}${pwd_hash}"
    verif_token = secrets.token_urlsafe(32)
    user = User(email=email, name=name, password_hash=stored, plan=plan,
                status="active", email_verified=False, email_verification_token=verif_token,
                trial_expires_at=datetime.utcnow() + timedelta(days=3))
    db.add(user)
    db.commit()
    sent = send_verification_email(email, verif_token)
    logger.info(f"📧 Signup {email} plan={plan} — verification{' sent' if sent else ' FAILED to send'}")
    return {"ok": True, "message": "Check your email for the verification link",
            "verification_sent": sent, "email": email, "plan": plan}
@app.post("/api/auth/login")
async def api_login(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    check_login_rate_limit(request.client.host)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return JSONResponse({"error": "Invalid email or password"}, 401)
    if user.status != "active":
        return JSONResponse({"error": "Account is " + user.status}, 403)
    if not user.email_verified:
        return JSONResponse({
            "error": "Please verify your email first",
            "unverified": True,
            "email": user.email
        }, 403)
    token = create_token(user.id)
    resp = JSONResponse({"ok": True, "token": token})
    resp.set_cookie(COOKIE_NAME, token, max_age=2592000, path="/", httponly=True, secure=True, samesite="lax")
    return resp
@app.post("/api/auth/resend-verification")
async def api_resend_verification(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email:
        return JSONResponse({"error": "Email required"}, 400)
    user = db.query(User).filter(User.email == email).first()
    if not user or user.email_verified:
        return JSONResponse({"error": "No unverified account with that email"}, 400)
    verif_token = secrets.token_urlsafe(32)
    user.email_verification_token = verif_token
    db.commit()
    sent = send_verification_email(email, verif_token)
    return {"ok": True, "message": "Verification email resent", "sent": sent}
@app.get("/api/auth/verify-email")
async def api_verify_email(token: str = "", db: Session = Depends(get_db)):
    if not token:
        return JSONResponse({"error": "Token required"}, 400)
    user = db.query(User).filter(User.email_verification_token == token).first()
    if not user:
        return JSONResponse({"error": "Invalid or expired verification link"}, 400)
    user.email_verified = True
    user.email_verification_token = ""
    db.commit()
    logger.info(f"✅ Email verified for user {user.id} ({user.email})")
    return {"ok": True, "message": "Email verified! You can now sign in."}
@app.get("/verify-email")
async def verify_email_page(token: str = "", db: Session = Depends(get_db)):
    """HTML page users land on after clicking verification link in email."""
    if token:
        user = db.query(User).filter(User.email_verification_token == token).first()
        if user:
            user.email_verified = True
            user.email_verification_token = ""
            db.commit()
            icon = "✅"
            color = "#22c55e"
            title = "Email Verified!"
            message = "You can now sign in to your account and start growing your Threads presence."
            btn_html = '<a href="/login" class="btn">Sign In</a>'
            logger.info(f"✅ Email verified for {user.email}")
        else:
            icon = "❌"
            color = "#ef4444"
            title = "Verification Failed"
            message = "Invalid or expired verification link."
            btn_html = '<a href="/signup" class="btn">Sign Up</a>'
    else:
        icon = "❌"
        color = "#ef4444"
        title = "Missing Token"
        message = "No verification token provided. Check your email for the full link."
        btn_html = '<a href="/login" class="btn">Sign In</a>'
    return HTMLResponse(VERIFY_RESULT_HTML.format(icon=icon, color=color, title=title, message=message, btn_html=btn_html))
# ── Password Reset ──
@app.post("/api/auth/forgot-password")
async def api_forgot_password(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    email = body.get("email", "").strip().lower()
    if not email:
        return JSONResponse({"error": "Email required"}, 400)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"ok": True, "message": "If that email exists, a reset link was sent"}
    reset_token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=1)
    user.reset_token = reset_token
    user.reset_token_expires = expires
    db.commit()
    sent = send_reset_email(email, reset_token)
    logger.info(f"🔑 Password reset sent to {email} — {'sent' if sent else 'FAILED'}")
    return {"ok": True, "message": "If that email exists, a reset link was sent", "sent": sent}
@app.post("/api/auth/reset-password")
async def api_reset_password(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    token = body.get("token", "").strip()
    password = body.get("password", "")
    if not token or not password:
        return JSONResponse({"error": "Token and password required"}, 400)
    if len(password) < 6:
        return JSONResponse({"error": "Password must be 6+ characters"}, 400)
    now = datetime.utcnow()
    user = db.query(User).filter(
        User.reset_token == token,
        User.reset_token_expires.isnot(None),
        User.reset_token_expires > now
    ).first()
    if not user:
        return JSONResponse({"error": "Invalid or expired reset token"}, 400)
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    stored = f"{salt}${pwd_hash}"
    user.password_hash = stored
    user.reset_token = ""
    user.reset_token_expires = None
    db.commit()
    logger.info(f"🔑 Password reset completed for user {user.id} ({user.email})")
    return {"ok": True}
@app.get("/api/me")
async def api_me(user: User = Depends(get_current_user)):
    plan_cfg = PLANS.get(user.plan, PLANS["starter"])
    now = datetime.utcnow()
    trial_days_left = None
    trial_expired = False
    if user.trial_expires_at:
        remaining = (user.trial_expires_at - now).days
        trial_days_left = max(0, remaining)
        trial_expired = remaining <= 0
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "plan": user.plan, "plan_config": plan_cfg, "status": user.status,
        "trial_expires_at": user.trial_expires_at.isoformat() if user.trial_expires_at else None,
        "trial_days_left": trial_days_left,
        "trial_expired": trial_expired,
    }
# ── Threads Login API ──
@app.post("/api/threads/login")
async def api_threads_login(request: Request, user: User = Depends(get_current_user)):
    """Login to a Threads account using email/password.
    
    Returns cookies that the frontend can pass to /api/accounts.
    Optionally proxies the login request through the selected country.
    """
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    country = body.get("country", "")
    
    if not username or not password:
        return JSONResponse({"error": "Username and password required"}, 400)
    
    # Build proxy string if country provided
    proxy = None
    if country and country in PROXY_BY_COUNTRY:
        proxy = PROXY_BY_COUNTRY[country]
    elif country:
        # Country not in the short list but selected in frontend — build from template
        proxy = f"{PROXY_HOST}:{PROXY_PORT}:{PROXY_USER}:{PROXY_PASS}_country-{country}"
    
    try:
        cookies = login_threads(username, password, proxy=proxy)
        return {
            "ok": True,
            "cookies": cookies,
            "username": username,
            "user_id": cookies.get("ds_user_id", ""),
        }
    except ThreadsLoginError as e:
        return JSONResponse({"error": str(e)}, 401)
    except Exception as e:
        return JSONResponse({"error": f"Login failed: {str(e)}"}, 500)
@app.post("/api/threads/verify")
async def api_threads_verify(request: Request, user: User = Depends(get_current_user)):
    """Verify that a set of cookies is still valid."""
    body = await request.json()
    cookies = body.get("cookies", {})
    if not cookies:
        return JSONResponse({"error": "Cookies required"}, 400)
    try:
        valid = verify_cookies(cookies)
        return {"ok": True, "valid": valid}
    except Exception as e:
        return {"ok": True, "valid": False, "error": str(e)}
# ── Accounts API ──
@app.get("/api/accounts")
async def api_accounts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    result = []
    for a in accounts:
        schedule_count = db.query(Schedule).filter(Schedule.account_id == a.id, Schedule.enabled == True).count()
        result.append({
            "id": a.id, "username": a.username, "display_name": a.display_name,
            "niche": a.niche, "active": a.active,
            "today_threads": a.today_threads, "today_replies": a.today_replies,
            "account_tags": a.account_tags or "[]",
            "schedules_active": schedule_count,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return result
@app.post("/api/accounts")
async def api_create_account(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(Account).filter(Account.user_id == user.id).count()
    limit = PLANS.get(user.plan, PLANS["starter"])["max_accounts"]
    if existing >= limit:
        return JSONResponse({"error": f"Plan limit: {limit} accounts. Upgrade to add more."}, 403)
    body = await request.json()
    username = (body.get("username") or "").strip().lower().lstrip("@")
    # Guard 1: same user can't add duplicate username
    dup = db.query(Account).filter(
        Account.user_id == user.id,
        Account.username == username
    ).first()
    if dup:
        return JSONResponse({"error": f"You already have @{username} connected."}, 409)
    # Guard 2: different user already owns this username (active)
    taken = db.query(Account).filter(
        Account.username == username,
        Account.user_id != user.id
    ).first()
    if taken:
        return JSONResponse({"error": f"@{username} is already connected to another account."}, 409)
    # Guard 3: username was previously claimed by another user (deleted but locked)
    locked = db.query(UsernameLock).filter(
        UsernameLock.username == username,
        UsernameLock.locked_by_user_id != user.id
    ).first()
    if locked:
        return JSONResponse({"error": f"@{username} was previously claimed and is permanently locked."}, 409)
    # Lock the username (idempotent — if this user already locked it, skip)
    existing_lock = db.query(UsernameLock).filter(
        UsernameLock.username == username
    ).first()
    if not existing_lock:
        db.add(UsernameLock(username=username, locked_by_user_id=user.id))
    account = Account(
        user_id=user.id,
        username=username,
        display_name=body.get("display_name", ""),
        bio=body.get("bio", ""),
        link=body.get("link", ""),
        niche=body.get("niche", "general"),
        proxy=body.get("proxy", ""),
        cookies_encrypted=json.dumps(body.get("cookies", [])),
        active=True,
    )
    db.add(account)
    db.flush()
    default_slots = [
        ("slot-1", 11), ("slot-2", 15), ("slot-3", 17),
        ("slot-4", 19), ("slot-5", 22), ("slot-6", 2),
    ]
    for name, hour in default_slots:
        db.add(Schedule(account_id=account.id, slot_name=name, hour_utc=hour))
    db.commit()
    return {"ok": True, "id": account.id}
@app.delete("/api/accounts/{account_id}")
async def api_delete_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    db.delete(account)
    db.commit()
    return {"ok": True}
@app.post("/api/accounts/{account_id}/toggle")
async def api_toggle_account(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    account.active = not account.active
    db.commit()
    return {"active": account.active}
@app.post("/api/accounts/{account_id}/learn-style")
async def api_learn_style(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fetch the account's last 70 posts and learn writing style from them."""
    from threads_saas import ThreadsAuthWrapper
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    try:
        cookies = json.loads(account.cookies_encrypted) if account.cookies_encrypted else {}
        if isinstance(cookies, list):
            cookies = {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}
        auth = ThreadsAuthWrapper.from_cookies(cookies, proxy=account.proxy or None)
        posts = auth.get_user_posts(count=70)
        auth.close()
    except Exception as e:
        return JSONResponse({"error": f"Failed to fetch posts: {str(e)}"}, 500)
    if not posts or len(posts) < 5:
        return JSONResponse({"ok": True, "style": "", "message": "Not enough posts found to learn style (need 5+)"}, 200)
    style = learn_writing_style(posts)
    account.writing_style = style
    db.commit()
    from logs.activity_logger import ActivityLogger
    act = ActivityLogger(account_id=account.id, username=account.username)
    act.success("style_learn", f"Learned writing style from {len(posts)} posts")
    return {"ok": True, "style": style, "posts_analyzed": len(posts)}
@app.get("/api/accounts/{account_id}/style")
async def api_get_style(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the learned writing style for an account."""
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    return {"style": account.writing_style or ""}
@app.post("/api/accounts/{account_id}/learn-and-go")
async def api_learn_and_go(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Quick one-shot: login, learn style, save — called right after account creation."""
    from threads_saas import ThreadsAuthWrapper
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    try:
        cookies = json.loads(account.cookies_encrypted) if account.cookies_encrypted else {}
        if isinstance(cookies, list):
            cookies = {c["name"]: c["value"] for c in cookies if "name" in c and "value" in c}
        auth = ThreadsAuthWrapper.from_cookies(cookies, proxy=account.proxy or None)
        posts = auth.get_user_posts(count=70)
        auth.close()
    except Exception as e:
        return JSONResponse({"ok": True, "style": "", "message": f"Style learning deferred: {str(e)}"}, 200)
    if posts and len(posts) >= 5:
        style = learn_writing_style(posts)
        account.writing_style = style
        db.commit()
        from logs.activity_logger import ActivityLogger
        ActivityLogger(account_id=account.id, username=account.username).success("style_learn", f"Learned writing style from {len(posts)} posts (auto)")
        logger.info(f"✅ Learned writing style for @{account.username} ({len(posts)} posts analyzed)")
        return {"ok": True, "style": style, "posts_analyzed": len(posts)}
    else:
        return {"ok": True, "style": "", "posts_analyzed": 0, "message": "Not enough posts yet"}
@app.post("/api/accounts/{account_id}/upgrade-style")
async def api_upgrade_style(account_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Upgrade an existing writing style by giving the AI an evolution direction."""
    from ai import STYLE_ANALYSIS_SYSTEM
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    body = await request.json()
    direction = body.get("direction", "").strip()
    if not direction:
        return JSONResponse({"ok": True, "style": account.writing_style, "message": "No direction given"}, 200)
    current_style = account.writing_style or ""
    prompt = f"""Current writing style signature:
{current_style}
Evolution direction requested by user:
{direction}
Rewrite the style signature to incorporate this evolution. Keep the same format and depth (3-4 paragraphs). The user's current style is the foundation — evolve it, don't replace it entirely. Be specific about how the new direction changes the voice.
New style signature:"""
    from ai import _call_ai
    messages = [
        {"role": "system", "content": STYLE_ANALYSIS_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    try:
        new_style = _call_ai(messages, max_tokens=600)
        account.writing_style = new_style
        db.commit()
        from logs.activity_logger import ActivityLogger
        ActivityLogger(account_id=account.id, username=account.username).success("style_upgrade", f"Upgraded style: {direction}")
        logger.info(f"✅ Upgraded style for @{account.username}: {direction}")
        return {"ok": True, "style": new_style}
    except Exception as e:
        return JSONResponse({"error": f"Upgrade failed: {str(e)}"}, 500)
@app.post("/api/accounts/{account_id}/update-style")
async def api_update_style(account_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Manually set the writing style (edit)."""
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    body = await request.json()
    account.writing_style = body.get("style", "")
    db.commit()
    from logs.activity_logger import ActivityLogger
    ActivityLogger(account_id=account.id, username=account.username).info("style_upgrade", "Manually edited writing style")
    return {"ok": True}
# ── Activity Logs API ──
@app.get("/api/accounts/{account_id}/activity")
async def api_activity(account_id: int, limit: int = 50, offset: int = 0,
                       action: str = None,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get paginated activity logs for an account."""
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    from logs.activity_logger import get_activity
    return get_activity(db, account_id, limit=limit, offset=offset, action_filter=action)
# ── Schedules API ──
@app.get("/api/schedules/all")
async def api_schedules_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get all schedules across all accounts for the unified timeline view."""
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    if not accounts:
        return []
    ids = [a.id for a in accounts]
    schedules = db.query(Schedule).filter(Schedule.account_id.in_(ids)).order_by(Schedule.hour_utc).all()
    # Determine which slots ran today
    today = datetime.utcnow().date()
    
    result = []
    for s in schedules:
        ran_today = s.last_run and s.last_run.date() == today and s.last_status == "success"
        account = next((a for a in accounts if a.id == s.account_id), None)
        result.append({
            "id": s.id,
            "account_id": s.account_id,
            "username": account.username if account else "unknown",
            "display_name": account.display_name if account else "",
            "slot_name": s.slot_name,
            "hour_utc": s.hour_utc,
            "post_type": s.post_type or "thread",
            "enabled": s.enabled,
            "last_run": s.last_run.isoformat() if s.last_run else None,
            "last_status": s.last_status or "never",
            "ran_today": ran_today,
            "active": account.active if account else False,
        })
    return result
@app.get("/api/accounts/{account_id}/schedules")
async def api_schedules(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    schedules = db.query(Schedule).filter(Schedule.account_id == account_id).order_by(Schedule.hour_utc).all()
    return [{"id": s.id, "slot_name": s.slot_name, "hour_utc": s.hour_utc, "enabled": s.enabled,
             "last_run": s.last_run.isoformat() if s.last_run else None, "last_status": s.last_status,
             "post_type": s.post_type or "thread"} for s in schedules]
@app.post("/api/accounts/{account_id}/schedules/{schedule_id}/toggle")
async def api_toggle_schedule(account_id: int, schedule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.account_id == account_id).first()
    if not sched:
        raise HTTPException(404)
    sched.enabled = not sched.enabled
    db.commit()
    return {"enabled": sched.enabled}
# ── Posts API ──
@app.get("/api/posts")
async def api_posts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    if not accounts:
        return []
    ids = [a.id for a in accounts]
    posts = db.query(Post).filter(Post.account_id.in_(ids)).order_by(Post.posted_at.desc()).limit(50).all()
    acct_map = {a.id: a for a in accounts}
    return [{"id": p.id, "account_id": p.account_id, "account_name": (acct_map[p.account_id].display_name or acct_map[p.account_id].username) if p.account_id in acct_map else None,
             "type": p.post_type, "code": p.thread_code,
             "preview": p.content_preview, "posted_at": p.posted_at.isoformat() if p.posted_at else None,
             "likes": p.likes, "replies": p.replies} for p in posts]
# ── Stats API ──
@app.get("/api/stats")
async def api_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    today_threads = 0
    today_replies = 0
    for a in accounts:
        today_threads += a.today_threads
        today_replies += a.today_replies
    return {
        "accounts": len(accounts),
        "active_accounts": sum(1 for a in accounts if a.active),
        "today_threads": today_threads,
        "today_replies": today_replies,
    }
# ── Schedule CRUD ──
@app.post("/api/accounts/{account_id}/schedules")
async def api_create_schedule(account_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    body = await request.json()
    hour = body.get("hour_utc", 12)
    name = body.get("slot_name", f"slot-{hour}")
    ptype = body.get("post_type", "thread")
    # Check for dup hour
    existing = db.query(Schedule).filter(Schedule.account_id == account_id, Schedule.hour_utc == hour).first()
    if existing:
        return JSONResponse({"error": f"Slot at UTC {hour}:00 already exists"}, 400)
    total = db.query(Schedule).filter(Schedule.account_id == account_id).count()
    plan_max = PLANS.get(user.plan, PLANS["starter"]).get("max_schedules", 6)
    if total >= plan_max:
        return JSONResponse({"error": f"Plan limit: {plan_max} slots. Upgrade to add more."}, 403)
    sched = Schedule(account_id=account_id, slot_name=name, hour_utc=hour, enabled=True, post_type=ptype)
    db.add(sched)
    db.commit()
    return {"ok": True, "id": sched.id}
@app.delete("/api/accounts/{account_id}/schedules/{schedule_id}")
async def api_delete_schedule(account_id: int, schedule_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.account_id == account_id).first()
    if not sched:
        raise HTTPException(404)
    db.delete(sched)
    db.commit()
    return {"ok": True}
# ── Account Detail + History API ──
@app.get("/api/accounts/{account_id}/detail")
async def api_account_detail(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    # Last 7 posts for this account
    recent_posts = db.query(Post).filter(Post.account_id == account_id).order_by(Post.posted_at.desc()).limit(7).all()
    # Total stats
    total_posts = db.query(Post).filter(Post.account_id == account_id).count()
    total_likes = db.query(func.coalesce(func.sum(Post.likes), 0)).filter(Post.account_id == account_id).scalar()
    total_replies_rcvd = db.query(func.coalesce(func.sum(Post.replies), 0)).filter(Post.account_id == account_id).scalar()
    schedule_count = db.query(Schedule).filter(Schedule.account_id == account_id, Schedule.enabled == True).count()
    plan_cfg = PLANS.get(user.plan, PLANS["starter"])
    return {
        "id": account.id,
        "username": account.username,
        "display_name": account.display_name,
        "bio": account.bio,
        "link": account.link,
        "niche": account.niche,
        "proxy": account.proxy,
        "active": account.active,
        "account_tags": account.account_tags or "[]",
        # targets
        "target_threads": account.target_threads,
        "target_replies": account.target_replies,
        # limits
        "max_threads": account.max_threads,
        "max_replies": account.max_replies,
        "sleep_hours_start": account.sleep_hours_start,
        "sleep_hours_end": account.sleep_hours_end,
        # style
        "content_style": account.content_style,
        "vibe": account.vibe,
        "post_tone": account.post_tone,
        "post_length": account.post_length,
        "post_format": account.post_format,
        "topic_keywords": account.topic_keywords,
        "avoid_topics": account.avoid_topics,
        "links_enabled": account.links_enabled,
        # style learning
        "writing_style": account.writing_style or "",
        # audience
        "target_niche": account.target_niche,
        "target_follower_min": account.target_follower_min,
        "target_follower_max": account.target_follower_max,
        # replies
        "reply_keywords": account.reply_keywords,
        "reply_tone": account.reply_tone,
        "reply_length": account.reply_length,
        "viral_threshold": account.viral_threshold,
        # stats
        "today_threads": account.today_threads,
        "today_replies": account.today_replies,
        "total_posts": total_posts,
        "total_likes": total_likes,
        "total_replies_rcvd": total_replies_rcvd,
        "schedules_active": schedule_count,
        "plan_config": plan_cfg,
        "recent_posts": [{"id": p.id, "type": p.post_type, "code": p.thread_code,
                          "preview": p.content_preview or "(no preview)",
                          "posted_at": p.posted_at.isoformat() if p.posted_at else None,
                          "likes": p.likes, "replies": p.replies} for p in recent_posts],
    }
@app.put("/api/accounts/{account_id}/settings")
async def api_account_settings(account_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update account targets, content style, audience, reply strategy, and limits."""
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    body = await request.json()
    plan_cfg = PLANS.get(user.plan, PLANS["starter"])
    for field in ["target_threads", "target_replies",
                   "max_threads", "max_replies",
                   "sleep_hours_start", "sleep_hours_end",
                   "viral_threshold",
                   "target_follower_min", "target_follower_max"]:
        if field in body:
            setattr(account, field, max(0, int(body[field])))
    for field in ["content_style", "vibe", "post_tone", "post_length", "post_format",
                   "topic_keywords", "avoid_topics",
                   "target_niche",
                   "reply_keywords", "reply_tone", "reply_length"]:
        if field in body:
            setattr(account, field, str(body[field]))
    if "account_tags" in body:
        tags = body["account_tags"]
        if isinstance(tags, list):
            account.account_tags = json.dumps(tags)
        else:
            account.account_tags = str(tags)
    # Plan-gated
    if plan_cfg["feature_link_promo"]:
        if "links_enabled" in body:
            account.links_enabled = bool(body["links_enabled"])
    db.commit()
    return {"ok": True}
@app.get("/api/accounts/{account_id}/posts")
async def api_account_posts(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    posts = db.query(Post).filter(Post.account_id == account_id).order_by(Post.posted_at.desc()).limit(50).all()
    return [{"id": p.id, "type": p.post_type, "code": p.thread_code,
             "preview": p.content_preview or "(no preview)",
             "posted_at": p.posted_at.isoformat() if p.posted_at else None,
             "likes": p.likes, "replies": p.replies} for p in posts]
@app.get("/api/stats/history")
async def api_stats_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    accounts = db.query(Account).filter(Account.user_id == user.id).all()
    if not accounts:
        return []
    ids = [a.id for a in accounts]
    # Group posts by date
    results = db.query(
        func.date(Post.posted_at).label("day"),
        func.count(Post.id).label("total_posts"),
        func.sum(Post.likes).label("total_likes"),
        func.sum(Post.replies).label("total_replies"),
    ).filter(Post.account_id.in_(ids)).group_by(func.date(Post.posted_at)).order_by(func.date(Post.posted_at).desc()).limit(14).all()
    return [{"day": r.day, "posts": r.total_posts, "likes": r.total_likes or 0, "replies": r.total_replies or 0} for r in results]
# ── Billing / Stripe ──
@app.post("/api/billing/create-checkout")
async def api_create_checkout(request: Request, user: User = Depends(get_current_user)):
    if not STRIPE_KEY:
        return JSONResponse({"error": "Stripe not configured"}, 503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    plan = body.get("plan", user.plan or "starter")
    try:
        stripe.api_key = STRIPE_KEY
        prices = {
            "starter": os.environ.get("STRIPE_PRICE_STARTER", "price_starter"),
            "growth": os.environ.get("STRIPE_PRICE_GROWTH", "price_growth"),
            "agency": os.environ.get("STRIPE_PRICE_AGENCY", "price_agency"),
        }
        price_id = prices.get(plan)
        if not price_id:
            return JSONResponse({"error": f"No price for plan: {plan}"}, 400)
        checkout = stripe.checkout.Session.create(
            customer_email=user.email,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{BASE_URL}/billing/success",
            cancel_url=f"{BASE_URL}/pricing",
            metadata={"user_id": str(user.id), "plan": plan},
        )
        return {"url": checkout.url}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)
@app.post("/api/billing/portal")
async def api_billing_portal(user: User = Depends(get_current_user)):
    if not STRIPE_KEY:
        return JSONResponse({"error": "Stripe not configured"}, 503)
    if not user.stripe_customer_id:
        return JSONResponse({"error": "No subscription yet"}, 400)
    try:
        stripe.api_key = STRIPE_KEY
        portal = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{BASE_URL}/dashboard",
        )
        return {"url": portal.url}
    except Exception as e:
        return JSONResponse({"error": str(e)}, 500)
@app.post("/api/stripe/webhook")
async def api_stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if webhook_secret:
        try:
            stripe.api_key = STRIPE_KEY
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
            logger.info(f"Stripe webhook: {event['type']}")
            if event["type"] == "checkout.session.completed":
                session = event["data"]["object"]
                user_id = int(session.get("metadata", {}).get("user_id", 0))
                if user_id:
                    db = next(get_db())
                    user = db.query(User).filter(User.id == user_id).first()
                    if user:
                        user.status = "active"
                        db.commit()
                    db.close()
            elif event["type"] == "customer.subscription.deleted":
                subscription = event["data"]["object"]
                customer_id = subscription.get("customer", "")
                db = next(get_db())
                user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
                if user:
                    user.status = "canceled"
                    user.plan = "starter"
                    db.commit()
                db.close()
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return JSONResponse({"error": str(e)}, 400)
    return {"ok": True}
# ── Content Presets API ──
@app.get("/api/presets")
async def api_presets(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    presets = db.query(ContentPreset).filter(ContentPreset.user_id == user.id).order_by(ContentPreset.created_at.desc()).all()
    return [{"id": p.id, "name": p.name, "settings": json.loads(p.settings_json or "{}"),
             "created_at": p.created_at.isoformat() if p.created_at else None} for p in presets]
@app.post("/api/presets")
async def api_create_preset(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Preset name required"}, 400)
    settings = body.get("settings", {})
    preset = ContentPreset(user_id=user.id, name=name, settings_json=json.dumps(settings))
    db.add(preset)
    db.commit()
    return {"ok": True, "id": preset.id}
@app.put("/api/presets/{preset_id}")
async def api_update_preset(preset_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preset = db.query(ContentPreset).filter(ContentPreset.id == preset_id, ContentPreset.user_id == user.id).first()
    if not preset:
        raise HTTPException(404)
    body = await request.json()
    if "name" in body:
        preset.name = body["name"].strip()
    if "settings" in body:
        preset.settings_json = json.dumps(body["settings"])
    db.commit()
    return {"ok": True}
@app.delete("/api/presets/{preset_id}")
async def api_delete_preset(preset_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preset = db.query(ContentPreset).filter(ContentPreset.id == preset_id, ContentPreset.user_id == user.id).first()
    if not preset:
        raise HTTPException(404)
    db.delete(preset)
    db.commit()
    return {"ok": True}
@app.post("/api/presets/{preset_id}/apply/{account_id}")
async def api_apply_preset(preset_id: int, account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    preset = db.query(ContentPreset).filter(ContentPreset.id == preset_id, ContentPreset.user_id == user.id).first()
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not preset or not account:
        raise HTTPException(404)
    settings = json.loads(preset.settings_json or "{}")
    for field in ["content_style", "vibe", "post_tone", "post_length", "post_format",
                   "topic_keywords", "avoid_topics", "links_enabled",
                   "target_niche",
                   "target_follower_min", "target_follower_max",
                   "reply_keywords", "reply_tone", "reply_length", "viral_threshold",
                   "target_threads", "target_replies", "max_threads", "max_replies",
                   "sleep_hours_start", "sleep_hours_end"]:
        if field in settings:
            setattr(account, field, settings[field])
    db.commit()
    return {"ok": True, "applied_fields": list(settings.keys())}
# ── Risk Score API ──
@app.get("/api/accounts/{account_id}/risk")
async def api_account_risk(account_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    account = db.query(Account).filter(Account.id == account_id, Account.user_id == user.id).first()
    if not account:
        raise HTTPException(404)
    risk = 0
    reasons = []
    # Fresh accounts with high targets
    if account.target_threads > 5:
        risk += 15
        reasons.append(f"High thread target ({account.target_threads}/day)")
    if account.target_replies > 20:
        risk += 15
        reasons.append(f"High reply target ({account.target_replies}/day)")
    # Fast posting
    if account.sleep_hours_start == account.sleep_hours_end:
        risk += 10
        reasons.append("No sleep hours — 24/7 posting flags bots")
    # Content breadth
    if account.avoid_topics:
        risk -= 5
        reasons.append("Avoid topics set — good safety net")
    else:
        risk += 5
        reasons.append("No blocked topics — risk of hot-button content")
    # Age
    age_days = 0
    if account.created_at:
        age_days = (datetime.utcnow() - account.created_at).days
    if age_days < 3:
        risk += 15
        reasons.append(f"Very fresh account ({age_days or '<1'} days old)")
    elif age_days < 14:
        risk += 5
    # Today's activity spike
    total_today = account.today_threads + account.today_replies
    if total_today > 25:
        risk += 10
        reasons.append(f"High today activity ({total_today} actions)")
    # Posting without niche
    if not account.target_niche and account.niche == "general":
        risk += 5
        reasons.append("No niche targeting — broad posting")
    # Viral threshold too low
    if account.viral_threshold < 10:
        risk += 5
        reasons.append("Very low viral threshold")
    # Lockout safety
    if account.sleep_hours_start != account.sleep_hours_end:
        risk -= 10
    risk = max(0, min(100, risk))
    level = "low" if risk < 25 else "medium" if risk < 50 else "high"
    return {
        "score": risk,
        "level": level,
        "reasons": reasons,
        "safe": risk < 50,
    }
# ── Batch Apply API ──
@app.post("/api/accounts/batch-apply")
async def api_batch_apply(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    body = await request.json()
    account_ids = body.get("account_ids", [])
    settings = body.get("settings", {})
    if not account_ids or not settings:
        return JSONResponse({"error": "account_ids and settings required"}, 400)
    count = 0
    for aid in account_ids:
        account = db.query(Account).filter(Account.id == aid, Account.user_id == user.id).first()
        if not account:
            continue
        for field in settings:
            if hasattr(account, field):
                setattr(account, field, settings[field])
        count += 1
    db.commit()
    return {"ok": True, "updated": count}
# ── Scheduler Manual Trigger ──
@app.post("/api/scheduler/run-now/{account_id}")
async def api_scheduler_run_now(account_id: int, user: User = Depends(get_current_user)):
    from scheduler import run_account_now
    result = await run_account_now(account_id)
    if "error" in result:
        return JSONResponse(result, 400)
    return result
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "9101"))
    uvicorn.run(app, host="0.0.0.0", port=port)
