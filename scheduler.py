"""Background scheduler — polls Schedule table and executes full posting cycle.

For each due schedule slot it:
  1. Reads the live feed for trend context
  2. Posts a thread or fun fact (trend-aware)
  3. Finds high-quality reply targets from the feed
  4. Replies up to the account's remaining reply budget
  5. Logs everything with humanization delays between actions
"""
import asyncio
import json
import random
from datetime import datetime, timezone
from database import Account, Schedule, Post, SessionLocal, get_daily_limit
from setup_logging import get_logger

logger = get_logger(__name__)

LOCK = asyncio.Lock()
_running = False

# ── Per-slot budgets ──
# How many replies each slot should attempt (before checking daily caps)
SLOT_REPLY_BUDGET = 10
SLOT_THREAD_COUNT = 1


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

        logger.info(f"🕐 Scheduler tick: UTC {hour}:00 — {len(schedules)} slots due")

        for sched in schedules:
            account = db.query(Account).filter(Account.id == sched.account_id).first()
            if not account:
                continue

            from main import PLANS
            user = account.user
            plan_cfg = PLANS.get(user.plan, PLANS["starter"])

            # ── Sleep hours check ──
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

            # ── Daily limit check ──
            daily_limit = plan_cfg.get("max_posts_day", get_daily_limit(user.plan))
            today_used = account.today_threads + account.today_replies
            if today_used >= daily_limit:
                sched.last_status = "daily_limit_reached"
                sched.last_run = _now()
                logger.debug(f"Account {account.id} hit daily limit ({today_used}/{daily_limit})")
                continue

            cookies = json.loads(account.cookies_encrypted or "{}")
            if not cookies:
                sched.last_status = "no_cookies"
                sched.last_run = _now()
                continue

            proxy = account.proxy or None

            # ── Authenticate ──
            try:
                from threads_saas import ThreadsAuthWrapper
                auth = ThreadsAuthWrapper.from_cookies(cookies, proxy=proxy)
            except Exception as e:
                logger.error(f"Account {account.id} auth failed: {e}")
                sched.last_status = f"auth_error"
                sched.last_run = _now()
                db.commit()
                continue

            try:
                # ── Step 1: Read live feed for trend context ──
                feed_posts = []
                try:
                    feed_posts = auth.get_feed(count=20)
                    logger.info(f"Account {account.id}: read {len(feed_posts)} feed posts for context")
                except Exception as e:
                    logger.warning(f"Account {account.id}: feed read failed ({e}), continuing without")

                # ── Step 2: Post thread or fun fact ──
                from ai import generate_thread, generate_fun_fact, generate_reply

                post_type = "thread"
                content = None

                if sched.slot_name == "fun_fact":
                    content = generate_fun_fact(account, feed_posts=feed_posts)
                    post_type = "fun_fact"
                else:
                    content, source = generate_thread(account, feed_posts=feed_posts)
                    logger.info(f"Thread generated: {source}")

                if content:
                    try:
                        link = account.link if account.links_enabled else None
                        result = auth.post_thread(content, link=link)
                        thread_code = result.get("thread_code", "")
                        logger.info(f"✅ Posted for {account.username}: {thread_code[:20]}")
                        db.add(Post(
                            account_id=account.id,
                            thread_code=thread_code,
                            post_type=post_type,
                            content_preview=content[:500],
                        ))
                        account.today_threads += 1
                        db.commit()
                    except Exception as e:
                        logger.error(f"Post failed for account {account.id}: {e}")
                        sched.last_status = f"post_error"

                # ── Step 3: Reply cycle ──
                reply_budget = min(
                    SLOT_REPLY_BUDGET,
                    max(0, (account.target_replies or 10) - account.today_replies),
                    max(0, (account.max_replies or 15) - account.today_replies),
                )

                if reply_budget > 0 and plan_cfg.get("feature_replies", True):
                    min_likes = account.viral_threshold or 0
                    reply_keywords_raw = account.reply_keywords or ""
                    reply_targets = []

                    try:
                        # Get feed-based targets
                        reply_targets = auth.find_reply_targets(
                            count=20,
                            min_likes=min_likes,
                        )
                    except Exception as e:
                        logger.warning(f"Account {account.id}: find-targets failed ({e})")

                    # Filter by reply keywords if set
                    if reply_keywords_raw.strip() and reply_targets:
                        from ai import _safe_json_list
                        keywords = _safe_json_list(reply_keywords_raw)
                        if keywords:
                            filtered = []
                            for t in reply_targets:
                                cap = (t.get("caption") or "").lower()
                                if any(k.lower() in cap for k in keywords):
                                    filtered.append(t)
                            if filtered:
                                reply_targets = filtered

                    # Limit to budget
                    reply_targets = reply_targets[:reply_budget]

                    replies_posted = 0
                    for target in reply_targets:
                        # Check we haven't hit daily reply cap midway
                        if account.today_replies >= (account.max_replies or 15):
                            break
                        if account.today_replies >= (account.target_replies or 10):
                            break

                        try:
                            reply_text = generate_reply(account, target, feed_posts=feed_posts)
                            if not reply_text:
                                continue

                            auth.post_reply(target["thread_code"], reply_text)

                            db.add(Post(
                                account_id=account.id,
                                thread_code=target["thread_code"],
                                post_type="reply",
                                content_preview=reply_text[:300],
                            ))
                            account.today_replies += 1
                            replies_posted += 1
                            db.commit()

                            logger.info(
                                f"💬 Replied to @{target['username']} "
                                f"({target['like_count']}❤️) — {reply_text[:40]}"
                            )

                        except Exception as e:
                            logger.error(f"Reply failed to {target.get('username','?')}: {e}")
                            db.rollback()
                            continue

                    if replies_posted:
                        logger.info(f"Account {account.id}: {replies_posted} replies posted this slot")

                # ── Mark schedule as successful ──
                sched.last_status = "success"
                sched.last_run = _now()
                db.commit()

            except Exception as e:
                logger.error(f"Schedule {sched.id} (account {account.id}) failed: {e}")
                sched.last_status = f"error: {str(e)[:50]}"
                sched.last_run = _now()
                db.commit()
            finally:
                try:
                    auth.close()
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Scheduler loop error: {e}")
        db.rollback()
    finally:
        db.close()
        _running = False


