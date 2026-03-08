"""
CyberTG – PyInstaller Build Script
Compiles the project into a standalone .exe
"""
import os
import sys
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "main.py")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")


def build():
    print("=" * 60)
    print("  CyberTG Mass Scraper & Adder 2026 — Build to EXE")
    print("=" * 60)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "CyberTG_2026",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        # Hidden imports for Telethon + CustomTkinter
        "--hidden-import", "telethon",
        "--hidden-import", "telethon.crypto",
        "--hidden-import", "telethon.tl",
        "--hidden-import", "customtkinter",
        "--hidden-import", "socks",
        "--hidden-import", "cryptg",
        "--hidden-import", "sqlite3",
        # Add data files
        "--add-data", f"core{os.pathsep}core",
        "--add-data", f"gui{os.pathsep}gui",
        # Paths
        "--distpath", DIST_DIR,
        "--workpath", BUILD_DIR,
        "--specpath", PROJECT_ROOT,
        # Main script
        MAIN_SCRIPT,
    ]

    print(f"\nRunning: {' '.join(cmd[:10])}...\n")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode == 0:
        exe_path = os.path.join(DIST_DIR, "CyberTG_2026.exe")
        print(f"\n✅ Build successful!")
        print(f"   Executable: {exe_path}")
        print(f"   Size: {os.path.getsize(exe_path) / 1024 / 1024:.1f} MB")
    else:
        print(f"\n❌ Build failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    build()
