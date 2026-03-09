"""
CyberTG – Self-Farm Tab
GUI for creating and managing farmed Telegram accounts via SMS APIs.
"""
import asyncio
import threading
import customtkinter as ctk
from core.session_manager import SessionManager
from core.self_farm import SelfFarmManager, SMS_PROVIDERS, COUNTRIES
from core.db import (
    get_farmed_accounts, get_farm_stats, get_setting, set_setting,
)
from core.logger import logger

BG_DARK      = "#0a0e27"
BG_CARD      = "#111638"
BG_INPUT     = "#161b42"
NEON_CYAN    = "#00d4ff"
NEON_PURPLE  = "#7c3aed"
NEON_GREEN   = "#10b981"
NEON_RED     = "#ef4444"
NEON_YELLOW  = "#f59e0b"
NEON_ORANGE  = "#f97316"
TEXT_PRIMARY = "#e2e8f0"
TEXT_MUTED   = "#64748b"
BORDER       = "#1e2550"


class SelfFarmTab:
    """Self-Farm interface — create Telegram accounts via SMS APIs."""

    def __init__(self, parent: ctk.CTkFrame, session_manager: SessionManager):
        self.parent = parent
        self.sm = session_manager
        self._is_farming = False
        self._stop_event = None
        self._build_ui()

    def _build_ui(self):
        self.parent.configure(fg_color=BG_DARK)

        # ── Config Panel ───────────────────────────────────────
        config = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        config.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(config, text="🌱 Self-Farm — Account Creator",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_GREEN).pack(anchor="w", padx=15, pady=(12, 8))

        # Row 1: API ID, API Hash
        row1 = ctk.CTkFrame(config, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(row1, text="API ID:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        self.api_id_entry = ctk.CTkEntry(row1, placeholder_text="12345678",
                                          width=130, height=35,
                                          fg_color=BG_INPUT, border_color=BORDER,
                                          text_color=TEXT_PRIMARY)
        self.api_id_entry.pack(side="left", padx=5)

        # Pre-fill from settings
        saved_api_id = get_setting("farm_api_id", "")
        if saved_api_id:
            self.api_id_entry.insert(0, saved_api_id)

        ctk.CTkLabel(row1, text="API Hash:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 5))
        self.api_hash_entry = ctk.CTkEntry(row1, placeholder_text="abcdef1234567890...",
                                            width=260, height=35,
                                            fg_color=BG_INPUT, border_color=BORDER,
                                            text_color=TEXT_PRIMARY)
        self.api_hash_entry.pack(side="left", padx=5)

        saved_api_hash = get_setting("farm_api_hash", "")
        if saved_api_hash:
            self.api_hash_entry.insert(0, saved_api_hash)

        # Row 2: SMS Provider, API Key
        row2 = ctk.CTkFrame(config, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(row2, text="SMS Provider:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        provider_names = list(SMS_PROVIDERS.keys())
        self.provider_menu = ctk.CTkOptionMenu(row2, values=provider_names,
                                                width=150, height=35,
                                                fg_color=BG_INPUT, button_color=NEON_PURPLE,
                                                text_color=TEXT_PRIMARY)
        saved_provider = get_setting("farm_sms_provider", "5sim")
        self.provider_menu.set(saved_provider if saved_provider in provider_names else "5sim")
        self.provider_menu.pack(side="left", padx=5)

        ctk.CTkLabel(row2, text="SMS API Key:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 5))
        self.sms_key_entry = ctk.CTkEntry(row2, placeholder_text="your-sms-api-key",
                                           width=300, height=35, show="•",
                                           fg_color=BG_INPUT, border_color=BORDER,
                                           text_color=TEXT_PRIMARY)
        self.sms_key_entry.pack(side="left", padx=5)

        saved_sms_key = get_setting("farm_sms_key", "")
        if saved_sms_key:
            self.sms_key_entry.insert(0, saved_sms_key)

        # Row 3: Country, Quantity, Delay
        row3 = ctk.CTkFrame(config, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(5, 3))

        ctk.CTkLabel(row3, text="Country:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        country_codes = list(COUNTRIES.keys())
        self.country_menu = ctk.CTkOptionMenu(row3, values=country_codes,
                                               width=80, height=35,
                                               fg_color=BG_INPUT, button_color=NEON_PURPLE,
                                               text_color=TEXT_PRIMARY)
        self.country_menu.set("US")
        self.country_menu.pack(side="left", padx=5)

        ctk.CTkLabel(row3, text="Quantity:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 5))
        self.qty_slider = ctk.CTkSlider(row3, from_=1, to=100, number_of_steps=99,
                                         width=180, height=18,
                                         fg_color=BG_INPUT,
                                         progress_color=NEON_GREEN,
                                         button_color=NEON_CYAN)
        self.qty_slider.set(10)
        self.qty_slider.pack(side="left", padx=5)
        self.qty_label = ctk.CTkLabel(row3, text="10", text_color=NEON_CYAN,
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.qty_label.pack(side="left", padx=(3, 15))
        self.qty_slider.configure(command=lambda v: self.qty_label.configure(text=f"{int(v)}"))

        ctk.CTkLabel(row3, text="Delay (s):", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        self.delay_slider = ctk.CTkSlider(row3, from_=5, to=60, number_of_steps=55,
                                           width=120, height=18,
                                           fg_color=BG_INPUT,
                                           progress_color=NEON_PURPLE,
                                           button_color=NEON_CYAN)
        self.delay_slider.set(15)
        self.delay_slider.pack(side="left", padx=5)
        self.delay_label = ctk.CTkLabel(row3, text="15s", text_color=NEON_CYAN,
                                         font=ctk.CTkFont(size=12, weight="bold"))
        self.delay_label.pack(side="left")
        self.delay_slider.configure(command=lambda v: self.delay_label.configure(text=f"{int(v)}s"))

        # Row 4: Buttons
        row4 = ctk.CTkFrame(config, fg_color="transparent")
        row4.pack(fill="x", padx=15, pady=(8, 12))

        self.farm_btn = ctk.CTkButton(row4, text="🚜 Start Farming", width=200, height=44,
                                       fg_color=NEON_GREEN, hover_color="#059669",
                                       text_color=BG_DARK,
                                       font=ctk.CTkFont(size=14, weight="bold"),
                                       command=self._start_farm)
        self.farm_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(row4, text="⬛ Stop", width=100, height=44,
                                       fg_color=NEON_RED, hover_color="#dc2626",
                                       text_color="#fff",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       command=self._stop_farm, state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        self.age_btn = ctk.CTkButton(row4, text="🌱 Run Aging Routine", width=180, height=44,
                                      fg_color=NEON_ORANGE, hover_color="#ea580c",
                                      text_color=BG_DARK,
                                      font=ctk.CTkFont(size=13, weight="bold"),
                                      command=self._run_aging)
        self.age_btn.pack(side="left", padx=5)

        ctk.CTkButton(row4, text="💾 Save Config", width=120, height=44,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      border_width=1, border_color=NEON_CYAN,
                      text_color=NEON_CYAN,
                      font=ctk.CTkFont(size=12),
                      command=self._save_config).pack(side="right")

        # ── Progress Panel ────────────────────────────────────
        prog_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        prog_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(prog_frame, text="📊 Farm Progress",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(12, 5))

        self.progress = ctk.CTkProgressBar(prog_frame, width=700, height=20,
                                            fg_color=BG_INPUT,
                                            progress_color=NEON_GREEN)
        self.progress.pack(padx=15, pady=5)
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(prog_frame, text="Ready to farm",
                                            text_color=TEXT_MUTED,
                                            font=ctk.CTkFont(size=12))
        self.progress_label.pack(padx=15, pady=(0, 5))

        # Stats
        stats_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=(5, 15))

        self.stat_total = self._stat_card(stats_row, "📦 Total", "0", NEON_CYAN)
        self.stat_created = self._stat_card(stats_row, "✅ Created", "0", NEON_GREEN)
        self.stat_aged = self._stat_card(stats_row, "🌱 Aged 30d+", "0", NEON_PURPLE)
        self.stat_failed = self._stat_card(stats_row, "❌ Failed", "0", NEON_RED)
        self.stat_cost = self._stat_card(stats_row, "💰 Total Cost", "$0", NEON_YELLOW)

        self._refresh_stats()

        # ── Accounts Table ────────────────────────────────────
        table_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        top_bar = ctk.CTkFrame(table_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(top_bar, text="🗃️ Farmed Accounts",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")

        ctk.CTkButton(top_bar, text="🔄 Refresh", width=90, height=30,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      text_color=NEON_CYAN, font=ctk.CTkFont(size=11),
                      command=self._refresh_table).pack(side="right")

        # Headers
        hdr = ctk.CTkFrame(table_frame, fg_color=BG_INPUT, corner_radius=6, height=32)
        hdr.pack(fill="x", padx=12, pady=(0, 2))
        hdr.pack_propagate(False)
        for text, w in [("Phone", 140), ("Provider", 100), ("Country", 70),
                        ("Cost", 70), ("Status", 100), ("Age (days)", 90), ("Last Activity", 140)]:
            ctk.CTkLabel(hdr, text=text, width=w, text_color=NEON_CYAN,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)

        self.table_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.table_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._refresh_table()

    def _stat_card(self, parent, label, value, color):
        card = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=8,
                            width=140, height=55)
        card.pack(side="left", padx=5, expand=True, fill="x")
        card.pack_propagate(False)

        val_label = ctk.CTkLabel(card, text=value,
                                  font=ctk.CTkFont(size=18, weight="bold"),
                                  text_color=color)
        val_label.pack(pady=(5, 0))
        ctk.CTkLabel(card, text=label, text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=10)).pack()
        return val_label

    def _refresh_stats(self):
        try:
            stats = get_farm_stats()
            self.stat_total.configure(text=str(stats["total"]))
            self.stat_created.configure(text=str(stats["created"]))
            self.stat_aged.configure(text=str(stats["aged"]))
            self.stat_failed.configure(text=str(stats["failed"]))
            self.stat_cost.configure(text=f"${stats['total_cost']:.2f}")
        except Exception:
            pass

    def _refresh_table(self):
        for w in self.table_scroll.winfo_children():
            w.destroy()

        accounts = get_farmed_accounts()
        if not accounts:
            ctk.CTkLabel(self.table_scroll, text="No farmed accounts yet — start farming!",
                         text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=13)).pack(pady=30)
            return

        for acc in accounts[:200]:
            row = ctk.CTkFrame(self.table_scroll, fg_color=BG_INPUT,
                               corner_radius=6, height=32)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=acc["phone"], width=140,
                         text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=acc.get("sms_provider", ""), width=100,
                         text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=acc.get("country", ""), width=70,
                         text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"${acc.get('cost', 0):.2f}", width=70,
                         text_color=NEON_YELLOW, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)

            status = acc.get("status", "")
            s_color = NEON_GREEN if status == "created" else (NEON_RED if status == "failed" else TEXT_MUTED)
            ctk.CTkLabel(row, text=f"● {status}", width=100,
                         text_color=s_color, font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)

            ctk.CTkLabel(row, text=str(acc.get("aged_days", 0)), width=90,
                         text_color=NEON_PURPLE, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=acc.get("last_activity", "—") or "—", width=140,
                         text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)

        self._refresh_stats()

    def _save_config(self):
        set_setting("farm_api_id", self.api_id_entry.get().strip())
        set_setting("farm_api_hash", self.api_hash_entry.get().strip())
        set_setting("farm_sms_provider", self.provider_menu.get())
        set_setting("farm_sms_key", self.sms_key_entry.get().strip())
        logger.success("💾 Farm config saved!")

    def _validate_config(self):
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        sms_key = self.sms_key_entry.get().strip()

        if not api_id or not api_hash:
            logger.error("API ID and API Hash are required")
            return None
        if not sms_key:
            logger.error("SMS API Key is required")
            return None

        try:
            int(api_id)
        except ValueError:
            logger.error("API ID must be a number")
            return None

        return {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "sms_provider": self.provider_menu.get(),
            "sms_key": sms_key,
        }

    def _start_farm(self):
        cfg = self._validate_config()
        if not cfg:
            return

        self._save_config()

        self._is_farming = True
        self._stop_event = asyncio.Event()

        self.farm_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.age_btn.configure(state="disabled")
        self.progress.set(0)

        qty = int(self.qty_slider.get())
        country = self.country_menu.get()
        delay = int(self.delay_slider.get())

        threading.Thread(
            target=self._farm_thread,
            args=(cfg, qty, country, delay),
            daemon=True
        ).start()

    def _farm_thread(self, cfg, qty, country, delay):
        logger.info(f"[Farm GUI] Thread started: {qty}x {country} via {cfg['sms_provider']}")
        farm = SelfFarmManager(
            api_id=cfg["api_id"],
            api_hash=cfg["api_hash"],
            sms_provider=cfg["sms_provider"],
            sms_api_key=cfg["sms_key"],
        )

        def on_progress(stage, info):
            self.parent.after(0, lambda: self._update_progress(stage, info, qty))

        try:
            result = self.sm.run_coro(farm.bulk_create(
                quantity=qty,
                country=country,
                delay_between=float(delay),
                progress_callback=on_progress,
                stop_event=self._stop_event,
            ), timeout=86400)
            logger.success(f"[Farm GUI] Thread finished: {result}")
        except Exception as e:
            logger.error(f"[Farm GUI] ❌ Thread error: {e}")
            import traceback
            logger.error(f"[Farm GUI] Traceback: {traceback.format_exc()}")
        finally:
            self.parent.after(0, self._farm_done)

    def _update_progress(self, stage, info, total):
        stage_labels = {
            "checking_api": "🔑 Verifying API key...",
            "buying_number": "🔢 Buying number...",
            "connecting": f"🔌 Connecting ({info})...",
            "sending_code": f"📨 Sending code to {info}...",
            "waiting_sms": f"⏳ Waiting for SMS ({info})...",
            "signing_in": f"🔐 Signing in {info}...",
            "setup_profile": f"👤 Setting up profile ({info})...",
            "saving": f"💾 Saving {info}...",
            "batch_progress": f"📊 {info}",
        }
        label = stage_labels.get(stage, str(stage))
        self.progress_label.configure(text=label)

        if stage == "batch_progress" and info:
            try:
                parts = info.split("/")
                done = int(parts[0])
                if total > 0:
                    self.progress.set(done / total)
            except Exception:
                pass

        self._refresh_stats()

    def _farm_done(self):
        self._is_farming = False
        self.farm_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.age_btn.configure(state="normal")
        self.progress.set(1.0)
        self.progress_label.configure(text="✅ Farm complete!")
        self._refresh_table()
        self._refresh_stats()

    def _stop_farm(self):
        if self._stop_event:
            self._stop_event.set()
        logger.warning("Stopping farm...")

    def _run_aging(self):
        cfg = self._validate_config()
        if not cfg:
            return

        accounts = get_farmed_accounts(status="created")
        if not accounts:
            logger.error("No farmed accounts to age")
            return

        phone_list = [a["phone"] for a in accounts]
        logger.info(f"🌱 Running aging on {len(phone_list)} accounts...")

        self.age_btn.configure(state="disabled")

        threading.Thread(
            target=self._aging_thread,
            args=(cfg, phone_list),
            daemon=True
        ).start()

    def _aging_thread(self, cfg, phone_list):
        farm = SelfFarmManager(
            api_id=cfg["api_id"],
            api_hash=cfg["api_hash"],
            sms_provider=cfg["sms_provider"],
            sms_api_key=cfg["sms_key"],
        )

        try:
            self.sm.run_coro(farm.start_aging(phone_list), timeout=86400)
        except Exception as e:
            logger.error(f"Aging error: {e}")
        finally:
            self.parent.after(0, lambda: self.age_btn.configure(state="normal"))
            self.parent.after(0, self._refresh_table)
