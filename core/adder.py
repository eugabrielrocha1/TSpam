"""
CyberTG – Bulk Member Adder
Adds scraped users to a target group with anti-ban measures.
"""
import asyncio
import random
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.types import InputPeerUser
from telethon.errors import (
    FloodWaitError,
    UserPrivacyRestrictedError,
    PeerFloodError,
    UserNotMutualContactError,
    ChatWriteForbiddenError,
    UserChannelsTooMuchError,
    UserKickedError,
    UserBannedInChannelError,
    InputUserDeactivatedError,
    UserAlreadyParticipantError,
)
from core.db import update_user_added_status
from core.logger import logger
from core.scraper import resolve_group


async def add_members(clients: list, target_group_link: str,
                      users: list, delay_min: int = 8, delay_max: int = 25,
                      progress_callback=None,
                      pause_event: asyncio.Event = None,
                      stop_event: asyncio.Event = None):
    """
    Add users to a target group using round-robin across multiple clients.

    Args:
        clients: List of connected TelegramClient instances
        target_group_link: Link or username of the target group
        users: List of user dicts from scraper/DB
        delay_min/max: Random delay range between adds
        progress_callback: fn(added, skipped, failed, total)
        pause_event: Set = paused, unset = running
        stop_event: Set = stop everything
    """
    if not clients:
        logger.error("No connected accounts available for adding")
        return

    # Resolve target group with first client
    target = await resolve_group(clients[0], target_group_link)
    if not target:
        logger.error("Could not resolve target group")
        return

    target_title = getattr(target, "title", target_group_link)
    logger.info(f"Starting adder → '{target_title}' with {len(clients)} account(s), {len(users)} users")

    added = 0
    skipped = 0
    failed = 0
    total = len(users)
    client_idx = 0
    flood_counts = {i: 0 for i in range(len(clients))}
    disabled_clients = set()

    for i, user in enumerate(users):
        # Check stop
        if stop_event and stop_event.is_set():
            logger.warning("Adder stopped by user")
            break

        # Check pause
        if pause_event and pause_event.is_set():
            logger.info("Adder paused — waiting for resume...")
            while pause_event.is_set():
                if stop_event and stop_event.is_set():
                    break
                await asyncio.sleep(0.5)
            if stop_event and stop_event.is_set():
                break
            logger.info("Adder resumed")

        # Skip if all clients are disabled
        if len(disabled_clients) >= len(clients):
            logger.error("All accounts hit PeerFlood — stopping adder")
            break

        # Round-robin to next available client
        attempts = 0
        while client_idx in disabled_clients and attempts < len(clients):
            client_idx = (client_idx + 1) % len(clients)
            attempts += 1

        client = clients[client_idx]
        user_id = user.get("user_id", 0)
        username = user.get("username", "")
        display = username or str(user_id)

        try:
            # Resolve target on this client too
            target_entity = await resolve_group(client, target_group_link)
            if not target_entity:
                logger.error(f"Client {client_idx} cannot resolve target")
                disabled_clients.add(client_idx)
                client_idx = (client_idx + 1) % len(clients)
                failed += 1
                continue

            # Get the user entity
            try:
                user_entity = await client.get_input_entity(user_id)
            except Exception:
                if username:
                    try:
                        user_entity = await client.get_input_entity(username)
                    except Exception:
                        logger.warning(f"Cannot resolve user {display} — skipping")
                        skipped += 1
                        update_user_added_status(user_id, "skipped")
                        if progress_callback:
                            progress_callback(added, skipped, failed, total)
                        continue
                else:
                    logger.warning(f"Cannot resolve user {display} — skipping")
                    skipped += 1
                    update_user_added_status(user_id, "skipped")
                    if progress_callback:
                        progress_callback(added, skipped, failed, total)
                    continue

            await client(InviteToChannelRequest(target_entity, [user_entity]))
            added += 1
            update_user_added_status(user_id, "added")
            logger.success(f"[{added}/{total}] Added {display} (via account #{client_idx})")

        except UserAlreadyParticipantError:
            skipped += 1
            update_user_added_status(user_id, "already_member")
            logger.info(f"User {display} already in group — skipped")

        except UserPrivacyRestrictedError:
            skipped += 1
            update_user_added_status(user_id, "privacy")
            logger.warning(f"Privacy restricted: {display}")

        except UserNotMutualContactError:
            skipped += 1
            update_user_added_status(user_id, "not_mutual")
            logger.warning(f"Not mutual contact: {display}")

        except UserChannelsTooMuchError:
            skipped += 1
            update_user_added_status(user_id, "too_many_channels")
            logger.warning(f"User in too many channels: {display}")

        except UserKickedError:
            skipped += 1
            update_user_added_status(user_id, "kicked")
            logger.warning(f"User was kicked from group: {display}")

        except UserBannedInChannelError:
            skipped += 1
            update_user_added_status(user_id, "banned_channel")
            logger.warning(f"User banned in channel: {display}")

        except InputUserDeactivatedError:
            skipped += 1
            update_user_added_status(user_id, "deactivated")
            logger.warning(f"User deactivated: {display}")

        except ChatWriteForbiddenError:
            logger.error("Cannot write to target group — check permissions")
            failed += 1
            break

        except FloodWaitError as e:
            logger.error(f"FloodWait {e.seconds}s on account #{client_idx}")
            flood_counts[client_idx] = flood_counts.get(client_idx, 0) + 1

            if flood_counts[client_idx] >= 3:
                logger.error(f"Account #{client_idx} disabled (3 floods)")
                disabled_clients.add(client_idx)
            else:
                wait_time = min(e.seconds + 5, 300)
                logger.warning(f"Sleeping {wait_time}s for FloodWait...")
                await asyncio.sleep(wait_time)

            failed += 1
            update_user_added_status(user_id, "flood_error")

        except PeerFloodError:
            logger.error(f"PeerFlood on account #{client_idx} — disabling")
            disabled_clients.add(client_idx)
            failed += 1
            update_user_added_status(user_id, "peer_flood")

        except Exception as e:
            failed += 1
            update_user_added_status(user_id, "error")
            logger.error(f"Error adding {display}: {e}")

        # Progress callback
        if progress_callback:
            progress_callback(added, skipped, failed, total)

        # Rotate client
        client_idx = (client_idx + 1) % len(clients)

        # Random delay
        delay = random.uniform(delay_min, delay_max)
        logger.info(f"Waiting {delay:.1f}s before next add...")
        await asyncio.sleep(delay)

    logger.success(f"Adder finished — Added: {added}, Skipped: {skipped}, Failed: {failed}")
    return {"added": added, "skipped": skipped, "failed": failed, "total": total}
