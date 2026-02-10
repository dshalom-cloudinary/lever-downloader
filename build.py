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
        driver_dir = Path(compute_driver_executable()).parent
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
        # Find the chromium-* directory
        for child in sorted(root.iterdir(), reverse=True):
            if child.is_dir() and "chromium" in child.name.lower():
                return child

    print("ERROR: Could not locate Playwright Chromium installation.")
    print("       Run `playwright install chromium` first.")
    sys.exit(1)


def build():
    chromium_path = find_chromium_path()
    print(f"Chromium found at: {chromium_path}")

    app_name = "Lever Resume Downloader"
    entry_point = "app/gui.py"

    # Determine platform-specific args
    is_mac = platform.system() == "Darwin"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", app_name,
        "--noconfirm",
        "--windowed" if is_mac else "--console",
        # Bundle Chromium
        "--add-data", f"{chromium_path}:playwright_chromium",
        # Hidden imports that PyInstaller misses
        "--hidden-import", "playwright",
        "--hidden-import", "playwright.sync_api",
        "--hidden-import", "greenlet",
        "--hidden-import", "pyee",
        # Collect Playwright's driver
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
