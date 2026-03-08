"""
CyberTG – Group Member Scraper
Scrapes members from Telegram groups/channels with filtering.
Uses the SessionManager's shared event loop — NO new clients created.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import (
    UserStatusRecently,
    UserStatusOnline,
    UserStatusOffline,
    UserStatusLastWeek,
    UserStatusLastMonth,
)
from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    InviteHashExpiredError,
)
from core.db import insert_scraped_users_batch
from core.logger import logger


async def resolve_group(client, group_link: str):
    """Resolve a group link to an entity. Supports public links and invite hashes."""
    link = group_link.strip()

    # Private invite link: t.me/+HASH or t.me/joinchat/HASH
    if "/+" in link or "/joinchat/" in link:
        invite_hash = link.split("+")[-1] if "+" in link else link.split("/joinchat/")[-1]
        invite_hash = invite_hash.strip("/")
        try:
            updates = await client(ImportChatInviteRequest(invite_hash))
            return updates.chats[0]
        except InviteHashExpiredError:
            logger.error("Invite link expired or invalid")
            return None
        except Exception as e:
            logger.error(f"Could not join via invite: {e}")
            return None

    # Public link or username
    try:
        if "t.me/" in link:
            username = link.split("t.me/")[-1].strip("/").split("?")[0]
        else:
            username = link.strip("@")
        entity = await client.get_entity(username)
        return entity
    except Exception as e:
        logger.error(f"Could not resolve group: {e}")
        return None


def _check_last_seen(user, max_days: int) -> bool:
    """Check if user was seen within max_days."""
    status = user.status
    if isinstance(status, (UserStatusOnline, UserStatusRecently)):
        return True
    if isinstance(status, UserStatusOffline):
        if status.was_online:
            cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
            return status.was_online.replace(tzinfo=timezone.utc) >= cutoff
    if isinstance(status, UserStatusLastWeek) and max_days >= 7:
        return True
    if isinstance(status, UserStatusLastMonth) and max_days >= 30:
        return True
    return False


def _last_seen_str(user) -> str:
    status = user.status
    if isinstance(status, UserStatusOnline):
        return "online"
    if isinstance(status, UserStatusRecently):
        return "recently"
    if isinstance(status, UserStatusOffline) and status.was_online:
        return status.was_online.strftime("%Y-%m-%d %H:%M")
    if isinstance(status, UserStatusLastWeek):
        return "last_week"
    if isinstance(status, UserStatusLastMonth):
        return "last_month"
    return "unknown"


def _flush_batch(batch: list):
    """Flush a batch of user tuples to the database."""
    if batch:
        try:
            insert_scraped_users_batch(batch)
        except Exception as e:
            logger.warning(f"Batch insert warning: {e}")
        batch.clear()


async def scrape_group(client, group_link: str,
                       filter_has_username: bool = True,
                       filter_not_bot: bool = True,
                       filter_last_seen_days: int = 30,
                       filter_has_photo: bool = False,
                       progress_callback=None,
                       stop_event=None):
    """
    Scrape members from a group/channel using an EXISTING connected client.
    This coroutine runs on the SessionManager's shared event loop.
    """
    all_users = []
    batch_buffer = []
    BATCH_SIZE = 50

    entity = await resolve_group(client, group_link)
    if not entity:
        return []

    source_name = getattr(entity, "title", str(group_link))
    logger.info(f"Scraping '{source_name}'...")

    total_fetched = 0

    try:
        async for user in client.iter_participants(entity, aggressive=True):
            if stop_event and stop_event.is_set():
                logger.warning("Scrape stopped by user")
                break

            total_fetched += 1

            # Apply filters
            if filter_not_bot and user.bot:
                continue
            if filter_has_username and not user.username:
                continue
            if filter_has_photo and not user.photo:
                continue
            if filter_last_seen_days > 0 and not _check_last_seen(user, filter_last_seen_days):
                continue

            user_data = {
                "user_id":    user.id,
                "username":   user.username or "",
                "first_name": user.first_name or "",
                "last_name":  user.last_name or "",
                "phone":      user.phone or "",
                "has_photo":  bool(user.photo),
                "last_seen":  _last_seen_str(user),
                "source":     source_name,
            }
            all_users.append(user_data)

            batch_buffer.append((
                user.id,
                user.username or "",
                user.first_name or "",
                user.last_name or "",
                user.phone or "",
                1 if user.photo else 0,
                _last_seen_str(user),
                source_name
            ))

            if len(batch_buffer) >= BATCH_SIZE:
                _flush_batch(batch_buffer)

            if progress_callback and total_fetched % 10 == 0:
                progress_callback(total_fetched, len(all_users))

    except FloodWaitError as e:
        logger.error(f"FloodWait {e.seconds}s — try again later")
    except ChatAdminRequiredError:
        logger.error("Admin rights required to scrape this group")
    except ChannelPrivateError:
        logger.error("Channel is private or you were banned")
    except Exception as e:
        logger.error(f"Scrape error: {type(e).__name__}: {e}")
    finally:
        _flush_batch(batch_buffer)

    if progress_callback:
        progress_callback(total_fetched, len(all_users))

    logger.success(f"Scrape complete: {len(all_users)} users matched from {total_fetched} total in '{source_name}'")
    return all_users