async def scheduler_loop():
    """Run every 60 seconds. Started as a FastAPI lifespan task."""
    logger.info("🚀 Scheduler started (checking every 60s)")
    while True:
        await asyncio.sleep(60)
        await run_scheduler()


async def run_account_now(account_id: int):
    """Manually trigger a single slot run for an account — regardless of hour."""
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            db.close()
            return {"error": "Account not found"}

        # Temporarily set a schedule to the current hour (in-memory only)
        current_hour = _utc_hour()
        schedules = (
            db.query(Schedule)
            .filter(Schedule.account_id == account_id, Schedule.enabled == True)
            .all()
        )

        if not schedules:
            db.close()
            return {"error": "No enabled schedules for this account"}

        # Pick the first enabled schedule, fake its hour_utc in memory
        sched = schedules[0]
        original_hour = sched.hour_utc
        sched.hour_utc = current_hour

        results = [{"slot": sched.slot_name, "triggered": True}]
        db.flush()
        db.close()

        await run_scheduler()

        # Restore original hour after run
        db2 = SessionLocal()
        try:
            restored = db2.query(Schedule).filter(Schedule.id == sched.id).first()
            if restored:
                restored.hour_utc = original_hour
                db2.commit()
        finally:
            db2.close()

        return {"ok": True, "slots_triggered": 1, "results": results}
    except Exception as e:
        db.close()
        logger.error(f"Manual run failed for account {account_id}: {e}")
        return {"error": str(e)}
