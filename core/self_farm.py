"""
CyberTG – Self-Farm Module
Automated Telegram account creation via SMS APIs + Telethon.
Creates accounts, saves sessions to disk + DB, ready for adder round-robin.
"""
import asyncio
import random
import time
import requests
from datetime import datetime

from telethon import TelegramClient, functions
from telethon.errors import (
    PhoneNumberBannedError,
    PhoneCodeInvalidError,
    FloodWaitError,
    PhoneNumberOccupiedError,
)
from core.db import (
    add_farmed_account,
    update_farm_status,
    update_farm_activity,
    get_farmed_accounts,
    get_setting,
    set_setting,
    update_account_status,
)
from core.logger import logger
from core.session_manager import SESSIONS_DIR

# ─── SMS Provider Configs ──────────────────────────────────────────
SMS_PROVIDERS = {
    "smspva": {
        "name": "SMSPVA",
        "base_url": "https://smspva.com/priemnik.php",
        "price_approx": 0.65,
    },
    "5sim": {
        "name": "5sim.net",
        "base_url": "https://5sim.net/v1",
        "price_approx": 0.014,
    },
    "smsactivate": {
        "name": "SMS-Activate",
        "base_url": "https://api.sms-activate.org/stubs/handler_api.php",
        "price_approx": 0.20,
    },
}

COUNTRIES = {
    "US": "United States",
    "BR": "Brazil",
    "IN": "India",
    "RU": "Russia",
    "UK": "United Kingdom",
    "ID": "Indonesia",
    "NG": "Nigeria",
    "PH": "Philippines",
    "MM": "Myanmar",
    "KE": "Kenya",
}


