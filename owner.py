"""Owner Dashboard — oversee all SaaS subscribers."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before anything
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    for line in open(_env_path):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            if k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()

from pathlib import Path
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from database import User, Account, Post, ActivityLog, Schedule, get_db

app = FastAPI(title="Owner Dashboard")

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
PLANS = {
    "owner":   {"name": "Owner",  "price": 0},
    "starter":  {"name": "Starter", "price": 10},
    "growth":   {"name": "Growth",  "price": 25},
    "agency":   {"name": "Agency",  "price": 80},
}


def serve_html(name: str) -> HTMLResponse:
    path = TEMPLATES_DIR / name
    if not path.exists():
        return HTMLResponse(f"<h1>404 - {name} not found</h1>", status_code=404)
    return HTMLResponse(path.read_text(encoding="utf-8"))


# ── API ──

@app.get("/api/owner/stats")
def owner_stats(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.status == "active").count()
    paused_users = db.query(User).filter(User.status == "paused").count()

    # Plans
    from sqlalchemy import func
    plan_rows = db.query(User.plan, func.count(User.id)).group_by(User.plan).all()
    plans_detail = {p: c for p, c in plan_rows}

    # Trial
    trial_active = db.query(User).filter(
        User.trial_expires_at.isnot(None),
        User.trial_expires_at > now
    ).count()
    trial_expired = db.query(User).filter(
        User.trial_expires_at.isnot(None),
        User.trial_expires_at <= now
    ).count()

    # Email verified
    verified = db.query(User).filter(User.email_verified == True).count()
    unverified = db.query(User).filter(User.email_verified == False).count()

    # Accounts
    total_accounts = db.query(Account).count()
    active_accounts = db.query(Account).filter(Account.active == True).count()
    paused_accounts = db.query(Account).filter(Account.active == False).count()

    # Activity today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    posts_today = db.query(Post).filter(Post.posted_at >= today_start).count()
    activity_today = db.query(ActivityLog).filter(ActivityLog.posted_at >= today_start).count()

    # Revenue (potential monthly)
    monthly_recurring = 0
    for plan_name, count in plans_detail.items():
        price = PLANS.get(plan_name, {}).get("price", 0)
        # Only count active users toward MRR
        active_on_plan = db.query(User).filter(User.plan == plan_name, User.status == "active").count()
        monthly_recurring += active_on_plan * price

    # Recent signups (last 7 days)
    week_ago = now - timedelta(days=7)
    signups_7d = db.query(User).filter(User.created_at >= week_ago).count()

    # At-risk: trial expiring in <=2 days
    at_risk_trial = db.query(User).filter(
        User.trial_expires_at.isnot(None),
        User.trial_expires_at > now,
        User.trial_expires_at <= now + timedelta(days=2)
    ).count()

    # Paused users (churning)
    paused_users_count = paused_users

    # Schedules running
    total_schedules = db.query(Schedule).count()
    active_schedules = db.query(Schedule).filter(Schedule.enabled == True).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "paused_users": paused_users_count,
        "verified": verified,
        "unverified": unverified,
        "trial_active": trial_active,
        "trial_expired": trial_expired,
        "at_risk_trial": at_risk_trial,
        "plans": plans_detail,
        "total_accounts": total_accounts,
        "active_accounts": active_accounts,
        "paused_accounts": paused_accounts,
        "posts_today": posts_today,
        "activity_today": activity_today,
        "monthly_recurring": monthly_recurring,
        "signups_7d": signups_7d,
        "total_schedules": total_schedules,
        "active_schedules": active_schedules,
    }


@app.get("/api/owner/users")
def owner_users(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    users = db.query(User).order_by(User.created_at.desc()).all()
    result = []
    for u in users:
        accts = db.query(Account).filter(Account.user_id == u.id).all()
        posts = db.query(Post).filter(Post.account_id.in_([a.id for a in accts])).count() if accts else 0
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        posts_today = db.query(Post).filter(
            Post.account_id.in_([a.id for a in accts]),
            Post.posted_at >= today_start
        ).count() if accts else 0

        trial_days_left = None
        if u.trial_expires_at:
            rem = (u.trial_expires_at - now).days
            trial_days_left = max(0, rem)

        result.append({
            "id": u.id,
            "email": u.email,
            "name": u.name or u.email.split("@")[0],
            "plan": u.plan,
            "status": u.status,
            "email_verified": u.email_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "trial_expires_at": u.trial_expires_at.isoformat() if u.trial_expires_at else None,
            "trial_days_left": trial_days_left,
            "accounts": len(accts),
            "active_accounts": sum(1 for a in accts if a.active),
            "total_posts": posts,
            "posts_today": posts_today,
        })
    return result


@app.get("/api/owner/accounts")
def owner_accounts(db: Session = Depends(get_db)):
    accts = db.query(Account).order_by(Account.created_at.desc()).all()
    result = []
    for a in accts:
        schedules = db.query(Schedule).filter(Schedule.account_id == a.id).all()
        active_sched = sum(1 for s in schedules if s.enabled)
        result.append({
            "id": a.id,
            "user_id": a.user_id,
            "username": a.username,
            "display_name": a.display_name,
            "niche": a.niche,
            "active": a.active,
            "today_threads": a.today_threads,
            "today_replies": a.today_replies,
            "today_follows": a.today_follows,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "schedules": len(schedules),
            "active_schedules": active_sched,
        })
    return result


@app.get("/api/owner/activity")
def owner_activity(db: Session = Depends(get_db)):
    """Last 100 activity logs across all accounts."""
    logs = db.query(ActivityLog).order_by(ActivityLog.posted_at.desc()).limit(100).all()
    result = []
    for log in logs:
        acct = db.query(Account).filter(Account.id == log.account_id).first()
        result.append({
            "id": log.id,
            "account_username": acct.username if acct else "deleted",
            "action": log.action,
            "detail": log.detail,
            "thread_code": log.thread_code,
            "posted_at": log.posted_at.isoformat() if log.posted_at else None,
        })
    return result


# ── Page ──

@app.get("/api/owner/growth")
def owner_growth(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    from sqlalchemy import func as sa_func
    days = 14
    data = []
    for i in range(days - 1, -1, -1):
        day = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        next_day = day + timedelta(days=1)
        signups = db.query(User).filter(User.created_at >= day, User.created_at < next_day).count()
        posts = db.query(Post).filter(Post.posted_at >= day, Post.posted_at < next_day).count()
        data.append({
            "date": day.isoformat(),
            "signups": signups,
            "posts": posts,
        })
    return data


@app.get("/api/owner/user/{user_id}")
def owner_user_detail(user_id: int, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return {"error": "User not found"}
    accts = db.query(Account).filter(Account.user_id == u.id).all()
    posts = db.query(Post).filter(Post.account_id.in_([a.id for a in accts])).count() if accts else 0
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    posts_today = db.query(Post).filter(
        Post.account_id.in_([a.id for a in accts]),
        Post.posted_at >= today_start
    ).count() if accts else 0

    trial_days_left = None
    if u.trial_expires_at:
        rem = (u.trial_expires_at - now).days
        trial_days_left = max(0, rem)

    return {
        "id": u.id, "email": u.email, "name": u.name or u.email.split("@")[0],
        "plan": u.plan, "status": u.status, "email_verified": u.email_verified,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "trial_expires_at": u.trial_expires_at.isoformat() if u.trial_expires_at else None,
        "trial_days_left": trial_days_left,
        "accounts": len(accts),
        "active_accounts": sum(1 for a in accts if a.active),
        "total_posts": posts,
        "posts_today": posts_today,
        "account_list": [{"id": a.id, "username": a.username, "niche": a.niche, "active": a.active} for a in accts],
    }


@app.post("/api/owner/user/{user_id}/toggle")
def owner_toggle_user(user_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return {"error": "User not found"}
    u.status = "paused" if u.status == "active" else "active"
    db.commit()
    return {"ok": True, "status": u.status}


@app.post("/api/owner/user/{user_id}/verify")
def owner_resend_verify(user_id: int, db: Session = Depends(get_db)):
    from email_utils import send_verification_email
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return {"error": "User not found"}
    import secrets
    token = secrets.token_urlsafe(32)
    u.email_verification_token = token
    db.commit()
    sent = send_verification_email(u.email, token)
    return {"ok": True, "sent": sent}


@app.post("/api/owner/user/{user_id}/set-plan")
def owner_set_plan(user_id: int, plan: str = "", db: Session = Depends(get_db)):
    valid = {"starter", "growth", "agency"}
    if plan not in valid:
        return {"error": f"Invalid plan. Must be one of: {', '.join(sorted(valid))}"}
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return {"error": "User not found"}
    u.plan = plan
    db.commit()
    return {"ok": True, "plan": plan}


@app.get("/api/owner/user/{user_id}/delete")
def owner_delete_user_confirm(user_id: int, db: Session = Depends(get_db)):
    """Delete a user and all their data."""
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return {"error": "User not found"}
    email = u.email
    db.delete(u)
    db.commit()
    return {"ok": True, "deleted": email}


@app.get("/")
def owner_page():
    html = (BASE_DIR / "templates" / "owner.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9102)
