"""
CyberTG – Settings Tab
App configuration: API credentials, delays, theme, build to exe.
"""
import os
import sys
import subprocess
import threading
import customtkinter as ctk
from core.db import get_setting, set_setting
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


class SettingsTab:
    """Application settings interface."""

    def __init__(self, parent: ctk.CTkFrame):
        self.parent = parent
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        self.parent.configure(fg_color=BG_DARK)

        # ── API Configuration ──────────────────────────────────
        api_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        api_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(api_frame, text="🔑 Default API Credentials",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 8))

        ctk.CTkLabel(api_frame, text="These will be pre-filled when adding new accounts",
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=15, pady=(0, 5))

        row1 = ctk.CTkFrame(api_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(row1, text="API ID:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12), width=80).pack(side="left")
        self.api_id_entry = ctk.CTkEntry(row1, width=200, height=38,
                                          fg_color=BG_INPUT, border_color=BORDER,
                                          text_color=TEXT_PRIMARY,
                                          placeholder_text="Get from my.telegram.org")
        self.api_id_entry.pack(side="left", padx=5)

        ctk.CTkLabel(row1, text="API Hash:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12), width=80).pack(side="left", padx=(20, 0))
        self.api_hash_entry = ctk.CTkEntry(row1, width=300, height=38,
                                            fg_color=BG_INPUT, border_color=BORDER,
                                            text_color=TEXT_PRIMARY,
                                            placeholder_text="Get from my.telegram.org")
        self.api_hash_entry.pack(side="left", padx=5)

        ctk.CTkButton(api_frame, text="💾 Save API Credentials", width=200, height=38,
                      fg_color=NEON_PURPLE, hover_color="#6d28d9",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save_api).pack(anchor="w", padx=15, pady=(5, 15))

        # ── Delay Configuration ────────────────────────────────
        delay_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        delay_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(delay_frame, text="⏱ Default Delay Configuration",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 8))

        row2 = ctk.CTkFrame(delay_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=3)

        ctk.CTkLabel(row2, text="Min Delay (s):", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.min_delay_entry = ctk.CTkEntry(row2, width=80, height=38,
                                             fg_color=BG_INPUT, border_color=BORDER,
                                             text_color=TEXT_PRIMARY)
        self.min_delay_entry.pack(side="left", padx=5)

        ctk.CTkLabel(row2, text="Max Delay (s):", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(20, 0))
        self.max_delay_entry = ctk.CTkEntry(row2, width=80, height=38,
                                             fg_color=BG_INPUT, border_color=BORDER,
                                             text_color=TEXT_PRIMARY)
        self.max_delay_entry.pack(side="left", padx=5)

        ctk.CTkButton(delay_frame, text="💾 Save Delays", width=160, height=38,
                      fg_color=NEON_PURPLE, hover_color="#6d28d9",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._save_delays).pack(anchor="w", padx=15, pady=(5, 15))

        # ── Theme ──────────────────────────────────────────────
        theme_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        theme_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(theme_frame, text="🎨 Appearance",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 8))

        theme_row = ctk.CTkFrame(theme_frame, fg_color="transparent")
        theme_row.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkLabel(theme_row, text="Theme:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.theme_menu = ctk.CTkOptionMenu(theme_row, values=["Dark", "Light", "System"],
                                             width=140, height=38,
                                             fg_color=BG_INPUT, button_color=NEON_PURPLE,
                                             text_color=TEXT_PRIMARY,
                                             command=self._change_theme)
        self.theme_menu.set("Dark")
        self.theme_menu.pack(side="left", padx=10)

        # ── Build to EXE ──────────────────────────────────────
        build_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        build_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(build_frame, text="📦 Compile to Executable",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 5))

        ctk.CTkLabel(build_frame, text="Creates a standalone .exe using PyInstaller",
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=15, pady=(0, 5))

        self.build_btn = ctk.CTkButton(build_frame, text="🔨 Build .exe", width=180, height=42,
                                        fg_color=NEON_GREEN, hover_color="#059669",
                                        text_color=BG_DARK,
                                        font=ctk.CTkFont(size=14, weight="bold"),
                                        command=self._build_exe)
        self.build_btn.pack(anchor="w", padx=15, pady=(5, 10))

        self.build_status = ctk.CTkLabel(build_frame, text="",
                                          font=ctk.CTkFont(size=12),
                                          text_color=TEXT_MUTED)
        self.build_status.pack(anchor="w", padx=15, pady=(0, 15))

        # ── About ─────────────────────────────────────────────
        about_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        about_frame.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(about_frame, text="⚡ CyberTG Mass Scraper & Adder 2026",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 3))
        ctk.CTkLabel(about_frame, text="Version 2.0 — Professional Telegram Automation Tool",
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=15, pady=(0, 3))
        ctk.CTkLabel(about_frame, text="Built with Telethon + CustomTkinter + SQLite",
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=15, pady=(0, 15))

    def _load_settings(self):
        api_id = get_setting("default_api_id", "")
        api_hash = get_setting("default_api_hash", "")
        min_delay = get_setting("default_min_delay", "8")
        max_delay = get_setting("default_max_delay", "25")

        if api_id:
            self.api_id_entry.insert(0, api_id)
        if api_hash:
            self.api_hash_entry.insert(0, api_hash)
        self.min_delay_entry.insert(0, min_delay)
        self.max_delay_entry.insert(0, max_delay)

    def _save_api(self):
        set_setting("default_api_id", self.api_id_entry.get().strip())
        set_setting("default_api_hash", self.api_hash_entry.get().strip())
        logger.success("API credentials saved")

    def _save_delays(self):
        set_setting("default_min_delay", self.min_delay_entry.get().strip())
        set_setting("default_max_delay", self.max_delay_entry.get().strip())
        logger.success("Default delays saved")

    def _change_theme(self, value):
        ctk.set_appearance_mode(value.lower())
        set_setting("theme", value.lower())
        logger.info(f"Theme changed to {value}")

    def _build_exe(self):
        self.build_btn.configure(state="disabled")
        self.build_status.configure(text="🔄 Building... this may take a few minutes",
                                     text_color=NEON_YELLOW)
        threading.Thread(target=self._build_thread, daemon=True).start()

    def _build_thread(self):
        try:
            project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            build_script = os.path.join(project_dir, "build.py")

            result = subprocess.run(
                [sys.executable, build_script],
                capture_output=True, text=True, cwd=project_dir
            )

            if result.returncode == 0:
                self.parent.after(0, lambda: self.build_status.configure(
                    text="✅ Build succeeded! Check dist/ folder",
                    text_color=NEON_GREEN))
                logger.success("EXE build completed successfully")
            else:
                self.parent.after(0, lambda: self.build_status.configure(
                    text=f"❌ Build failed: {result.stderr[:100]}",
                    text_color=NEON_RED))
                logger.error(f"Build failed: {result.stderr[:200]}")

        except Exception as e:
            self.parent.after(0, lambda: self.build_status.configure(
                text=f"❌ Error: {str(e)[:80]}",
                text_color=NEON_RED))
            logger.error(f"Build error: {e}")
        finally:
            self.parent.after(0, lambda: self.build_btn.configure(state="normal"))
