# ⚡ CyberTG Mass Scraper & Adder 2026

Professional Telegram automation desktop tool built with **Telethon**, **CustomTkinter**, and **SQLite**.

---

## 🚀 Features

- **Multi-Account Sessions** — Login with multiple phone numbers, save sessions
- **Proxy Support** — SOCKS5 and HTTP proxy per account
- **Smart Scraper** — Scrape group/channel members with filters (username, not-bot, last-seen, photo)
- **Bulk Adder** — Add users in batch with random delay (8-25s), pause/resume, progress bar
- **Anti-Ban Protection** — FloodWait handling, PeerFlood auto-switch, account round-robin
- **Real-Time Logs** — Colored log viewer with CSV/TXT export
- **Compile to `.exe`** — Built-in PyInstaller compilation button

---

## 📦 Installation

### Prerequisites
- **Python 3.10+** (recommended: 3.11 or 3.12)
- **Telegram API credentials** from [my.telegram.org](https://my.telegram.org)

### Steps

```bash
# 1. Clone or download the project folder

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python main.py
```

---

## 🗂️ Project Structure

```
TSpamV2/
├── main.py                  # Entry point
├── build.py                 # PyInstaller build script
├── requirements.txt         # Dependencies
├── core/
│   ├── db.py                # SQLite database layer
│   ├── session_manager.py   # Multi-session Telethon manager
│   ├── scraper.py           # Group member scraper
│   ├── adder.py             # Bulk member adder
│   └── logger.py            # Thread-safe logger
├── gui/
│   ├── app.py               # Main window + theme
│   └── tabs/
│       ├── accounts.py      # Account management tab
│       ├── scraper.py       # Scraper tab
│       ├── adder.py         # Adder tab
│       ├── logs.py          # Logs tab
│       └── settings.py      # Settings tab
└── sessions/                # Auto-created .session files
```

---

## 🎯 Usage Guide

### 1. Setup API Credentials
1. Go to **Settings** tab
2. Enter your **API ID** and **API Hash** from [my.telegram.org](https://my.telegram.org)
3. Click **Save API Credentials**

### 2. Add Accounts
1. Go to **Accounts** tab
2. Enter phone number (international format, e.g. `+5511999999999`)
3. Enter API ID and API Hash
4. Optionally configure proxy (SOCKS5/HTTP)
5. Click **Add & Login** → enter the code sent to your Telegram

### 3. Scrape Members
1. Go to **Scraper** tab
2. Paste the group/channel link
3. Select a connected account
4. Configure filters (has username, not bot, last seen, has photo)
5. Click **Start Scraping**

### 4. Add Members
1. Go to **Adder** tab
2. Enter the target group link
3. Select user source (all scraped or specific group)
4. Adjust delay range (recommended: 8-25s)
5. Click **Start Adding**
6. Use Pause/Resume/Stop as needed

### 5. Export Logs
1. Go to **Logs** tab
2. Click **Export TXT** or **Export CSV**

### 6. Build to EXE
1. Go to **Settings** tab
2. Click **Build .exe**
3. Find the executable in `dist/CyberTG_2026.exe`

---

## 🛡️ Anti-Ban Protections

| Protection | Description |
|---|---|
| Account Rotation | Round-robin across all connected accounts |
| Random Delay | 8-25s randomized delay between each add |
| FloodWait Handling | Auto-sleep when Telegram sends FloodWait |
| PeerFlood Switch | Automatically disables flooded accounts |
| 3-Strike Disable | Account disabled after 3 consecutive floods |
| Error Categorization | Privacy, NotMutual, Banned — all handled gracefully |

---

## 📋 Compile to Standalone EXE

```bash
python build.py
```

Or click the **Build .exe** button in the Settings tab.

The executable will be created at `dist/CyberTG_2026.exe`.

---

**CyberTG Mass Scraper & Adder 2026** — Made with ⚡
