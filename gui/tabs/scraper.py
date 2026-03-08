"""
CyberTG – Scraper Tab
Scrape group/channel members with filters and progress.
All Telethon operations dispatched to the SessionManager's shared loop.
"""
import threading
import customtkinter as ctk
from core.session_manager import SessionManager
from core.scraper import scrape_group
from core.db import get_scraped_count, get_all_scraped_users, clear_scraped_users
from core.logger import logger

BG_DARK      = "#0a0e27"
BG_CARD      = "#111638"
BG_INPUT     = "#161b42"
NEON_CYAN    = "#00d4ff"
NEON_PURPLE  = "#7c3aed"
NEON_GREEN   = "#10b981"
NEON_RED     = "#ef4444"
TEXT_PRIMARY = "#e2e8f0"
TEXT_MUTED   = "#64748b"
BORDER       = "#1e2550"


class ScraperTab:
    """Scraper interface — scrape members from a group/channel."""

    def __init__(self, parent: ctk.CTkFrame, session_manager: SessionManager):
        self.parent = parent
        self.sm = session_manager
        self._is_scraping = False
        self._stop_flag = False
        self._build_ui()

    def _build_ui(self):
        self.parent.configure(fg_color=BG_DARK)

        # ── Config Panel ───────────────────────────────────────
        config = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        config.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(config, text="🔍 Scraper Configuration",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 8))

        # Row: Group link + Account selector
        row1 = ctk.CTkFrame(config, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(row1, text="Group/Channel Link:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        self.group_entry = ctk.CTkEntry(row1, placeholder_text="https://t.me/groupname or t.me/+invite",
                                         width=400, height=38,
                                         fg_color=BG_INPUT, border_color=BORDER,
                                         text_color=TEXT_PRIMARY)
        self.group_entry.pack(side="left", padx=5)

        ctk.CTkLabel(row1, text="Account:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(15, 5))
        self.account_menu = ctk.CTkOptionMenu(row1, values=["— Select —"],
                                               width=180, height=38,
                                               fg_color=BG_INPUT, button_color=NEON_PURPLE,
                                               text_color=TEXT_PRIMARY,
                                               command=lambda _: None)
        self.account_menu.pack(side="left", padx=5)

        ctk.CTkButton(row1, text="🔄", width=38, height=38,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      command=self._refresh_accounts).pack(side="left", padx=2)

        # Row: Filters
        row2 = ctk.CTkFrame(config, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(8, 3))

        ctk.CTkLabel(row2, text="Filters:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 10))

        self.filter_username = ctk.CTkCheckBox(row2, text="Has Username",
                                                fg_color=NEON_PURPLE,
                                                hover_color="#6d28d9",
                                                text_color=TEXT_PRIMARY)
        self.filter_username.pack(side="left", padx=8)
        self.filter_username.select()

        self.filter_not_bot = ctk.CTkCheckBox(row2, text="Not Bot",
                                               fg_color=NEON_PURPLE,
                                               hover_color="#6d28d9",
                                               text_color=TEXT_PRIMARY)
        self.filter_not_bot.pack(side="left", padx=8)
        self.filter_not_bot.select()

        self.filter_photo = ctk.CTkCheckBox(row2, text="Has Photo",
                                             fg_color=NEON_PURPLE,
                                             hover_color="#6d28d9",
                                             text_color=TEXT_PRIMARY)
        self.filter_photo.pack(side="left", padx=8)

        self.filter_last_seen = ctk.CTkCheckBox(row2, text="Last Seen < 30 days",
                                                  fg_color=NEON_PURPLE,
                                                  hover_color="#6d28d9",
                                                  text_color=TEXT_PRIMARY)
        self.filter_last_seen.pack(side="left", padx=8)
        self.filter_last_seen.select()

        # Buttons + Progress
        row3 = ctk.CTkFrame(config, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(8, 12))

        self.start_btn = ctk.CTkButton(row3, text="🚀 Start Scraping", width=180, height=42,
                                        fg_color=NEON_GREEN, hover_color="#059669",
                                        text_color=BG_DARK,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        command=self._start_scrape)
        self.start_btn.pack(side="left")

        self.stop_btn = ctk.CTkButton(row3, text="⬛ Stop", width=100, height=42,
                                       fg_color=NEON_RED, hover_color="#dc2626",
                                       text_color="#fff",
                                       font=ctk.CTkFont(size=13, weight="bold"),
                                       command=self._stop_scrape, state="disabled")
        self.stop_btn.pack(side="left", padx=10)

        self.progress = ctk.CTkProgressBar(row3, width=300, height=16,
                                            fg_color=BG_INPUT,
                                            progress_color=NEON_CYAN)
        self.progress.pack(side="left", padx=15)
        self.progress.set(0)

        self.progress_label = ctk.CTkLabel(row3, text="0 members fetched | 0 matched",
                                            text_color=TEXT_MUTED,
                                            font=ctk.CTkFont(size=12))
        self.progress_label.pack(side="left", padx=5)

        # ── Results Table ──────────────────────────────────────
        results_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        results_frame.pack(fill="both", expand=True, padx=10, pady=5)

        top_bar = ctk.CTkFrame(results_frame, fg_color="transparent")
        top_bar.pack(fill="x", padx=15, pady=(10, 5))

        self.results_title = ctk.CTkLabel(top_bar, text=f"📊 Scraped Users ({get_scraped_count()})",
                                           font=ctk.CTkFont(size=15, weight="bold"),
                                           text_color=TEXT_PRIMARY)
        self.results_title.pack(side="left")

        ctk.CTkButton(top_bar, text="🗑️ Clear All", width=100, height=30,
                      fg_color=BG_INPUT, hover_color=NEON_RED,
                      text_color=NEON_RED, font=ctk.CTkFont(size=11),
                      command=self._clear_all).pack(side="right")

        ctk.CTkButton(top_bar, text="🔄 Refresh", width=90, height=30,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      text_color=NEON_CYAN, font=ctk.CTkFont(size=11),
                      command=self._refresh_results).pack(side="right", padx=5)

        # Table headers
        hdr = ctk.CTkFrame(results_frame, fg_color=BG_INPUT, corner_radius=6, height=32)
        hdr.pack(fill="x", padx=12, pady=(0, 2))
        hdr.pack_propagate(False)
        for text, w in [("User ID", 110), ("Username", 140), ("Name", 180),
                        ("Photo", 60), ("Last Seen", 120), ("Source", 160)]:
            ctk.CTkLabel(hdr, text=text, width=w, text_color=NEON_CYAN,
                         font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)

        self.results_scroll = ctk.CTkScrollableFrame(results_frame, fg_color="transparent")
        self.results_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._refresh_results()
        self._refresh_accounts()
        self._auto_refresh_accounts()

    def _auto_refresh_accounts(self):
        """Periodically refresh the account dropdown every 2 seconds."""
        self._refresh_accounts()
        self.parent.after(2000, self._auto_refresh_accounts)

    def _refresh_accounts(self):
        phones = self.sm.get_connected_phones()
        if phones:
            self.account_menu.configure(values=phones)
            self.account_menu.set(phones[0])
        else:
            self.account_menu.configure(values=["— No accounts —"])
            self.account_menu.set("— No accounts —")

    def _start_scrape(self):
        phone = self.account_menu.get()
        if not phone or phone.startswith("—"):
            logger.error("Select a connected account first")
            return

        client = self.sm.get_client(phone)
        if not client:
            logger.error(f"Account {phone} is not connected")
            return

        group = self.group_entry.get().strip()
        if not group:
            logger.error("Enter a group/channel link")
            return

        self._is_scraping = True
        self._stop_flag = False
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.set(0)

        filters = {
            "filter_has_username": bool(self.filter_username.get()),
            "filter_not_bot": bool(self.filter_not_bot.get()),
            "filter_has_photo": bool(self.filter_photo.get()),
            "filter_last_seen_days": 30 if self.filter_last_seen.get() else 0,
        }

        threading.Thread(target=self._scrape_thread, args=(client, group, filters),
                         daemon=True).start()

    def _scrape_thread(self, client, group, filters):
        """Dispatch scrape_group to the SM's shared event loop."""
        def on_progress(fetched, matched):
            self.parent.after(0, lambda: self._update_progress(fetched, matched))

        try:
            self.sm.run_coro(scrape_group(
                client, group,
                progress_callback=on_progress,
                stop_event=None,
                **filters
            ), timeout=600)
        except Exception as e:
            logger.error(f"Scrape error: {e}")
        finally:
            self.parent.after(0, self._scrape_done)

    def _update_progress(self, fetched, matched):
        self.progress_label.configure(text=f"{fetched} members fetched | {matched} matched")
        if fetched > 0:
            self.progress.set(min(0.95, fetched / max(fetched + 50, 200)))

    def _scrape_done(self):
        self._is_scraping = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.progress.set(1.0)
        self._refresh_results()

    def _stop_scrape(self):
        self._stop_flag = True
        logger.warning("Stopping scrape...")

    def _refresh_results(self):
        for w in self.results_scroll.winfo_children():
            w.destroy()

        users = get_all_scraped_users()
        self.results_title.configure(text=f"📊 Scraped Users ({len(users)})")

        for u in users[:500]:  # Show max 500 rows
            row = ctk.CTkFrame(self.results_scroll, fg_color=BG_INPUT,
                               corner_radius=6, height=32)
            row.pack(fill="x", pady=1)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=str(u["user_id"]), width=110,
                         text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f'@{u["username"]}' if u["username"] else "—", width=140,
                         text_color=NEON_CYAN, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            name = f'{u["first_name"]} {u["last_name"]}'.strip() or "—"
            ctk.CTkLabel(row, text=name, width=180,
                         text_color=TEXT_PRIMARY, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text="✓" if u["has_photo"] else "✗", width=60,
                         text_color=NEON_GREEN if u["has_photo"] else TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=u["last_seen"], width=120,
                         text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=u["source_group"][:25], width=160,
                         text_color=TEXT_MUTED, font=ctk.CTkFont(size=11)).pack(side="left", padx=4)

    def _clear_all(self):
        clear_scraped_users()
        self._refresh_results()
        logger.info("All scraped users cleared")
