"""
CyberTG – Self-Farm Module v2
Automated Telegram account creation via SMS APIs + Telethon.
Creates accounts, saves sessions to disk + DB, ready for adder round-robin.

Supported SMS providers: 5sim.net, smspva.com, sms-activate.org
"""
import asyncio
import os
import random
import time
import traceback
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
    "5sim": {
        "name": "5sim.net",
        "base_url": "https://5sim.net/v1",
        "price_approx": 0.014,
    },
    "smspva": {
        "name": "SMSPVA",
        "base_url": "https://smspva.com/priemnik.php",
        "price_approx": 0.65,
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

# 5sim country slugs
_5SIM_COUNTRIES = {
    "US": "usa", "BR": "brazil", "IN": "india", "RU": "russia",
    "UK": "england", "ID": "indonesia", "NG": "nigeria", "PH": "philippines",
    "MM": "myanmar", "KE": "kenya",
}


# ─── SMS API Adapters ──────────────────────────────────────────────
class SMSAdapter:
    """Base SMS adapter — override for each provider."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def buy_number(self, country: str = "US") -> tuple:
        raise NotImplementedError

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        raise NotImplementedError

    def cancel_number(self, order_id: str):
        pass

    def finish_number(self, order_id: str):
        pass


# ────────────────────── 5sim.net ──────────────────────────
class FiveSimAdapter(SMSAdapter):
    """Adapter for 5sim.net API (Bearer token auth)."""

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def check_balance(self) -> float:
        """Check 5sim balance to verify API key works."""
        try:
            r = requests.get(
                "https://5sim.net/v1/user/profile",
                headers=self._headers(), timeout=15,
            )
            logger.info(f"[5sim] Profile response ({r.status_code}): {r.text[:300]}")
            if r.status_code == 200:
                data = r.json()
                balance = data.get("balance", 0)
                logger.info(f"[5sim] Balance: {balance}")
                return float(balance)
            elif r.status_code == 401:
                logger.error("[5sim] ❌ API Key INVALID (401 Unauthorized)")
                raise Exception("5sim API Key is invalid (401)")
            else:
                logger.error(f"[5sim] Profile check failed: {r.status_code} {r.text[:200]}")
                raise Exception(f"5sim profile check failed: {r.status_code}")
        except requests.RequestException as e:
            logger.error(f"[5sim] Connection error: {e}")
            raise

    def buy_number(self, country: str = "US") -> tuple:
        cc = _5SIM_COUNTRIES.get(country, "usa")

        # Buy activation for telegram
        url = f"https://5sim.net/v1/user/buy/activation/{cc}/any/telegram"
        logger.info(f"[5sim] Buying number: GET {url}")

        r = requests.get(url, headers=self._headers(), timeout=30)
        logger.info(f"[5sim] Buy response ({r.status_code}): {r.text[:500]}")

        if r.status_code != 200:
            raise Exception(f"5sim buy_number HTTP {r.status_code}: {r.text[:300]}")

        data = r.json()
        if "id" not in data or "phone" not in data:
            raise Exception(f"5sim buy_number missing id/phone: {data}")

        phone = str(data["phone"])
        if not phone.startswith("+"):
            phone = "+" + phone
        order_id = str(data["id"])

        logger.success(f"[5sim] ✅ Number purchased: {phone} (order #{order_id})")
        return phone, order_id

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        """Poll 5sim for SMS code."""
        url = f"https://5sim.net/v1/user/check/{order_id}"
        start = time.time()
        attempt = 0

        while time.time() - start < max_wait:
            attempt += 1
            try:
                r = requests.get(url, headers=self._headers(), timeout=15)
                data = r.json()
                status = data.get("status", "")

                logger.info(
                    f"[5sim] Check #{attempt} (order {order_id}): "
                    f"status={status}, sms={data.get('sms', [])}"
                )

                # 5sim statuses: PENDING, RECEIVED, CANCELED, TIMEOUT, FINISHED, BANNED
                if status == "RECEIVED" or status == "FINISHED":
                    sms_list = data.get("sms", [])
                    if sms_list and len(sms_list) > 0:
                        # The code can be in 'code' or 'text' field
                        raw_code = sms_list[0].get("code", "") or sms_list[0].get("text", "")
                        code = "".join(c for c in str(raw_code) if c.isdigit())
                        if code and len(code) >= 4:
                            logger.success(f"[5sim] ✅ Code received: {code}")
                            return code
                        else:
                            logger.warning(f"[5sim] SMS found but no valid code: '{raw_code}'")

                elif status in ("CANCELED", "TIMEOUT", "BANNED"):
                    raise Exception(f"5sim order {order_id} ended with status: {status}")

            except requests.RequestException as e:
                logger.warning(f"[5sim] Check request error: {e}")

            time.sleep(5)

        raise Exception(f"5sim: SMS code not received within {max_wait}s (order {order_id})")

    def cancel_number(self, order_id: str):
        try:
            r = requests.get(
                f"https://5sim.net/v1/user/cancel/{order_id}",
                headers=self._headers(), timeout=10,
            )
            logger.info(f"[5sim] Cancel order {order_id}: {r.status_code}")
        except Exception as e:
            logger.warning(f"[5sim] Cancel failed: {e}")

    def finish_number(self, order_id: str):
        try:
            r = requests.get(
                f"https://5sim.net/v1/user/finish/{order_id}",
                headers=self._headers(), timeout=10,
            )
            logger.info(f"[5sim] Finish order {order_id}: {r.status_code}")
        except Exception as e:
            logger.warning(f"[5sim] Finish failed: {e}")


# ────────────────────── SMSPVA ────────────────────────────
class SMSPVAAdapter(SMSAdapter):

    def buy_number(self, country: str = "US") -> tuple:
        r = requests.get(
            "https://smspva.com/priemnik.php",
            params={
                "metession": "get_number", "country": country,
                "service": "Telegram", "apikey": self.api_key,
            },
            timeout=30,
        )
        logger.info(f"[SMSPVA] Buy response: {r.text[:300]}")
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
                    "metession": "get_sms", "country": "US",
                    "service": "Telegram", "id": order_id,
                    "apikey": self.api_key,
                },
                timeout=15,
            )
            data = r.json()
            logger.info(f"[SMSPVA] Check: {data}")
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
                    "metession": "denial", "service": "Telegram",
                    "id": order_id, "apikey": self.api_key,
                },
                timeout=10,
            )
        except Exception:
            pass


# ────────────────────── SMS-Activate ──────────────────────
class SMSActivateAdapter(SMSAdapter):

    def buy_number(self, country: str = "US") -> tuple:
        country_map = {"US": "187", "BR": "73", "IN": "22", "RU": "0",
                       "UK": "16", "ID": "6", "NG": "19", "PH": "4"}
        cc = country_map.get(country, "187")
        r = requests.get(
            "https://api.sms-activate.org/stubs/handler_api.php",
            params={
                "api_key": self.api_key, "action": "getNumber",
                "service": "tg", "country": cc,
            },
            timeout=30,
        )
        logger.info(f"[SMS-Activate] Buy response: {r.text[:300]}")
        text = r.text
        if text.startswith("ACCESS_NUMBER"):
            parts = text.split(":")
            return "+" + parts[2], parts[1]
        raise Exception(f"SMS-Activate buy_number failed: {text}")

    def get_code(self, order_id: str, max_wait: int = 120) -> str:
        requests.get(
            "https://api.sms-activate.org/stubs/handler_api.php",
            params={
                "api_key": self.api_key, "action": "setStatus",
                "id": order_id, "status": "1",
            },
            timeout=10,
        )
        start = time.time()
        while time.time() - start < max_wait:
            r = requests.get(
                "https://api.sms-activate.org/stubs/handler_api.php",
                params={
                    "api_key": self.api_key, "action": "getStatus",
                    "id": order_id,
                },
                timeout=15,
            )
            logger.info(f"[SMS-Activate] Check: {r.text[:200]}")
            text = r.text
            if text.startswith("STATUS_OK"):
                return text.split(":")[1]
            time.sleep(5)
        raise Exception("SMS-Activate: SMS code not received within timeout")

    def cancel_number(self, order_id: str):
        try:
            requests.get(
                "https://api.sms-activate.org/stubs/handler_api.php",
                params={
                    "api_key": self.api_key, "action": "setStatus",
                    "id": order_id, "status": "8",
                },
                timeout=10,
            )
        except Exception:
            pass


# ─── Factory ──────────────────────────────────────────────
def get_sms_adapter(provider: str, api_key: str) -> SMSAdapter:
    adapters = {
        "5sim": FiveSimAdapter,
        "smspva": SMSPVAAdapter,
        "smsactivate": SMSActivateAdapter,
    }
    cls = adapters.get(provider)
    if not cls:
        raise ValueError(f"Unknown SMS provider: {provider}")
    logger.info(f"[SMS] Using provider: {provider}")
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
        Full flow: buy number → send code → receive SMS → sign up → save.
        All blocking HTTP calls run in executor to avoid blocking the event loop.
        """
        sms = self._get_sms()
        phone = None
        order_id = None
        client = None
        loop = asyncio.get_event_loop()

        try:
            # ─── Step 1: Validate API key (5sim only) ──────────
            if self.sms_provider == "5sim":
                logger.info("[Farm] Step 0: Checking 5sim balance...")
                if progress_callback:
                    progress_callback("checking_api", "Verifying API key...")
                balance = await loop.run_in_executor(None, sms.check_balance)
                logger.info(f"[Farm] 5sim balance: {balance}")
                if balance <= 0:
                    raise Exception(f"5sim balance is zero ({balance}). Add funds first.")

            # ─── Step 1: Buy number ────────────────────────────
            logger.info(f"[Farm] Step 1: Buying number ({self.sms_provider}, {country})...")
            if progress_callback:
                progress_callback("buying_number", None)

            phone, order_id = await loop.run_in_executor(
                None, sms.buy_number, country
            )
            logger.success(f"[Farm] 🔢 Number: {phone} (order #{order_id})")

            # ─── Step 2: Connect Telethon ──────────────────────
            logger.info("[Farm] Step 2: Connecting Telethon client...")
            if progress_callback:
                progress_callback("connecting", phone)

            session_path = os.path.join(SESSIONS_DIR, phone.replace("+", ""))
            client = TelegramClient(
                session_path, self.api_id, self.api_hash,
                device_model="Telegram Desktop 5.12.0 x64",
                system_version="Windows 11 Pro",
                app_version="5.12.0",
                lang_code="pt-br",
                system_lang_code="pt-br",
            )
            await client.connect()
            logger.success("[Farm] Telethon connected")

            # ─── Step 3: Request verification code ─────────────
            logger.info(f"[Farm] Step 3: Sending code request to {phone}...")
            if progress_callback:
                progress_callback("sending_code", phone)

            sent = await client.send_code_request(phone)
            phone_code_hash = sent.phone_code_hash
            logger.success(f"[Farm] 📨 Code request sent (hash: {phone_code_hash[:10]}...)")

            # ─── Step 4: Wait for SMS code ─────────────────────
            logger.info("[Farm] Step 4: Waiting for SMS code...")
            if progress_callback:
                progress_callback("waiting_sms", phone)

            code = await loop.run_in_executor(
                None, sms.get_code, order_id, 120
            )
            logger.success(f"[Farm] ✅ SMS code received: {code}")

            # ─── Step 5: Sign in / Sign up ─────────────────────
            logger.info(f"[Farm] Step 5: Signing in with code {code}...")
            if progress_callback:
                progress_callback("signing_in", phone)

            signed_up = False
            try:
                await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                logger.success(f"[Farm] Signed in to existing account: {phone}")
            except PhoneCodeInvalidError:
                raise Exception(f"Invalid SMS code: {code}")
            except PhoneNumberBannedError:
                raise Exception(f"Number {phone} is BANNED by Telegram")
            except Exception as sign_err:
                # Number is new → need sign_up
                logger.info(f"[Farm] sign_in failed ({sign_err}), trying sign_up...")
                try:
                    rand_id = random.randint(10000, 99999)
                    await client.sign_up(
                        code,
                        first_name=f"User{rand_id}",
                        phone_code_hash=phone_code_hash,
                    )
                    signed_up = True
                    logger.success(f"[Farm] 📝 Signed up new account: {phone}")
                except Exception as signup_err:
                    raise Exception(
                        f"Sign in failed: {sign_err} | Sign up failed: {signup_err}"
                    )

            # ─── Step 6: Setup profile ─────────────────────────
            logger.info("[Farm] Step 6: Setting up profile...")
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
                logger.success("[Farm] Profile updated")
            except Exception as e:
                logger.warning(f"[Farm] Profile update skipped: {e}")

            # ─── Step 7: Finish SMS order ──────────────────────
            try:
                await loop.run_in_executor(None, sms.finish_number, order_id)
            except Exception:
                pass

            # ─── Step 8: Save to DB ────────────────────────────
            logger.info("[Farm] Step 7: Saving to database...")
            if progress_callback:
                progress_callback("saving", phone)

            phone_clean = phone.replace("+", "")
            cost = SMS_PROVIDERS.get(self.sms_provider, {}).get("price_approx", 0.50)
            add_farmed_account(
                phone_clean, str(self.api_id), self.api_hash,
                self.sms_provider, country, cost
            )
            update_account_status(phone_clean, "farmed")
            logger.success(f"[Farm] 🌱 DONE: {phone} saved (${cost:.2f})")

            await client.disconnect()

            return {
                "phone": phone_clean,
                "status": "created",
                "cost": cost,
                "provider": self.sms_provider,
                "country": country,
            }

        except Exception as e:
            logger.error(f"[Farm] ❌ FAILED for {phone or 'unknown'}: {e}")
            logger.error(f"[Farm] Traceback: {traceback.format_exc()}")

            # Cancel unused SMS number
            if order_id:
                try:
                    await loop.run_in_executor(None, sms.cancel_number, order_id)
                except Exception:
                    pass

            # Mark as failed in DB
            if phone:
                try:
                    phone_clean = phone.replace("+", "")
                    update_farm_status(phone_clean, "failed")
                except Exception:
                    pass

            # Disconnect client
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

            raise

    async def bulk_create(self, quantity: int = 10, country: str = "US",
                           delay_between: float = 15.0,
                           progress_callback=None,
                           stop_event=None) -> dict:
        """Create multiple accounts sequentially with delay."""
        created = 0
        failed = 0
        total_cost = 0.0
        results = []

        logger.info(f"[Farm] 🚜 BULK START: {quantity} accounts, country={country}, "
                     f"provider={self.sms_provider}, delay={delay_between}s")

        for i in range(quantity):
            if stop_event and stop_event.is_set():
                logger.warning("[Farm] ⬛ Stopped by user")
                break

            logger.info(f"[Farm] ━━━ Account {i + 1}/{quantity} ━━━")

            try:
                result = await self.create_single_account(
                    country=country,
                    progress_callback=progress_callback,
                )
                created += 1
                total_cost += result.get("cost", 0.0)
                results.append(result)
                logger.success(f"[Farm] Account {i + 1} ✅ OK ({created} total created)")
            except Exception as e:
                failed += 1
                logger.error(f"[Farm] Account {i + 1} ❌ FAILED: {e}")

            # Progress callback
            if progress_callback:
                progress_callback(
                    "batch_progress",
                    f"{created}/{quantity} created, {failed} failed"
                )

            # Delay between creations
            if i < quantity - 1:
                delay = random.uniform(delay_between * 0.8, delay_between * 1.2)
                logger.info(f"[Farm] ⏳ Waiting {delay:.1f}s before next...")
                for _ in range(int(delay * 2)):
                    if stop_event and stop_event.is_set():
                        break
                    await asyncio.sleep(0.5)

        logger.success(
            f"[Farm] 🏁 BULK DONE: {created} created, {failed} failed, "
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
        """Basic aging: log in, send saved message, update profile."""
        _api_id = api_id or self.api_id
        _api_hash = api_hash or self.api_hash

        logger.info(f"[Aging] Starting for {len(phone_list)} accounts...")

        for phone in phone_list:
            try:
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
                    logger.warning(f"[Aging] Skip {phone} — not authorized")
                    await client.disconnect()
                    continue

                messages = [
                    "📝 Daily note", "🔄 Sync check", "✅ Active", "🕐 Ping",
                    "📊 Status OK", "🔒 Verified", "💬 Online", "⚡ Updated",
                ]
                await client.send_message("me", random.choice(messages))

                bios = ["", "Hello!", "Active user", "🌍", "📱"]
                try:
                    await client(functions.account.UpdateProfileRequest(
                        about=random.choice(bios)
                    ))
                except Exception:
                    pass

                update_farm_activity(phone)
                logger.success(f"[Aging] ✅ {phone} aged")

                await client.disconnect()
                await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                logger.error(f"[Aging] Error for {phone}: {e}")
                continue
