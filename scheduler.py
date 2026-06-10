"""Background scheduler — polls Schedule table and posts content on time.

Runs inside the FastAPI process as a lifespan background task.
For each due schedule slot it:
  1. Checks account is active, not in sleep hours, under daily limits
  2. Generates content via ai.py
  3. Posts via threads.py
  4. Logs result to Post table
  5. Updates Schedule.last_run / last_status
"""
import asyncio
import json
from datetime import datetime, timezone
from database import Account, Schedule, Post, SessionLocal, get_daily_limit
from setup_logging import get_logger

logger = get_logger(__name__)

LOCK = asyncio.Lock()
_running = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_hour() -> int:
    return _now().hour


async def run_scheduler():
    global _running
    if _running:
        logger.debug("Scheduler already running, skipping")
        return
    _running = True

    db = SessionLocal()
    try:
        hour = _utc_hour()

        schedules = (
            db.query(Schedule)
            .join(Account, Schedule.account_id == Account.id)
            .filter(
                Schedule.enabled == True,
                Schedule.hour_utc == hour,
                Account.active == True,
            )
            .all()
        )

        if not schedules:
            return

        logger.info(f"Scheduler tick: UTC {hour}:00 — {len(schedules)} slots due")

        for sched in schedules:
            account = db.query(Account).filter(Account.id == sched.account_id).first()
            if not account:
                continue

            # Re-fetch user plan limit
            from main import PLANS
            user = account.user
            plan_cfg = PLANS.get(user.plan, PLANS["starter"])

            if not account.active:
                sched.last_status = "account_inactive"
                sched.last_run = _now()
                continue

            # Sleep hours check
            sleep_start = account.sleep_hours_start or 0
            sleep_end = account.sleep_hours_end or 0
            if sleep_start != sleep_end and (
                (sleep_start < sleep_end and sleep_start <= hour <= sleep_end) or
                (sleep_start > sleep_end and (hour >= sleep_start or hour <= sleep_end))
            ):
                sched.last_status = "sleep_hours"
                sched.last_run = _now()
                logger.debug(f"Account {account.id} in sleep hours ({sleep_start}-{sleep_end})")
                continue

            # Daily limits
            daily_limit = plan_cfg.get("max_posts_day", get_daily_limit(user.plan))
            today_used = account.today_threads + account.today_replies
            if today_used >= daily_limit:
                sched.last_status = "daily_limit_reached"
                sched.last_run = _now()
                logger.debug(f"Account {account.id} hit daily limit ({today_used}/{daily_limit})")
                continue

            # ── Execute the post ──
            try:
                from ai import generate_thread, generate_fun_fact
                from threads import ThreadsAuth

                cookies = json.loads(account.cookies_encrypted or "{}")
                if not cookies:
                    sched.last_status = "no_cookies"
                    sched.last_run = _now()
                    continue

                proxy = account.proxy or None

                # Choose post type
                post_type = "thread"
                if sched.slot_name == "fun_fact":
                    content = generate_fun_fact(account)
                    post_type = "fun_fact"
                else:
                    content = generate_thread(account)
                    post_type = "thread"

                if not content:
                    sched.last_status = "ai_empty"
                    sched.last_run = _now()
                    continue

                # Post to Threads
                auth = ThreadsAuth.from_cookies(cookies, proxy=proxy)
                link = account.link if account.links_enabled else None

                result = auth.post_thread(content, link=link)
                auth.close()

                thread_code = result.get("thread_code", "")
                logger.info(f"Posted for account {account.id} ({account.username}): {thread_code[:20]}")

                # Log the post
                db.add(Post(
                    account_id=account.id,
                    thread_code=thread_code,
                    post_type=post_type,
                    content_preview=content[:500],
                ))

                # Update stats
                account.today_threads += 1
                sched.last_status = "success"
                sched.last_run = _now()

                db.commit()

            except Exception as e:
                logger.error(f"Schedule {sched.id} (account {account.id}) failed: {e}")
                sched.last_status = f"error: {str(e)[:50]}"
                sched.last_run = _now()
                db.commit()

    except Exception as e:
        logger.error(f"Scheduler loop error: {e}")
        db.rollback()
    finally:
        db.close()
        _running = False


async def scheduler_loop():
    """Run every 60 seconds. Started as a FastAPI lifespan task."""
    logger.info("Scheduler started (checking every 60s)")
    while True:
        await asyncio.sleep(60)
        await run_scheduler()


async def run_account_now(account_id: int):
    """Manually trigger all enabled schedules for an account — regardless of hour."""
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return {"error": "Account not found"}

        schedules = (
            db.query(Schedule)
            .filter(Schedule.account_id == account_id, Schedule.enabled == True)
            .all()
        )

        results = []
        for sched in schedules[:3]:  # max 3 at once
            sched.hour_utc = _utc_hour()
            db.commit()
            results.append({"slot": sched.slot_name, "triggered": True})

        db.close()
        await run_scheduler()
        return {"ok": True, "slots_triggered": len(results), "results": results}
    except Exception as e:
        db.close()
        logger.error(f"Manual run failed for account {account_id}: {e}")
        return {"error": str(e)}
