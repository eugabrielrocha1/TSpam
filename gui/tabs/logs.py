"""
CyberTG – Logs Tab
Real-time log viewer with colored entries and export options.
"""
import os
import customtkinter as ctk
from tkinter import filedialog
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

LEVEL_COLORS = {
    "INFO":    NEON_CYAN,
    "SUCCESS": NEON_GREEN,
    "WARNING": NEON_YELLOW,
    "ERROR":   NEON_RED,
}


class LogsTab:
    """Real-time log viewer with export options."""

    def __init__(self, parent: ctk.CTkFrame):
        self.parent = parent
        self.auto_scroll = True
        self._build_ui()

    def _build_ui(self):
        self.parent.configure(fg_color=BG_DARK)

        # ── Toolbar ────────────────────────────────────────────
        toolbar = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=10, height=50)
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        toolbar.pack_propagate(False)

        ctk.CTkLabel(toolbar, text="📋 Real-Time Logs",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(side="left", padx=15)

        # Export buttons
        ctk.CTkButton(toolbar, text="📄 Export TXT", width=110, height=32,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      text_color=NEON_CYAN,
                      font=ctk.CTkFont(size=12),
                      command=self._export_txt).pack(side="right", padx=5)

        ctk.CTkButton(toolbar, text="📊 Export CSV", width=110, height=32,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      text_color=NEON_GREEN,
                      font=ctk.CTkFont(size=12),
                      command=self._export_csv).pack(side="right", padx=5)

        ctk.CTkButton(toolbar, text="🗑️ Clear", width=80, height=32,
                      fg_color=BG_INPUT, hover_color=NEON_RED,
                      text_color=NEON_RED,
                      font=ctk.CTkFont(size=12),
                      command=self._clear_logs).pack(side="right", padx=5)

        self.auto_scroll_btn = ctk.CTkButton(
            toolbar, text="⬇ Auto-scroll: ON", width=140, height=32,
            fg_color=NEON_PURPLE, hover_color="#6d28d9",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._toggle_autoscroll
        )
        self.auto_scroll_btn.pack(side="right", padx=5)

        # ── Log Text Area ─────────────────────────────────────
        self.log_text = ctk.CTkTextbox(
            self.parent,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(family="Consolas", size=12),
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            wrap="word",
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=5)

        # Configure color tags
        for level, color in LEVEL_COLORS.items():
            self.log_text._textbox.tag_configure(level, foreground=color)
        self.log_text._textbox.tag_configure("TIMESTAMP", foreground=TEXT_MUTED)

    def poll_logs(self):
        """Called periodically by the main app to drain log entries."""
        entries = logger.drain()
        if not entries:
            return

        self.log_text.configure(state="normal")
        for entry in entries:
            ts_part = f'[{entry["timestamp"]}] '
            level_part = f'[{entry["level"]}] '
            msg_part = entry["message"] + "\n"

            self.log_text._textbox.insert("end", ts_part, "TIMESTAMP")
            self.log_text._textbox.insert("end", level_part, entry["level"])
            self.log_text._textbox.insert("end", msg_part, entry["level"])

        self.log_text.configure(state="disabled")

        if self.auto_scroll:
            self.log_text._textbox.see("end")

    def _toggle_autoscroll(self):
        self.auto_scroll = not self.auto_scroll
        state = "ON" if self.auto_scroll else "OFF"
        self.auto_scroll_btn.configure(text=f"⬇ Auto-scroll: {state}")

    def _clear_logs(self):
        self.log_text.configure(state="normal")
        self.log_text._textbox.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        logger.clear()

    def _export_txt(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            title="Export Logs as TXT"
        )
        if path:
            logger.export_txt(path)
            logger.info(f"Logs exported to {path}")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export Logs as CSV"
        )
        if path:
            logger.export_csv(path)
            logger.info(f"Logs exported to {path}")
