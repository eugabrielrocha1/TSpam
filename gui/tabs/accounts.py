"""
CyberTG – Accounts Tab
Manage Telegram accounts: add, login, proxy config, delete.
"""
import threading
import customtkinter as ctk
from core.session_manager import SessionManager
from core.db import add_account, get_all_accounts, delete_account
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


class CodeDialog(ctk.CTkToplevel):
    """Dialog for entering verification code / 2FA password."""
    def __init__(self, parent, phone):
        super().__init__(parent)
        self.title(f"Verification — {phone}")
        self.geometry("400x260")
        self.configure(fg_color=BG_DARK)
        self.resizable(False, False)
        self.grab_set()

        self.result_code = None
        self.result_password = None

        ctk.CTkLabel(self, text=f"📱 Code sent to {phone}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=NEON_CYAN).pack(pady=(20, 10))

        self.code_entry = ctk.CTkEntry(self, placeholder_text="Enter code",
                                        width=250, height=40,
                                        fg_color=BG_INPUT, border_color=BORDER,
                                        text_color=TEXT_PRIMARY)
        self.code_entry.pack(pady=5)

        self.pass_entry = ctk.CTkEntry(self, placeholder_text="2FA password (if needed)",
                                        width=250, height=40, show="•",
                                        fg_color=BG_INPUT, border_color=BORDER,
                                        text_color=TEXT_PRIMARY)
        self.pass_entry.pack(pady=5)

        ctk.CTkButton(self, text="✓ Confirm", width=200, height=40,
                      fg_color=NEON_GREEN, hover_color="#059669",
                      text_color=BG_DARK, font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._confirm).pack(pady=15)

    def _confirm(self):
        self.result_code = self.code_entry.get().strip()
        self.result_password = self.pass_entry.get().strip() or None
        self.destroy()


class AccountsTab:
    """Accounts management interface."""

    def __init__(self, parent: ctk.CTkFrame, session_manager: SessionManager):
        self.parent = parent
        self.sm = session_manager
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        self.parent.configure(fg_color=BG_DARK)

        # ── Top: Add Account Form ─────────────────────────────
        form_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        form_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(form_frame, text="➕ Add New Account",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=NEON_CYAN).pack(anchor="w", padx=15, pady=(12, 8))

        # Row 1: Phone, API ID, API Hash
        row1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=3)

        self.phone_entry = self._labeled_entry(row1, "Phone (intl)", "+5511999999999", 180)
        self.api_id_entry = self._labeled_entry(row1, "API ID", "12345678", 120)
        self.api_hash_entry = self._labeled_entry(row1, "API Hash", "abcdef1234567890", 220)

        # Row 2: Proxy
        row2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=3)

        self.proxy_type = ctk.CTkOptionMenu(row2, values=["", "SOCKS5", "HTTP"],
                                             width=100, height=35,
                                             fg_color=BG_INPUT, button_color=NEON_PURPLE,
                                             text_color=TEXT_PRIMARY)
        self.proxy_type.set("")
        ctk.CTkLabel(row2, text="Proxy", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 2))
        self.proxy_type.pack(side="left", padx=3)

        self.proxy_addr = self._labeled_entry(row2, "Address", "1.2.3.4", 130)
        self.proxy_port = self._labeled_entry(row2, "Port", "1080", 70)
        self.proxy_user = self._labeled_entry(row2, "User", "", 90)
        self.proxy_pass = self._labeled_entry(row2, "Pass", "", 90)

        # Button
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(5, 12))

        ctk.CTkButton(btn_frame, text="🔐 Add & Login", width=180, height=40,
                      fg_color=NEON_PURPLE, hover_color="#6d28d9",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._add_account).pack(side="left")

        ctk.CTkButton(btn_frame, text="🔄 Reconnect All", width=160, height=40,
                      fg_color=BG_INPUT, hover_color=BORDER,
                      border_width=1, border_color=NEON_CYAN,
                      text_color=NEON_CYAN,
                      font=ctk.CTkFont(size=13),
                      command=self._reconnect_all).pack(side="left", padx=10)

        # ── Bottom: Accounts Table ────────────────────────────
        table_frame = ctk.CTkFrame(self.parent, fg_color=BG_CARD, corner_radius=12)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        ctk.CTkLabel(table_frame, text="📋 Saved Accounts",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w", padx=15, pady=(12, 5))

        # Headers
        hdr = ctk.CTkFrame(table_frame, fg_color=BG_INPUT, corner_radius=6, height=35)
        hdr.pack(fill="x", padx=12, pady=(0, 2))
        hdr.pack_propagate(False)
        for text, w in [("Phone", 150), ("API ID", 100), ("Proxy", 160),
                        ("Status", 110), ("Actions", 150)]:
            ctk.CTkLabel(hdr, text=text, width=w, text_color=NEON_CYAN,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)

        self.table_scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent")
        self.table_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    def _labeled_entry(self, parent, label, placeholder, width):
        ctk.CTkLabel(parent, text=label, text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(5, 2))
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder,
                              width=width, height=35,
                              fg_color=BG_INPUT, border_color=BORDER,
                              text_color=TEXT_PRIMARY)
        entry.pack(side="left", padx=3)
        return entry

    def _refresh_table(self):
        for widget in self.table_scroll.winfo_children():
            widget.destroy()

        accounts = get_all_accounts()
        if not accounts:
            ctk.CTkLabel(self.table_scroll, text="No accounts added yet",
                         text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=13)).pack(pady=30)
            return

        for acc in accounts:
            row = ctk.CTkFrame(self.table_scroll, fg_color=BG_INPUT,
                               corner_radius=8, height=40)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            ctk.CTkLabel(row, text=acc["phone"], width=150,
                         text_color=TEXT_PRIMARY,
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=5)

            ctk.CTkLabel(row, text=str(acc["api_id"])[:10], width=100,
                         text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=5)

            proxy_str = f'{acc["proxy_type"]}:{acc["proxy_addr"]}' if acc["proxy_type"] else "None"
            ctk.CTkLabel(row, text=proxy_str, width=160,
                         text_color=TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left", padx=5)

            status = acc["status"]
            s_color = NEON_GREEN if status == "connected" else (NEON_RED if status in ("banned", "error") else TEXT_MUTED)
            ctk.CTkLabel(row, text=f"● {status}", width=110,
                         text_color=s_color,
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)

            # Actions
            act_frame = ctk.CTkFrame(row, fg_color="transparent")
            act_frame.pack(side="left", padx=5)

            phone = acc["phone"]
            ctk.CTkButton(act_frame, text="🔄", width=35, height=28,
                          fg_color=BG_CARD, hover_color=BORDER,
                          command=lambda p=phone: self._reconnect_single(p)).pack(side="left", padx=2)
            ctk.CTkButton(act_frame, text="🗑️", width=35, height=28,
                          fg_color=BG_CARD, hover_color=NEON_RED,
                          command=lambda p=phone: self._delete_account(p)).pack(side="left", padx=2)

    def _add_account(self):
        phone = self.phone_entry.get().strip()
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()

        if not phone or not api_id or not api_hash:
            logger.error("Phone, API ID, and API Hash are required")
            return

        proxy_t = self.proxy_type.get()
        proxy_a = self.proxy_addr.get().strip()
        proxy_p = self.proxy_port.get().strip()
        proxy_u = self.proxy_user.get().strip()
        proxy_pw = self.proxy_pass.get().strip()

        add_account(phone, api_id, api_hash, proxy_t, proxy_a,
                    int(proxy_p) if proxy_p else 0, proxy_u, proxy_pw)
        logger.info(f"Account {phone} saved to database")
        self._refresh_table()

        # Start login in background thread but using SM's shared loop
        acc = {
            "phone": phone, "api_id": api_id, "api_hash": api_hash,
            "proxy_type": proxy_t, "proxy_addr": proxy_a,
            "proxy_port": int(proxy_p) if proxy_p else 0,
            "proxy_user": proxy_u, "proxy_pass": proxy_pw
        }
        threading.Thread(target=self._login_thread, args=(acc,), daemon=True).start()

    def _login_thread(self, acc):
        """Run login on the SM's shared loop (NOT a new loop)."""
        try:
            client, code_hash = self.sm.run_coro(
                self.sm.login_send_code(acc)
            )
            if code_hash is None:
                # Already authorized
                self.parent.after(100, self._refresh_table)
                return

            # Need code — show dialog on main thread
            self.parent.after(0, lambda: self._show_code_dialog(client, acc["phone"], code_hash))
        except Exception as e:
            logger.error(f"Login failed: {e}")
            self.parent.after(100, self._refresh_table)

    def _show_code_dialog(self, client, phone, code_hash):
        dialog = CodeDialog(self.parent, phone)
        self.parent.wait_window(dialog)

        code = dialog.result_code
        password = dialog.result_password
        if not code:
            logger.warning(f"Login cancelled for {phone}")
            return

        threading.Thread(target=self._enter_code_thread,
                         args=(client, phone, code, code_hash, password),
                         daemon=True).start()

    def _enter_code_thread(self, client, phone, code, code_hash, password):
        """Enter code on the SM's shared loop."""
        try:
            self.sm.run_coro(
                self.sm.login_enter_code(client, phone, code, code_hash, password)
            )
        except Exception as e:
            logger.error(f"Code verification failed: {e}")
        self.parent.after(100, self._refresh_table)

    def _reconnect_single(self, phone):
        accounts = get_all_accounts()
        acc = next((a for a in accounts if a["phone"] == phone), None)
        if not acc:
            return
        threading.Thread(target=self._reconnect_thread, args=(acc,), daemon=True).start()

    def _reconnect_thread(self, acc):
        """Reconnect on the SM's shared loop."""
        try:
            self.sm.run_coro(self.sm.reconnect_account(acc))
        except Exception as e:
            logger.error(f"Reconnect failed: {e}")
        self.parent.after(100, self._refresh_table)

    def _reconnect_all(self):
        threading.Thread(target=self._reconnect_all_thread, daemon=True).start()

    def _reconnect_all_thread(self):
        """Reconnect all on the SM's shared loop."""
        try:
            self.sm.run_coro(self.sm.reconnect_all())
        except Exception as e:
            logger.error(f"Reconnect all failed: {e}")
        self.parent.after(100, self._refresh_table)

    def _delete_account(self, phone):
        delete_account(phone)
        try:
            self.sm.run_coro(self.sm.disconnect_account(phone))
        except Exception:
            pass
        logger.info(f"Deleted account {phone}")
        self._refresh_table()
