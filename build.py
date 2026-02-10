#!/usr/bin/env python3
"""
build.py – Package the Lever Resume Downloader as a standalone desktop app.
---------------------------------------------------------------------------
Produces:
    macOS  →  dist/Lever Resume Downloader.app
    Other  →  dist/LeverResumeDownloader/  (folder with executable)

Usage:
    python build.py
"""

import platform
import subprocess
import sys
from pathlib import Path

# ── Locate Playwright's bundled Chromium ─────────────────────────
def find_chromium_path() -> Path:
    """Return the path to the Playwright Chromium installation."""
    try:
        from playwright._impl._driver import compute_driver_executable
        result = compute_driver_executable()
        # compute_driver_executable may return a tuple (node_path, cli_js) or a string
        driver_exec = result[0] if isinstance(result, (tuple, list)) else result
        driver_dir = Path(driver_exec).parent
    except ImportError:
        # Fallback: common locations
        driver_dir = None

    # Walk known cache locations
    search_roots = []
    if driver_dir:
        search_roots.append(driver_dir / "package" / ".local-browsers")
    search_roots.append(Path.home() / "Library" / "Caches" / "ms-playwright")
    search_roots.append(Path.home() / ".cache" / "ms-playwright")

    for root in search_roots:
        if not root.exists():
            continue
        # Prefer full chromium over headless_shell
        candidates = [c for c in root.iterdir() if c.is_dir() and "chromium" in c.name.lower()]
        # Sort so that "chromium-XXXX" (without "headless") comes before "chromium_headless_shell-XXXX"
        candidates.sort(key=lambda p: ("headless" in p.name.lower(), p.name), reverse=False)
        if candidates:
            return candidates[0]

    print("ERROR: Could not locate Playwright Chromium installation.")
    print("       Run `playwright install chromium` first.")
    sys.exit(1)


def build():
    app_name = "Lever Resume Downloader"
    entry_point = "app/gui.py"

    # Determine platform-specific args
    is_mac = platform.system() == "Darwin"

    # NOTE: Chromium is NOT bundled.  The app auto-installs it on first launch
    # via _ensure_chromium_installed() in core.py.  This avoids macOS code-
    # signing issues with nested .app bundles and keeps the download small.
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--noconfirm",
        "--windowed" if is_mac else "--console",
        # Hidden imports that PyInstaller misses
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "greenlet",
        "--hidden-import", "pyee",
        # Collect Playwright's driver (includes node binary + CLI)
        "--collect-all", "playwright",
        # Entry point
        entry_point,
    ]

    # Add icon if available
    icon_path = Path("app/assets/icon.icns" if is_mac else "app/assets/icon.ico")
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    print(f"\nRunning PyInstaller ...\n  {' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)

    print(f"\nBuild complete!")
    if is_mac:
        print(f"  App bundle: dist/{app_name}.app")
        print(f"  To run:     open 'dist/{app_name}.app'")
    else:
        print(f"  Executable: dist/{app_name}/{app_name}")
    print()


if __name__ == "__main__":
    build()
