"""
CyberTG – Bulk Member Adder v2
Adds scraped users to a target group with BATCH add + anti-ban measures.
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


# ─── Single-user fallback ──────────────────────────────────────────
async def _add_single(client, target_entity, user_entity, user_id, display,
                      flood_counts, client_idx, disabled_clients):
    """Try adding a single user (fallback when batch fails)."""
    result = {"status": "ok", "skipped": False, "failed": False}
    try:
        await client(InviteToChannelRequest(target_entity, [user_entity]))
        update_user_added_status(user_id, "added")
        logger.success(f"Added (single) {display}")
        return result

    except UserAlreadyParticipantError:
        update_user_added_status(user_id, "already_member")
        result["skipped"] = True
    except UserPrivacyRestrictedError:
        update_user_added_status(user_id, "privacy")
        result["skipped"] = True
    except UserNotMutualContactError:
        update_user_added_status(user_id, "not_mutual")
        result["skipped"] = True
    except UserChannelsTooMuchError:
        update_user_added_status(user_id, "too_many_channels")
        result["skipped"] = True
    except UserKickedError:
        update_user_added_status(user_id, "kicked")
        result["skipped"] = True
    except UserBannedInChannelError:
        update_user_added_status(user_id, "banned_channel")
        result["skipped"] = True
    except InputUserDeactivatedError:
        update_user_added_status(user_id, "deactivated")
        result["skipped"] = True
    except FloodWaitError as e:
        flood_counts[client_idx] = flood_counts.get(client_idx, 0) + 1
        if flood_counts[client_idx] >= 3:
            disabled_clients.add(client_idx)
        update_user_added_status(user_id, "flood_error")
        result["failed"] = True
    except PeerFloodError:
        disabled_clients.add(client_idx)
        update_user_added_status(user_id, "peer_flood")
        result["failed"] = True
    except Exception:
        update_user_added_status(user_id, "error")
        result["failed"] = True

    return result


# ─── Main adder function ──────────────────────────────────────────
async def add_members(clients: list, target_group_link: str,
                      users: list, delay_min: int = 8, delay_max: int = 15,
                      batch_size: int = 80,
                      progress_callback=None,
                      pause_event: asyncio.Event = None,
                      stop_event: asyncio.Event = None):
    """
    Add users to a target group using BATCH InviteToChannelRequest
    with round-robin account rotation and intelligent fallback.

    Args:
        clients: List of connected TelegramClient instances
        target_group_link: Link or username of the target group
        users: List of user dicts from scraper/DB
        delay_min/max: Random delay range between batch adds
        batch_size: Number of users per InviteToChannelRequest (default 80)
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
    logger.info(f"Starting BATCH adder → '{target_title}' with {len(clients)} account(s), "
                f"{len(users)} users, batch_size={batch_size}")

    added = 0
    skipped = 0
    failed = 0
    total = len(users)
    client_idx = 0
    flood_counts = {i: 0 for i in range(len(clients))}
    disabled_clients = set()

    # Pre-resolve target entity per client (cache)
    target_entities = {}

    # ── Batch accumulator ──────────────────────────────────────
    batch_entities = []   # list of (user_entity, user_id, display)

    for i, user in enumerate(users):
        # ── Stop check ─────────────────────────────────────────
        if stop_event and stop_event.is_set():
            logger.warning("Adder stopped by user")
            break

        # ── Pause check ────────────────────────────────────────
        if pause_event and pause_event.is_set():
            logger.info("Adder paused — waiting for resume...")
            while pause_event.is_set():
                if stop_event and stop_event.is_set():
                    break
                await asyncio.sleep(0.5)
            if stop_event and stop_event.is_set():
                break
            logger.info("Adder resumed")

        # ── All clients dead? ──────────────────────────────────
        if len(disabled_clients) >= len(clients):
            logger.error("All accounts hit PeerFlood — stopping adder")
            break

        # ── Round-robin to next available client ───────────────
        attempts = 0
        while client_idx in disabled_clients and attempts < len(clients):
            client_idx = (client_idx + 1) % len(clients)
            attempts += 1

        client = clients[client_idx]
        user_id = user.get("user_id", 0)
        username = user.get("username", "")
        display = username or str(user_id)

        # ── Resolve user entity ────────────────────────────────
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

        batch_entities.append((user_entity, user_id, display))

        # ── Flush batch when full or at last user ──────────────
        is_last = (i == len(users) - 1)
        if len(batch_entities) >= batch_size or is_last:
            # Ensure we have target resolved for this client
            if client_idx not in target_entities:
                te = await resolve_group(client, target_group_link)
                if not te:
                    logger.error(f"Client #{client_idx} cannot resolve target — disabling")
                    disabled_clients.add(client_idx)
                    for _, uid, _ in batch_entities:
                        update_user_added_status(uid, "error")
                        failed += 1
                    batch_entities.clear()
                    client_idx = (client_idx + 1) % len(clients)
                    if progress_callback:
                        progress_callback(added, skipped, failed, total)
                    continue
                target_entities[client_idx] = te

            target_entity = target_entities[client_idx]
            entities_only = [e for e, _, _ in batch_entities]

            try:
                # ── BATCH ADD — one API call for up to 80 users ──
                await client(InviteToChannelRequest(target_entity, entities_only))
                batch_added = len(entities_only)
                added += batch_added
                for _, uid, dsp in batch_entities:
                    update_user_added_status(uid, "added")
                logger.success(f"✅ Batch added {batch_added} users "
                               f"(total {added}/{total}, via account #{client_idx})")
                batch_entities.clear()

            except FloodWaitError as e:
                logger.error(f"FloodWait {e.seconds}s on batch (account #{client_idx})")
                flood_counts[client_idx] = flood_counts.get(client_idx, 0) + 1

                if flood_counts[client_idx] >= 3:
                    logger.error(f"Account #{client_idx} disabled (3 floods)")
                    disabled_clients.add(client_idx)
                else:
                    wait_time = min(e.seconds + 5, 300)
                    logger.warning(f"Sleeping {wait_time}s for FloodWait...")
                    await asyncio.sleep(wait_time)

                # Fallback to single-user mode for this batch
                logger.warning(f"Falling back to single-add for {len(batch_entities)} users")
                for ue, uid, dsp in batch_entities:
                    res = await _add_single(client, target_entity, ue, uid, dsp,
                                            flood_counts, client_idx, disabled_clients)
                    if res["skipped"]:
                        skipped += 1
                    elif res["failed"]:
                        failed += 1
                    else:
                        added += 1
                    if progress_callback:
                        progress_callback(added, skipped, failed, total)
                    await asyncio.sleep(random.uniform(2, 5))
                batch_entities.clear()

            except PeerFloodError:
                logger.error(f"PeerFlood on batch (account #{client_idx}) — disabling")
                disabled_clients.add(client_idx)

                # Fallback single
                logger.warning(f"Falling back to single-add for {len(batch_entities)} users")
                next_idx = (client_idx + 1) % len(clients)
                if next_idx not in disabled_clients and next_idx < len(clients):
                    fallback_client = clients[next_idx]
                    if next_idx not in target_entities:
                        te = await resolve_group(fallback_client, target_group_link)
                        if te:
                            target_entities[next_idx] = te
                    if next_idx in target_entities:
                        for ue, uid, dsp in batch_entities:
                            res = await _add_single(fallback_client, target_entities[next_idx],
                                                    ue, uid, dsp, flood_counts, next_idx,
                                                    disabled_clients)
                            if res["skipped"]:
                                skipped += 1
                            elif res["failed"]:
                                failed += 1
                            else:
                                added += 1
                            if progress_callback:
                                progress_callback(added, skipped, failed, total)
                            await asyncio.sleep(random.uniform(2, 5))
                batch_entities.clear()

            except ChatWriteForbiddenError:
                logger.error("Cannot write to target group — check permissions")
                for _, uid, _ in batch_entities:
                    update_user_added_status(uid, "error")
                    failed += 1
                batch_entities.clear()
                break

            except Exception as e:
                logger.error(f"Batch add error: {e}")
                # Fallback single
                logger.warning(f"Falling back to single-add for {len(batch_entities)} users")
                for ue, uid, dsp in batch_entities:
                    res = await _add_single(client, target_entity, ue, uid, dsp,
                                            flood_counts, client_idx, disabled_clients)
                    if res["skipped"]:
                        skipped += 1
                    elif res["failed"]:
                        failed += 1
                    else:
                        added += 1
                    if progress_callback:
                        progress_callback(added, skipped, failed, total)
                    await asyncio.sleep(random.uniform(1, 3))
                batch_entities.clear()

            # Progress + rotate + delay after batch flush
            if progress_callback:
                progress_callback(added, skipped, failed, total)

            client_idx = (client_idx + 1) % len(clients)

            delay = random.uniform(delay_min, delay_max)
            logger.info(f"Waiting {delay:.1f}s before next batch...")
            await asyncio.sleep(delay)

    logger.success(f"Adder finished — Added: {added}, Skipped: {skipped}, Failed: {failed}")
    return {"added": added, "skipped": skipped, "failed": failed, "total": total}
