"""
CyberTG – Main Application Window
Dark cyber-themed CustomTkinter interface with tabbed layout.
"""
import customtkinter as ctk
from gui.tabs.accounts import AccountsTab
from gui.tabs.scraper import ScraperTab
from gui.tabs.adder import AdderTab
from gui.tabs.logs import LogsTab
from gui.tabs.settings import SettingsTab
from core.session_manager import SessionManager
from core.logger import logger

# ─── Color Palette ──────────────────────────────────────────────────
BG_DARK       = "#0a0e27"
BG_CARD       = "#111638"
BG_INPUT      = "#161b42"
NEON_CYAN     = "#00d4ff"
NEON_PURPLE   = "#7c3aed"
NEON_GREEN    = "#10b981"
NEON_RED      = "#ef4444"
NEON_YELLOW   = "#f59e0b"
TEXT_PRIMARY  = "#e2e8f0"
TEXT_MUTED    = "#64748b"
BORDER_COLOR  = "#1e2550"


class CyberTGApp(ctk.CTk):
    """Main Application Window."""

    def __init__(self):
        super().__init__()

        # ── Window config ──────────────────────────────────────
        self.title("CyberTG Mass Scraper & Adder 2026")
        self.geometry("1200x750")
        self.minsize(1000, 650)
        self.configure(fg_color=BG_DARK)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # ── Session manager (shared) ──────────────────────────
        self.session_manager = SessionManager()

        # ── Header bar ─────────────────────────────────────────
        self._build_header()

        # ── Tab view ───────────────────────────────────────────
        self._build_tabs()

        # ── Status bar ─────────────────────────────────────────
        self._build_status_bar()

        # ── Periodic updates ───────────────────────────────────
        self._update_status()

        # ── Auto-reconnect saved accounts (on shared loop) ────
        import threading
        threading.Thread(target=self._auto_reconnect, daemon=True).start()

    # ────────────────────── Header ──────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_CARD, height=60, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)
        header.pack_propagate(False)

        # Logo / Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            title_frame,
            text="⚡ CyberTG",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=NEON_CYAN
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="  Mass Scraper & Adder 2026",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=TEXT_MUTED
        ).pack(side="left", padx=(5, 0))

        # Version badge
        badge = ctk.CTkLabel(
            header,
            text="v2.0",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=BG_DARK,
            fg_color=NEON_PURPLE,
            corner_radius=8,
            width=45,
            height=24
        )
        badge.pack(side="right", padx=20)

    # ────────────────────── Tabs ────────────────────────────────
    def _build_tabs(self):
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=BG_DARK,
            segmented_button_fg_color=BG_CARD,
            segmented_button_selected_color=NEON_PURPLE,
            segmented_button_selected_hover_color="#6d28d9",
            segmented_button_unselected_color=BG_CARD,
            segmented_button_unselected_hover_color=BG_INPUT,
            text_color=TEXT_PRIMARY,
            corner_radius=10,
        )
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(10, 5))

        # Create tabs
        tab_accounts = self.tabview.add("  📱 Accounts  ")
        tab_scraper  = self.tabview.add("  🔍 Scraper  ")
        tab_adder    = self.tabview.add("  ➕ Adder  ")
        tab_logs     = self.tabview.add("  📋 Logs  ")
        tab_settings = self.tabview.add("  ⚙️ Settings  ")

        # Initialize tab contents
        self.accounts_tab = AccountsTab(tab_accounts, self.session_manager)
        self.scraper_tab  = ScraperTab(tab_scraper, self.session_manager)
        self.adder_tab    = AdderTab(tab_adder, self.session_manager)
        self.logs_tab     = LogsTab(tab_logs)
        self.settings_tab = SettingsTab(tab_settings)

    # ────────────────────── Status Bar ──────────────────────────
    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, fg_color=BG_CARD, height=32, corner_radius=0)
        self.status_bar.pack(fill="x", padx=0, pady=0, side="bottom")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar,
            text="● 0 accounts connected",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED
        )
        self.status_label.pack(side="left", padx=15)

        self.status_right = ctk.CTkLabel(
            self.status_bar,
            text="CyberTG 2026 — Ready",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        )
        self.status_right.pack(side="right", padx=15)

    # ────────────────────── Periodic Updates ────────────────────
    def _update_status(self):
        count = self.session_manager.connected_count()
        color = NEON_GREEN if count > 0 else NEON_RED
        self.status_label.configure(
            text=f"● {count} account(s) connected",
            text_color=color
        )
        # Drain logs to logs tab
        self.logs_tab.poll_logs()
        self.after(500, self._update_status)

    def _auto_reconnect(self):
        """Reconnect all saved accounts on startup using SM's shared loop."""
        try:
            self.session_manager.run_coro(self.session_manager.reconnect_all())
        except Exception as e:
            logger.error(f"Auto-reconnect failed: {e}")
