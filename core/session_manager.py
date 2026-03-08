"""
CyberTG – Telethon Session Manager
Handles multi-account connections with proxy support.
All Telethon operations run on a SINGLE shared asyncio event loop thread
to avoid session file lock conflicts.
"""
import asyncio
import os
import threading
import socks
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    AuthKeyUnregisteredError,
    FloodWaitError,
)
from core.db import update_account_status, get_all_accounts
from core.logger import logger

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")


def _ensure_sessions_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def _build_proxy(acc: dict):
    """Build proxy dict for Telethon from account record."""
    ptype = (acc.get("proxy_type") or "").strip().upper()
    paddr = (acc.get("proxy_addr") or "").strip()
    pport = acc.get("proxy_port") or 0

    if not ptype or not paddr or not pport:
        return None

    proxy_map = {
        "SOCKS5": socks.SOCKS5,
        "SOCKS4": socks.SOCKS4,
        "HTTP":   socks.HTTP,
    }
    stype = proxy_map.get(ptype)
    if stype is None:
        return None

    puser = (acc.get("proxy_user") or "").strip() or None
    ppass = (acc.get("proxy_pass") or "").strip() or None
    return (stype, paddr, int(pport), True, puser, ppass)


class SessionManager:
    """Manages multiple Telethon client sessions on a single shared event loop."""

    def __init__(self):
        self.clients: dict[str, TelegramClient] = {}
        _ensure_sessions_dir()

        # Create a dedicated background event loop for ALL Telethon operations
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

    def _run_loop(self):
        """Background thread running the shared asyncio event loop forever."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run_coro(self, coro, timeout=300):
        """Run an async coroutine on the shared loop (blocking from caller thread).
        This is the ONLY way to interact with Telethon clients."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def run_coro_no_wait(self, coro):
        """Schedule a coroutine on the shared loop without waiting."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _session_path(self, phone: str) -> str:
        return os.path.join(SESSIONS_DIR, phone)

    async def _connect_client(self, acc: dict) -> TelegramClient:
        phone = acc["phone"]
        api_id = int(acc["api_id"])
        api_hash = acc["api_hash"]
        proxy = _build_proxy(acc)

        session_path = self._session_path(phone)
        client = TelegramClient(session_path, api_id, api_hash, proxy=proxy)
        await client.connect()
        return client

    async def login_send_code(self, acc: dict) -> tuple:
        """Connect and send the login code. Returns (client, phone_code_hash)."""
        client = await self._connect_client(acc)
        phone = acc["phone"]

        if await client.is_user_authorized():
            self.clients[phone] = client
            update_account_status(phone, "connected")
            logger.success(f"Account {phone} already authorized")
            return client, None

        try:
            result = await client.send_code_request(phone)
            logger.info(f"Code sent to {phone}")
            return client, result.phone_code_hash
        except PhoneNumberBannedError:
            logger.error(f"Phone {phone} is BANNED")
            update_account_status(phone, "banned")
            await client.disconnect()
            raise
        except FloodWaitError as e:
            logger.error(f"FloodWait {e.seconds}s for {phone}")
            update_account_status(phone, "flood")
            await client.disconnect()
            raise
        except Exception as e:
            logger.error(f"Error sending code to {phone}: {e}")
            await client.disconnect()
            raise

    async def login_enter_code(self, client: TelegramClient, phone: str,
                                code: str, phone_code_hash: str,
                                password: str = None):
        """Complete login with the received code (and 2FA if needed)."""
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise
            await client.sign_in(password=password)
        except PhoneCodeInvalidError:
            logger.error(f"Invalid code for {phone}")
            raise

        self.clients[phone] = client
        update_account_status(phone, "connected")
        logger.success(f"Account {phone} logged in successfully")

    async def reconnect_account(self, acc: dict):
        """Reconnect an already-authorized account."""
        phone = acc["phone"]
        try:
            client = await self._connect_client(acc)
            if await client.is_user_authorized():
                self.clients[phone] = client
                update_account_status(phone, "connected")
                logger.success(f"Reconnected {phone}")
            else:
                update_account_status(phone, "need_login")
                logger.warning(f"Session expired for {phone}, need re-login")
                await client.disconnect()
        except Exception as e:
            update_account_status(phone, "error")
            logger.error(f"Reconnect failed for {phone}: {e}")

    async def reconnect_all(self):
        """Reconnect all saved accounts."""
        accounts = get_all_accounts()
        for acc in accounts:
            await self.reconnect_account(acc)

    async def disconnect_account(self, phone: str):
        client = self.clients.pop(phone, None)
        if client:
            await client.disconnect()
            update_account_status(phone, "disconnected")
            logger.info(f"Disconnected {phone}")

    async def disconnect_all(self):
        for phone in list(self.clients.keys()):
            await self.disconnect_account(phone)

    def get_connected_clients(self) -> list[TelegramClient]:
        return list(self.clients.values())

    def get_connected_phones(self) -> list[str]:
        return list(self.clients.keys())

    def get_client(self, phone: str):
        return self.clients.get(phone)

    def connected_count(self) -> int:
        return len(self.clients)
