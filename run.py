#!/usr/bin/env python3
"""
run.py – Interactive CLI for the Lever Resume Downloader
--------------------------------------------------------
Prompts for the Lever URL and download folder, then runs the
ResumeDownloader engine with coloured terminal output.

Usage:
    python run.py
"""

import os
import sys
from pathlib import Path

from app.core import ResumeDownloader, DEFAULT_LEVER_URL, DEFAULT_DOWNLOAD_DIR

# ── ANSI colour helpers ──────────────────────────────────────────
BOLD  = "\033[1m"
DIM   = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED   = "\033[31m"
CYAN  = "\033[36m"
RESET = "\033[0m"

# ── Ensure stdin reads from the real terminal ─────────────────────
# When this script is launched via  curl ... | bash  the shell's
# stdin is the pipe, not the keyboard.  Re-open /dev/tty so that
# input() can prompt the user interactively.
if not sys.stdin.isatty():
    try:
        sys.stdin = open("/dev/tty", "r")
    except OSError:
        pass  # not on a Unix system or no tty available


def _print_banner():
    print()
    print(f"{BOLD}{'=' * 52}{RESET}")
    print(f"{BOLD}   Lever Resume Downloader  (Terminal){RESET}")
    print(f"{BOLD}{'=' * 52}{RESET}")
    print()


def _prompt(label: str, default: str) -> str:
    """Prompt the user for input with a default value."""
    display_default = default if len(default) < 60 else default[:57] + "..."
    answer = input(f"{CYAN}{label}{RESET} [{DIM}{display_default}{RESET}]: ").strip()
    return answer if answer else default


def _handle_progress(event: dict):
    """Print progress events to the terminal with colour."""
    etype = event.get("type", "")

    if etype == "status":
        print(f"  {DIM}{event['message']}{RESET}")

    elif etype == "login_waiting":
        elapsed = event["elapsed"]
        print(f"  {YELLOW}Waiting for login... ({elapsed}s elapsed){RESET}")

    elif etype == "login_detected":
        print(f"  {GREEN}Login detected!{RESET}")

    elif etype == "scrolling":
        count = event["count"]
        print(f"  {DIM}Scrolling... {count} candidates loaded so far{RESET}", end="\r")

    elif etype == "candidates_found":
        count = event["count"]
        print(f"\n  {BOLD}Found {count} candidate(s){RESET}")
        print()

    elif etype == "candidate_start":
        idx, total, name = event["index"], event["total"], event["name"]
        print(f"  [{idx:3d}/{total}] {name} ... ", end="", flush=True)

    elif etype == "candidate_done":
        result = event["result"]
        if result == "downloaded":
            print(f"{GREEN}downloaded{RESET}")
        elif "no_" in result:
            print(f"{YELLOW}{result}{RESET}")
        else:
            print(f"{RED}{result}{RESET}")

    elif etype == "complete":
        d, s, e = event["downloaded"], event["skipped"], event["errors"]
        print()
        print(f"  {BOLD}{'=' * 40}{RESET}")
        print(f"  {GREEN}Downloaded: {d}{RESET}   "
              f"{YELLOW}Skipped: {s}{RESET}   "
              f"{RED}Errors: {e}{RESET}")
        print(f"  {BOLD}{'=' * 40}{RESET}")

    elif etype == "error":
        print(f"  {RED}ERROR: {event['message']}{RESET}")


def main():
    _print_banner()

    lever_url = _prompt("Lever URL", DEFAULT_LEVER_URL)
    download_dir = _prompt("Download folder", str(DEFAULT_DOWNLOAD_DIR))

    print()
    print(f"  {BOLD}URL:{RESET}    {lever_url}")
    print(f"  {BOLD}Folder:{RESET} {download_dir}")
    print()

    downloader = ResumeDownloader(
        lever_url=lever_url,
        download_dir=Path(download_dir),
        on_progress=_handle_progress,
    )

    try:
        downloader.run()
    except KeyboardInterrupt:
        print(f"\n  {YELLOW}Cancelled.{RESET}")
        downloader.stop()
        sys.exit(1)

    print()
    print(f"  {DIM}Results saved to {download_dir}/results.txt{RESET}")
    print()


if __name__ == "__main__":
    main()
