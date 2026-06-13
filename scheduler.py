"""Background scheduler — polls Schedule table and executes full posting cycle.

For each due schedule slot it:
  1. Reads the live feed for trend context
  2. Posts a thread or fun fact (trend-aware)
  3. Finds high-quality reply targets from the feed
  4. Replies up to the account's remaining reply budget
  5. Logs everything (console + activity_logs table)
"""
import asyncio
import json
import random
from datetime import datetime, timezone, timedelta
from database import Account, Schedule, Post, ActivityLog, SessionLocal, get_daily_limit
from setup_logging import get_logger
from logs.activity_logger import ActivityLogger

logger = get_logger(__name__)

LOCK = asyncio.Lock()
_running = False

# ── Per-slot budgets ──
SLOT_REPLY_BUDGET = 10
SLOT_THREAD_COUNT = 1

# ── Auth cache: avoid re-authing same account multiple times per tick ──
_auth_cache: dict = {}


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
        # ── Daily counter reset ──
        today_str = _now().strftime("%Y-%m-%d")
        db.query(Account).filter(
            Account.last_reset_date != today_str
        ).update({
            Account.today_threads: 0,
            Account.today_replies: 0,
            Account.today_follows: 0,
            Account.today_dms: 0,
            Account.last_reset_date: today_str,
        }, synchronize_session=False)
        db.commit()
        logger.debug(f"Daily reset checked — today: {today_str}")

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

            act = ActivityLogger(account_id=account.id, username=account.username)

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
                act.info("schedule_skip", f"Sleep hours ({sleep_start}-{sleep_end} UTC) — skipped")
                logger.debug(f"Account {account.id} in sleep hours ({sleep_start}-{sleep_end})")
                continue

            # ── Daily limit check ──
            daily_limit = get_daily_limit(user.plan)  # 60/account regardless of plan
            today_used = account.today_threads + account.today_replies
            if today_used >= daily_limit:
                sched.last_status = "daily_limit_reached"
                sched.last_run = _now()
                act.info("schedule_skip", f"Daily limit hit ({today_used}/{daily_limit})")
                logger.debug(f"Account {account.id} hit daily limit ({today_used}/{daily_limit})")
                continue

            cookies = json.loads(account.cookies_encrypted or "{}")
            if not cookies:
                sched.last_status = "no_cookies"
                sched.last_run = _now()
                act.error("auth_fail", "No cookies saved for this account")
                continue

            proxy = account.proxy or None

            # ── Authenticate (cached per account per tick) ──
            try:
                from threads_saas import ThreadsAuthWrapper
                if sched.account_id not in _auth_cache:
                    auth = ThreadsAuthWrapper.from_cookies(cookies, proxy=proxy)
                    _auth_cache[sched.account_id] = auth

                    # ── One-time browser fingerprint enrichment ──
                    if not auth.auth.session_params or "__dyn" not in auth.auth.session_params:
                        logger.info(f"Account {account.id}: enriching browser fingerprint (one-time)...")
                        try:
                            if auth.auth.refresh_from_browser(headless=True, timeout_ms=45000):
                                enriched = json.loads(account.cookies_encrypted or "[]")
                                enriched = [c for c in enriched if isinstance(c, dict) and not c.get("name", "").startswith("__")]
                                enriched.append({"name": "__session_params", "value": json.dumps(auth.auth.session_params)})
                                enriched.append({"name": "__fb_dtsg", "value": auth.auth.fb_dtsg or ""})
                                enriched.append({"name": "__lsd", "value": auth.auth.lsd or ""})
                                account.cookies_encrypted = json.dumps(enriched)
                                db.commit()
                                logger.info(f"Account {account.id}: fingerprint enriched and saved ✅")
                            else:
                                logger.warning(f"Account {account.id}: browser refresh returned False")
                        except Exception as e:
                            logger.warning(f"Account {account.id}: browser refresh failed ({type(e).__name__}), continuing with HTML fingerprint")
                else:
                    auth = _auth_cache[sched.account_id]
            except Exception as e:
                logger.error(f"Account {account.id} auth failed: {e}")
                act.error("auth_fail", f"Auth failed: {str(e)[:100]}")
                sched.last_status = "auth_error"
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
                        act.success(post_type, f"Posted {post_type} ({content[:50]}...)", thread_code=thread_code)
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
                        act.error("post_error", f"Post failed: {str(e)[:100]}")
                        sched.last_status = "post_error"

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

                    reply_targets = reply_targets[:reply_budget]

                    replies_posted = 0
                    for target in reply_targets:
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

                            act.success("reply", f"Replied to @{target['username']} ({target.get('like_count',0)}❤️)", thread_code=target["thread_code"])
                            logger.info(
                                f"💬 Replied to @{target['username']} "
                                f"({target['like_count']}❤️) — {reply_text[:40]}"
                            )

                        except Exception as e:
                            logger.error(f"Reply failed to {target.get('username','?')}: {e}")
                            act.error("reply_error", f"Reply failed to @{target.get('username','?')}: {str(e)[:80]}")
                            db.rollback()
                            continue

                    if replies_posted:
                        act.info("reply", f"Posted {replies_posted} replies this slot")

                # ── Mark schedule as successful ──
                sched.last_status = "success"
                sched.last_run = _now()
                db.commit()

            except Exception as e:
                logger.error(f"Schedule {sched.id} (account {account.id}) failed: {e}")
                act.error("error", f"Schedule failed: {str(e)[:100]}")
                sched.last_status = f"error: {str(e)[:50]}"
                sched.last_run = _now()
                db.commit()
            # auth closed in outer finally after all accounts processed

    except Exception as e:
        logger.error(f"Scheduler loop error: {e}")
        db.rollback()
    finally:
        # Close cached auth wrappers
        for aid, a in list(_auth_cache.items()):
            try:
                a.close()
            except Exception:
                pass
        _auth_cache.clear()
        db.close()
        _running = False