# ─── SMS API Adapters ──────────────────────────────────────────────
class SMSAdapter:
    """Base SMS adapter — override for each provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def buy_number(self, country: str = "US") -> tuple:
        """Returns (phone_number, order_id) or raises."""
        raise NotImplementedError

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        """Poll for SMS code. Returns code string or raises."""
        raise NotImplementedError

    def cancel_number(self, order_id: str):
        """Cancel/release a number if code not received."""
        pass


class SMSPVAAdapter(SMSAdapter):
    """Adapter for smspva.com API."""

    def buy_number(self, country: str = "US") -> tuple:
        country_map = {"US": "US", "BR": "BR", "IN": "IN", "RU": "RU",
                       "UK": "UK", "ID": "ID", "NG": "NG", "PH": "PH"}
        cc = country_map.get(country, "US")

        r = requests.get(
            "https://smspva.com/priemnik.php",
            params={
                "metession": "get_number",
                "country": cc,
                "service": "Telegram",
                "apikey": self.api_key,
            },
            timeout=30,
        )
        data = r.json()
        if data.get("response") == "1":
            return data["number"], str(data["id"])
        raise Exception(f"SMSPVA buy_number failed: {data}")

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        start = time.time()
        while time.time() - start < max_wait:
            r = requests.get(
                "https://smspva.com/priemnik.php",
                params={
                    "metession": "get_sms",
                    "country": "US",
                    "service": "Telegram",
                    "id": order_id,
                    "apikey": self.api_key,
                },
                timeout=15,
            )
            data = r.json()
            if data.get("response") == "1" and data.get("sms"):
                code = "".join(c for c in str(data["sms"]) if c.isdigit())
                if code:
                    return code
            time.sleep(5)
        raise Exception("SMSPVA: SMS code not received within timeout")

    def cancel_number(self, order_id: str):
        try:
            requests.get(
                "https://smspva.com/priemnik.php",
                params={
                    "metession": "denial",
                    "service": "Telegram",
                    "id": order_id,
                    "apikey": self.api_key,
                },
                timeout=10,
            )
        except Exception:
            pass


class FiveSimAdapter(SMSAdapter):
    """Adapter for 5sim.net API."""

    def buy_number(self, country: str = "US") -> tuple:
        country_map = {"US": "usa", "BR": "brazil", "IN": "india", "RU": "russia",
                       "UK": "england", "ID": "indonesia", "NG": "nigeria", "PH": "philippines"}
        cc = country_map.get(country, "usa")

        r = requests.get(
            f"https://5sim.net/v1/user/buy/activation/{cc}/any/telegram",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        data = r.json()
        if "phone" in data and "id" in data:
            phone = data["phone"]
            if not phone.startswith("+"):
                phone = "+" + phone
            return phone, str(data["id"])
        raise Exception(f"5sim buy_number failed: {data}")

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        start = time.time()
        while time.time() - start < max_wait:
            r = requests.get(
                f"https://5sim.net/v1/user/check/{order_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            data = r.json()
            if data.get("sms") and len(data["sms"]) > 0:
                code_text = data["sms"][0].get("code", "")
                code = "".join(c for c in code_text if c.isdigit())
                if code:
                    return code
            time.sleep(5)
        raise Exception("5sim: SMS code not received within timeout")

    def cancel_number(self, order_id: str):
        try:
            requests.get(
                f"https://5sim.net/v1/user/cancel/{order_id}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
        except Exception:
            pass


class SMSActivateAdapter(SMSAdapter):
    """Adapter for sms-activate.org API."""

    def buy_number(self, country: str = "US") -> tuple:
        country_map = {"US": "187", "BR": "73", "IN": "22", "RU": "0",
                       "UK": "16", "ID": "6", "NG": "19", "PH": "4"}
        cc = country_map.get(country, "187")

        r = requests.get(
            "https://api.sms-activate.org/stubs/handler_api.php",
            params={
                "api_key": self.api_key,
                "action": "getNumber",
                "service": "tg",
                "country": cc,
            },
            timeout=30,
        )
        text = r.text
        if text.startswith("ACCESS_NUMBER"):
            parts = text.split(":")
            return "+" + parts[2], parts[1]
        raise Exception(f"SMS-Activate buy_number failed: {text}")

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        # First set status to "ready"
        requests.get(
            "https://api.sms-activate.org/stubs/handler_api.php",
            params={
                "api_key": self.api_key,
                "action": "setStatus",
                "id": order_id,
                "status": "1",
            },
            timeout=10,
        )

        start = time.time()
        while time.time() - start < max_wait:
            r = requests.get(
                "https://api.sms-activate.org/stubs/handler_api.php",
                params={
                    "api_key": self.api_key,
                    "action": "getStatus",
                    "id": order_id,
                },
                timeout=15,
            )
            text = r.text
            if text.startswith("STATUS_OK"):
                code = text.split(":")[1]
                return code
            time.sleep(5)
        raise Exception("SMS-Activate: SMS code not received within timeout")

    def cancel_number(self, order_id: str):
        try:
            requests.get(
                "https://api.sms-activate.org/stubs/handler_api.php",
                params={
                    "api_key": self.api_key,
                    "action": "setStatus",
                    "id": order_id,
                    "status": "8",
                },
                timeout=10,
            )
        except Exception:
            pass


def get_sms_adapter(provider: str, api_key: str) -> SMSAdapter:
    """Factory: return the correct SMS adapter."""
    adapters = {
        "smspva": SMSPVAAdapter,
        "5sim": FiveSimAdapter,
        "smsactivate": SMSActivateAdapter,
    }
    cls = adapters.get(provider)
    if not cls:
        raise ValueError(f"Unknown SMS provider: {provider}")
    return cls(api_key)


# ─── Self-Farm Manager ────────────────────────────────────────────
class SelfFarmManager:
    """Creates Telegram accounts via SMS APIs and saves to sessions + DB."""

    def __init__(self, api_id: int, api_hash: str,
                 sms_provider: str = "5sim", sms_api_key: str = ""):
        self.api_id = api_id
        self.api_hash = api_hash
        self.sms_provider = sms_provider
        self.sms_api_key = sms_api_key
        self._sms = None

    def _get_sms(self) -> SMSAdapter:
        if not self._sms or self.sms_api_key != self._sms.api_key:
            self._sms = get_sms_adapter(self.sms_provider, self.sms_api_key)
        return self._sms

    async def create_single_account(self, country: str = "US",
                                     progress_callback=None) -> dict:
        """
        Buy a number, register on Telegram, setup profile, save session.
        Returns dict with account info or raises on failure.
        """
        sms = self._get_sms()
        phone = None
        order_id = None
        client = None

        try:
            # Step 1: Buy number
            if progress_callback:
                progress_callback("buying_number", phone)
            phone, order_id = sms.buy_number(country)
            logger.info(f"🔢 Number purchased: {phone} (order {order_id})")

            # Step 2: Connect Telethon client
            if progress_callback:
                progress_callback("connecting", phone)
            import os
            session_path = os.path.join(SESSIONS_DIR, phone.replace("+", ""))
            client = TelegramClient(
                session_path,
                self.api_id,
                self.api_hash,
                device_model="Telegram Desktop 5.12.0 x64",
                system_version="Windows 11 Pro",
                app_version="5.12.0",
                lang_code="pt-br",
                system_lang_code="pt-br",
            )
            await client.connect()

            # Step 3: Send code request
            if progress_callback:
                progress_callback("sending_code", phone)
            sent = await client.send_code_request(phone)
            phone_code_hash = sent.phone_code_hash
            logger.info(f"📨 Code requested for {phone}")

            # Step 4: Wait for SMS code (blocking in thread)
            if progress_callback:
                progress_callback("waiting_sms", phone)
            code = await asyncio.get_event_loop().run_in_executor(
                None, sms.get_code, order_id, 120
            )
            logger.info(f"✅ SMS code received for {phone}: {code}")

            # Step 5: Sign in or sign up
            if progress_callback:
                progress_callback("signing_in", phone)
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                logger.info(f"Signed in to existing account: {phone}")
            except PhoneNumberOccupiedError:
                logger.info(f"Number already has account, signed in: {phone}")
            except PhoneCodeInvalidError:
                raise Exception(f"Invalid SMS code for {phone}")
            except Exception as sign_err:
                # Might need sign_up for new number
                try:
                    rand_id = random.randint(10000, 99999)
                    await client.sign_up(
                        code,
                        first_name=f"User{rand_id}",
                        phone_code_hash=phone_code_hash,
                    )
                    logger.info(f"📝 Signed up new account: {phone}")
                except Exception as signup_err:
                    raise Exception(f"Sign in/up failed: {sign_err} / {signup_err}")

            # Step 6: Setup profile
            if progress_callback:
                progress_callback("setup_profile", phone)
            try:
                names = ["Alex", "Maria", "John", "Sara", "David", "Anna",
                         "Daniel", "Emily", "Carlos", "Sofia", "Lucas", "Mia"]
                lasts = ["Smith", "Silva", "Kumar", "Lee", "Garcia", "Jones",
                         "Brown", "Davis", "Wilson", "Lopez", "Martin", "Clark"]
                await client(functions.account.UpdateProfileRequest(
                    first_name=random.choice(names),
                    last_name=random.choice(lasts),
                    about=""
                ))
            except Exception:
                pass  # Profile update is non-critical

            # Step 7: Save to DB
            if progress_callback:
                progress_callback("saving", phone)
            phone_clean = phone.replace("+", "")
            cost = SMS_PROVIDERS.get(self.sms_provider, {}).get("price_approx", 0.50)
            add_farmed_account(
                phone_clean, str(self.api_id), self.api_hash,
                self.sms_provider, country, cost
            )
            update_account_status(phone_clean, "farmed")
            logger.success(f"🌱 Account farmed successfully: {phone} (${cost:.2f})")

            await client.disconnect()

            return {
                "phone": phone_clean,
                "status": "created",
                "cost": cost,
                "provider": self.sms_provider,
                "country": country,
            }

        except Exception as e:
            logger.error(f"❌ Farm failed for {phone or 'unknown'}: {e}")
            if order_id:
                try:
                    sms.cancel_number(order_id)
                except Exception:
                    pass
            if phone:
                phone_clean = phone.replace("+", "")
                update_farm_status(phone_clean, "failed")
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            raise

    async def bulk_create(self, quantity: int = 10, country: str = "US",
                           delay_between: float = 15.0,
                           progress_callback=None,
                           stop_event: asyncio.Event = None) -> dict:
        """
        Create multiple accounts sequentially with delay.
        Returns stats dict.
        """
        created = 0
        failed = 0
        total_cost = 0.0
        results = []

        logger.info(f"🚜 Starting bulk farm: {quantity} accounts in {country}")

        for i in range(quantity):
            if stop_event and stop_event.is_set():
                logger.warning("Farm stopped by user")
                break

            logger.info(f"━━━ Account {i + 1}/{quantity} ━━━")

            try:
                result = await self.create_single_account(
                    country=country,
                    progress_callback=progress_callback,
                )
                created += 1
                total_cost += result.get("cost", 0.0)
                results.append(result)
            except Exception as e:
                failed += 1
                logger.error(f"Account {i + 1} failed: {e}")

            # Progress
            if progress_callback:
                progress_callback("batch_progress", f"{created}/{quantity} created, {failed} failed")

            # Delay between creations (avoid rate limits)
            if i < quantity - 1:
                delay = random.uniform(delay_between * 0.8, delay_between * 1.2)
                logger.info(f"⏳ Waiting {delay:.1f}s before next account...")
                for _ in range(int(delay * 2)):
                    if stop_event and stop_event.is_set():
                        break
                    await asyncio.sleep(0.5)

        logger.success(
            f"🏁 Bulk farm done: {created} created, {failed} failed, "
            f"${total_cost:.2f} total cost"
        )

        return {
            "created": created,
            "failed": failed,
            "total_cost": total_cost,
            "results": results,
        }

    async def start_aging(self, phone_list: list, api_id: int = None,
                           api_hash: str = None):
        """
        Basic aging routine: log in, send a saved message, add a contact.
        Run daily to make accounts look aged/active.
        """
        _api_id = api_id or self.api_id
        _api_hash = api_hash or self.api_hash

        for phone in phone_list:
            try:
                import os
                session_path = os.path.join(SESSIONS_DIR, phone)
                client = TelegramClient(
                    session_path, _api_id, _api_hash,
                    device_model="Telegram Desktop 5.12.0 x64",
                    system_version="Windows 11 Pro",
                    app_version="5.12.0",
                    lang_code="pt-br",
                    system_lang_code="pt-br",
                )
                await client.connect()

                if not await client.is_user_authorized():
                    logger.warning(f"Aging skip {phone} — not authorized")
                    await client.disconnect()
                    continue

                # Send a message to Saved Messages
                messages = [
                    "📝 Daily note", "🔄 Sync check", "✅ Active", "🕐 Ping",
                    "📊 Status OK", "🔒 Verified", "💬 Online", "⚡ Updated",
                ]
                await client.send_message("me", random.choice(messages))

                # Update profile slightly
                bios = ["", "Hello!", "Active user", "🌍", "📱"]
                try:
                    await client(functions.account.UpdateProfileRequest(
                        about=random.choice(bios)
                    ))
                except Exception:
                    pass

                update_farm_activity(phone)
                logger.success(f"🌱 Aged activity for {phone}")

                await client.disconnect()
                await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"Aging error for {phone}: {e}")
                continue
