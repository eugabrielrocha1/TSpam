"""
CyberTG – Adder Tab
Bulk-add scraped users to a target group with anti-ban controls.
"""
import asyncio
import threading
from datetime import datetime
import customtkinter as ctk
from core.session_manager import SessionManager
from core.adder import add_members
from core.db import get_scraped_users, get_source_groups, get_scraped_count, get_all_accounts
from core.logger import logger

BG_DARK      = "#0a0e27"
BG_CARD      = "#111638"
BG_INPUT     = "#161b42"
NEON_CYAN    = "#00d4ff"
NEON_PURPLE  = "#7c3aed"
NEON_GREEN   = "#10b981"
NEON_RED     = "#ef4444"
NEON_YELLOW  = "#f59e0b"
TEXT_PRIMARY = "#e2e8f0"
TEXT_MUTED   = "#64748b"
BORDER       = "#1e2550"


class AdderTab:
    """Adder interface — add scraped users to a target group."""

    def __init__(self, parent: ctk.CTkFrame, session_manager: SessionManager):
        self.parent = parent
        self.sm = session_manager
        self._pause_event = None
        self._stop_event = None
        self._is_running = False
        self._build_ui()

    def _build_ui(self):
        self.parent.configure(fg_color=BG_DARK)

        # ── Config Panel ───────────────────────────────────────
        config = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        config.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(config, text="➕ Adder Configuration",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 8))

        # Row 1: Target group + Source
        row1 = ctk.CTkFrame(config, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(row1, text="Target Group:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        self.target_entry = ctk.CTkEntry(row1, placeholder_text="https://t.me/target_group",
                                          width=350, height=38,
                                          fg_color=BG_INPUT, border_color=BORDER,
                                          text_color=TEXT_PRIMARY)
        self.target_entry.pack(side="left", padx=5)

        ctk.CTkLabel(row1, text="Source:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 5))
        self.source_menu = ctk.CTkOptionMenu(row1, values=["All scraped users"],
                                              width=200, height=38,
                                              fg_color=BG_INPUT, button_color=NEON_PURPLE,
                                              text_color=TEXT_PRIMARY)
        self.source_menu.pack(side="left", padx=5)

        ctk.CTkButton(row1, text="🔄", width=38, height=38,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      command=self._refresh_sources).pack(side="left", padx=2)

        # Row 2: Delay sliders
        row2 = ctk.CTkFrame(config, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(8, 3))

        ctk.CTkLabel(row2, text="Delay Range (seconds):", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row2, text="Min:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 3))
        self.delay_min = ctk.CTkSlider(row2, from_=3, to=30, number_of_steps=27,
                                        width=150, height=18,
                                        fg_color=BG_INPUT,
                                        progress_color=NEON_PURPLE,
                                        button_color=NEON_CYAN)
        self.delay_min.set(8)
        self.delay_min.pack(side="left", padx=3)
        self.delay_min_label = ctk.CTkLabel(row2, text="8s", text_color=NEON_CYAN,
                                             font=ctk.CTkFont(size=12, weight="bold"))
        self.delay_min_label.pack(side="left", padx=(0, 15))

        ctk.CTkLabel(row2, text="Max:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 3))
        self.delay_max = ctk.CTkSlider(row2, from_=5, to=60, number_of_steps=55,
                                        width=150, height=18,
                                        fg_color=BG_INPUT,
                                        progress_color=NEON_PURPLE,
                                        button_color=NEON_CYAN)
        self.delay_max.set(25)
        self.delay_max.pack(side="left", padx=3)
        self.delay_max_label = ctk.CTkLabel(row2, text="25s", text_color=NEON_CYAN,
                                             font=ctk.CTkFont(size=12, weight="bold"))
        self.delay_max_label.pack(side="left")

        # Update labels on slider change
        self.delay_min.configure(command=lambda v: self.delay_min_label.configure(text=f"{int(v)}s"))
        self.delay_max.configure(command=lambda v: self.delay_max_label.configure(text=f"{int(v)}s"))

        # Row 2.5: Batch size + Aged filter
        row2b = ctk.CTkFrame(config, fg_color="transparent")
        row2b.pack(fill="x", padx=15, pady=(5, 3))

        ctk.CTkLabel(row2b, text="Batch Size:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 5))
        self.batch_size = ctk.CTkSlider(row2b, from_=10, to=200, number_of_steps=19,
                                         width=150, height=18,
                                         fg_color=BG_INPUT,
                                         progress_color=NEON_GREEN,
                                         button_color=NEON_CYAN)
        self.batch_size.set(80)
        self.batch_size.pack(side="left", padx=3)
        self.batch_size_label = ctk.CTkLabel(row2b, text="80", text_color=NEON_CYAN,
                                              font=ctk.CTkFont(size=12, weight="bold"))
        self.batch_size_label.pack(side="left", padx=(0, 20))
        self.batch_size.configure(command=lambda v: self.batch_size_label.configure(text=f"{int(v)}"))

        self.filter_aged = ctk.CTkCheckBox(row2b, text="🔒 Only Aged Accounts (+30 days)",
                                            fg_color=NEON_PURPLE,
                                            hover_color="#6d28d9",
                                            text_color=TEXT_PRIMARY,
                                            font=ctk.CTkFont(size=12))
        self.filter_aged.pack(side="left", padx=15)

        # Row 3: Buttons
        row3 = ctk.CTkFrame(config, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(8, 12))

        self.start_btn = ctk.CTkButton(row3, text="🚀 Start Adding", width=170, height=44,
                                        fg_color=NEON_GREEN, hover_color="#059669",
                                        text_color=BG_DARK,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        command=self._start_add)
        self.start_btn.pack(side="left")

        self.pause_btn = ctk.CTkButton(row3, text="⏸ Pause", width=110, height=44,
                                        fg_color=NEON_YELLOW, hover_color="#d97706",
                                        text_color=BG_DARK,
                                        font=ctk.CTkFont(size=13, weight="bold"),
                                        command=self._toggle_pause, state="disabled")
        self.pause_btn.pack(side="left", padx=8)

        self.stop_btn = ctk.CTkButton(row3, text="⬛ Stop", width=100, height=44,
                                       fg_color=NEON_RED, hover_color="#dc2626",
                                       text_color="#fff",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       command=self._stop_add, state="disabled")
        self.stop_btn.pack(side="left")

        # ── Progress Panel ─────────────────────────────────────
        prog_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        prog_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(prog_frame, text="📈 Progress",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(12, 5))

        self.progress = ctk.CTkProgressBar(prog_frame, width=700, height=22,
                                            fg_color=BG_INPUT,
                                            progress_color=NEON_GREEN)
        self.progress.pack(padx=15, pady=5)
        self.progress.set(0)

        # Stats row
        stats_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=15, pady=(5, 15))

        self.stat_added = self._stat_card(stats_row, "✅ Added", "0", NEON_GREEN)
        self.stat_skipped = self._stat_card(stats_row, "⏭ Skipped", "0", NEON_YELLOW)
        self.stat_failed = self._stat_card(stats_row, "❌ Failed", "0", NEON_RED)
        self.stat_remaining = self._stat_card(stats_row, "📋 Remaining", "0", NEON_CYAN)
        self.stat_accounts = self._stat_card(stats_row, "👤 Accounts", "0", NEON_PURPLE)

        # ── Info Panel ─────────────────────────────────────────
        info = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        info.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(info, text="ℹ️ Anti-Ban Protection Active",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=NEON_GREEN).pack(anchor="w", padx=15, pady=(12, 5))

        protections = [
            "• BATCH ADD: sends up to 80 users per API call (10x faster)",
            "• Round-robin account rotation distributes rate limits",
            "• Random delay between batches prevents detection",
            "• Auto-fallback to single-add on batch errors",
            "• Auto-sleep on FloodWait errors with smart backoff",
            "• Auto-disable accounts after 3 flood errors or PeerFlood",
            "• Aged filter: prioritize accounts with +30 days for higher limits",
            "• Desktop fingerprint: Telegram Desktop 5.12.0 x64 identity",
        ]
        for p in protections:
            ctk.CTkLabel(info, text=p, text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=12),
                         anchor="w").pack(anchor="w", padx=20, pady=1)

    def _stat_card(self, parent, label, value, color):
        card = ctk.CTkFrame(parent, fg_color=BG_INPUT, corner_radius=8,
                            width=140, height=55)
        card.pack(side="left", padx=5, expand=True, fill="x")
        card.pack_propagate(False)

        val_label = ctk.CTkLabel(card, text=value,
                                  font=ctk.CTkFont(size=20, weight="bold"),
                                  text_color=color)
        val_label.pack(pady=(5, 0))
        ctk.CTkLabel(card, text=label, text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=10)).pack()
        return val_label

    def _refresh_sources(self):
        groups = get_source_groups()
        options = ["All scraped users"] + groups
        self.source_menu.configure(values=options)
        self.source_menu.set(options[0])
        # Update account count
        count = self.sm.connected_count()
        self.stat_accounts.configure(text=str(count))

    def _start_add(self):
        # ── Aged filter: only use accounts created 30+ days ago ──
        if self.filter_aged.get():
            all_accounts = get_all_accounts()
            aged_phones = []
            for acc in all_accounts:
                created = acc.get("created_at")
                if created:
                    try:
                        age_days = (datetime.now() - datetime.fromisoformat(created)).days
                        if age_days >= 30:
                            aged_phones.append(acc["phone"])
                    except Exception:
                        pass
            clients = [self.sm.get_client(p) for p in aged_phones if self.sm.get_client(p)]
            if not clients:
                logger.error("No aged accounts (30+ days) connected — uncheck filter or add older accounts")
                return
            logger.info(f"Using {len(clients)} aged account(s) for adding")
        else:
            clients = self.sm.get_connected_clients()

        if not clients:
            logger.error("No connected accounts — go to Accounts tab first")
            return

        target = self.target_entry.get().strip()
        if not target:
            logger.error("Enter a target group link")
            return

        source = self.source_menu.get()
        source_group = None if source == "All scraped users" else source
        users = get_scraped_users(source_group=source_group, status="pending")

        if not users:
            logger.error("No pending users to add")
            return

        self._is_running = True
        self._pause_event = asyncio.Event()
        self._stop_event = asyncio.Event()

        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸ Pause")
        self.stop_btn.configure(state="normal")
        self.progress.set(0)

        self.stat_accounts.configure(text=str(len(clients)))
        self.stat_remaining.configure(text=str(len(users)))

        d_min = int(self.delay_min.get())
        d_max = int(self.delay_max.get())
        if d_max < d_min:
            d_max = d_min + 5

        b_size = int(self.batch_size.get())

        threading.Thread(target=self._adder_thread,
                         args=(clients, target, users, d_min, d_max, b_size),
                         daemon=True).start()

    def _adder_thread(self, clients, target, users, d_min, d_max, batch_size=80):
        """Dispatch add_members to the SM's shared event loop."""
        def on_progress(added, skipped, failed, total):
            self.parent.after(0, lambda: self._update_progress(added, skipped, failed, total))

        try:
            self.sm.run_coro(add_members(
                clients=clients,
                target_group_link=target,
                users=users,
                delay_min=d_min,
                delay_max=d_max,
                batch_size=batch_size,
                progress_callback=on_progress,
                pause_event=self._pause_event,
                stop_event=self._stop_event,
            ), timeout=86400)
        except Exception as e:
            logger.error(f"Adder error: {e}")
        finally:
            self.parent.after(0, self._adder_done)

    def _update_progress(self, added, skipped, failed, total):
        done = added + skipped + failed
        if total > 0:
            self.progress.set(done / total)
        self.stat_added.configure(text=str(added))
        self.stat_skipped.configure(text=str(skipped))
        self.stat_failed.configure(text=str(failed))
        self.stat_remaining.configure(text=str(max(0, total - done)))

    def _adder_done(self):
        self._is_running = False
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled")
        self.stop_btn.configure(state="disabled")
        self.progress.set(1.0)

    def _toggle_pause(self):
        if self._pause_event is None:
            return
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.pause_btn.configure(text="⏸ Pause", fg_color=NEON_YELLOW)
            logger.info("Adder resumed")
        else:
            self._pause_event.set()
            self.pause_btn.configure(text="▶ Resume", fg_color=NEON_GREEN)
            logger.info("Adder paused")

    def _stop_add(self):
        if self._stop_event:
            self._stop_event.set()
        if self._pause_event:
            self._pause_event.clear()
        logger.warning("Stopping adder...")