async def scheduler_loop():
    """Run every 60 seconds. Started as a FastAPI lifespan task."""
    logger.info("Scheduler started (checking every 60s)")
    # Cleanup old logs on startup
    _cleanup_old_logs()
    while True:
        await asyncio.sleep(60)
        await run_scheduler()
        # Purge logs older than 3 days every hour
        if datetime.now(timezone.utc).minute == 0:
            _cleanup_old_logs()


def _cleanup_old_logs():
    """Delete activity logs older than 3 days."""
    try:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=3)
            deleted = db.query(ActivityLog).filter(ActivityLog.posted_at < cutoff).delete()
            db.commit()
            if deleted:
                logger.info(f"🧹 Purged {deleted} old activity logs (older than 3 days)")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Log cleanup failed: {e}")


async def run_account_now(account_id: int):
    """Manually trigger posting for an account — runs directly instead of hacking the hour."""
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            db.close()
            return {"error": "Account not found"}

        # Build a single schedule that always matches current hour
        current_hour = _utc_hour()
        schedules = (
            db.query(Schedule)
            .filter(Schedule.account_id == account_id, Schedule.enabled == True)
            .all()
        )

        if not schedules:
            db.close()
            return {"error": "No enabled schedules for this account"}

        # Pick the best schedule (closest to current hour, or first)
        sched = min(schedules, key=lambda s: abs(s.hour_utc - current_hour))
        results = [{"slot": sched.slot_name, "triggered": True}]
        db.close()

        # Run the posting logic directly (same as a normal slot)
        err = await _run_slot(account_id, sched.slot_name, sched.post_type)
        if err:
            return {"ok": True, "slots_triggered": 1, "results": results, "warning": err}

        return {"ok": True, "slots_triggered": 1, "results": results}
    except Exception as e:
        db.close()
        logger.error(f"Manual run failed for account {account_id}: {e}")
        return {"error": str(e)}


async def _run_slot(account_id: int, slot_name: str, post_type: str = "thread") -> str | None:
    """Execute a single slot for a given account. Used by the scheduler and manual trigger."""
    db = SessionLocal()
    try:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            return "Account not found"

        act = ActivityLogger(account_id=account.id, username=account.username)
        from main import PLANS
        user = account.user
        plan_cfg = PLANS.get(user.plan, PLANS["starter"])
        hour = _utc_hour()

        # Sleep hours check
        sleep_start = account.sleep_hours_start or 0
        sleep_end = account.sleep_hours_end or 0
        if sleep_start != sleep_end and (
            (sleep_start < sleep_end and sleep_start <= hour <= sleep_end) or
            (sleep_start > sleep_end and (hour >= sleep_start or hour <= sleep_end))
        ):
            act.info("schedule_skip", f"Run-now skipped: sleep hours ({sleep_start}-{sleep_end} UTC)")
            return None  # Not an error, just skipped

        # Daily limit check
        daily_limit = get_daily_limit(user.plan)
        today_used = account.today_threads + account.today_replies
        if today_used >= daily_limit:
            act.info("schedule_skip", f"Run-now skipped: daily limit ({today_used}/{daily_limit})")
            return None

        cookies = json.loads(account.cookies_encrypted or "{}")
        if not cookies:
            act.error("auth_fail", "No cookies saved")
            return "No cookies"

        proxy = account.proxy or None
        from threads_saas import ThreadsAuthWrapper
        auth = ThreadsAuthWrapper.from_cookies(cookies, proxy=proxy)

        # Feed context
        feed_posts = []
        try:
            feed_posts = auth.get_feed(count=20)
        except Exception as e:
            logger.warning(f"Account {account.id}: feed read failed ({e})")

        # Post
        from ai import generate_thread, generate_fun_fact, generate_reply
        content = None
        effective_type = post_type

        if slot_name == "fun_fact":
            content = generate_fun_fact(account, feed_posts=feed_posts)
            effective_type = "fun_fact"
        else:
            content, source = generate_thread(account, feed_posts=feed_posts)

        if content:
            try:
                link = account.link if account.links_enabled else None
                result = auth.post_thread(content, link=link)
                thread_code = result.get("thread_code", "")
                act.success(effective_type, f"Posted {effective_type} ({content[:50]}...)", thread_code=thread_code)
                db.add(Post(
                    account_id=account.id,
                    thread_code=thread_code,
                    post_type=effective_type,
                    content_preview=content[:500],
                ))
                account.today_threads += 1
                db.commit()
            except Exception as e:
                logger.error(f"Post failed for account {account.id}: {e}")
                act.error("post_error", f"Post failed: {str(e)[:100]}")

        # Reply cycle
        reply_budget = min(
            10,  # SLOT_REPLY_BUDGET
            max(0, (account.target_replies or 10) - account.today_replies),
            max(0, (account.max_replies or 15) - account.today_replies),
        )

        if reply_budget > 0 and plan_cfg.get("feature_replies", True):
            min_likes = account.viral_threshold or 0
            reply_keywords_raw = account.reply_keywords or ""
            reply_targets = []

            try:
                reply_targets = auth.find_reply_targets(count=20, min_likes=min_likes)
            except Exception as e:
                logger.warning(f"Account {account.id}: find-targets failed ({e})")

            if reply_keywords_raw.strip() and reply_targets:
                from ai import _safe_json_list
                keywords = _safe_json_list(reply_keywords_raw)
                if keywords:
                    filtered = [t for t in reply_targets
                                if any(k.lower() in (t.get("caption") or "").lower() for k in keywords)]
                    if filtered:
                        reply_targets = filtered

            reply_targets = reply_targets[:reply_budget]
            replies_posted = 0
            for target in reply_targets:
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
                    act.success("reply", f"Replied to @{target['username']} ({target.get('like_count',0)}❤️)", thread_code=target["thread_code"])
                except Exception as e:
                    logger.error(f"Reply failed to {target.get('username','?')}: {e}")
                    act.error("reply_error", f"Reply failed: {str(e)[:80]}")
                    db.rollback()
                    continue

            if replies_posted:
                act.info("reply", f"Posted {replies_posted} replies")

        auth.close()
        return None
    except Exception as e:
        logger.error(f"Slot execution failed for account {account_id}: {e}")
        return str(e)
    finally:
        db.close()
