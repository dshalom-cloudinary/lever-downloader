#!/usr/bin/env python3
"""
gui.py – Tkinter Desktop GUI for the Lever Resume Downloader
-------------------------------------------------------------
Launch with:  python -m app.gui   (from repo root)
              or double-click the packaged .app
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Allow running as `python app/gui.py` or `python -m app.gui`
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import ResumeDownloader, DEFAULT_LEVER_URL, DEFAULT_DOWNLOAD_DIR


# ── Theme constants ──────────────────────────────────────────────
BG       = "#f5f6f8"
FG       = "#1e1e2e"
ACCENT   = "#0078d4"
SUCCESS  = "#16a34a"
ERROR    = "#dc2626"
MUTED    = "#6b7280"
FONT     = ("Helvetica Neue", 13)
FONT_SM  = ("Helvetica Neue", 11)
FONT_LOG = ("Menlo", 11)
PAD      = 14
# ─────────────────────────────────────────────────────────────────


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Lever Resume Downloader")
        self.geometry("680x580")
        self.minsize(560, 480)
        self.configure(bg=BG)

        self._downloader: ResumeDownloader | None = None
        self._thread: threading.Thread | None = None

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────

    def _build_ui(self):
        # Main container with padding
        outer = tk.Frame(self, bg=BG, padx=PAD * 2, pady=PAD)
        outer.pack(fill="both", expand=True)

        # Title
        tk.Label(
            outer, text="Lever Resume Downloader", font=("Helvetica Neue", 20, "bold"),
            bg=BG, fg=FG,
        ).pack(anchor="w", pady=(0, PAD))

        # ── URL input ────────────────────────────────────────────
        tk.Label(outer, text="Lever candidates URL", font=FONT_SM, bg=BG, fg=MUTED).pack(anchor="w")
        self._url_var = tk.StringVar(value=DEFAULT_LEVER_URL)
        url_entry = tk.Entry(outer, textvariable=self._url_var, font=FONT, relief="solid", bd=1)
        url_entry.pack(fill="x", pady=(2, PAD))

        # ── Output folder ────────────────────────────────────────
        tk.Label(outer, text="Save resumes to", font=FONT_SM, bg=BG, fg=MUTED).pack(anchor="w")
        folder_frame = tk.Frame(outer, bg=BG)
        folder_frame.pack(fill="x", pady=(2, PAD))

        self._folder_var = tk.StringVar(value=str(DEFAULT_DOWNLOAD_DIR))
        folder_entry = tk.Entry(folder_frame, textvariable=self._folder_var, font=FONT, relief="solid", bd=1)
        folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        browse_btn = tk.Button(
            folder_frame, text="Browse ...", font=FONT_SM, command=self._browse_folder,
            relief="solid", bd=1, padx=10,
        )
        browse_btn.pack(side="right")

        # ── Buttons ──────────────────────────────────────────────
        btn_frame = tk.Frame(outer, bg=BG)
        btn_frame.pack(fill="x", pady=(0, PAD))

        self._start_btn = tk.Button(
            btn_frame, text="Download Resumes", font=("Helvetica Neue", 14, "bold"),
            bg=ACCENT, fg="white", activebackground="#005a9e", activeforeground="white",
            relief="flat", padx=20, pady=6, command=self._on_start,
        )
        self._start_btn.pack(side="left")

        self._cancel_btn = tk.Button(
            btn_frame, text="Cancel", font=FONT, state="disabled",
            relief="solid", bd=1, padx=14, pady=4, command=self._on_cancel,
        )
        self._cancel_btn.pack(side="left", padx=(10, 0))

        # ── Status line ──────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(
            outer, textvariable=self._status_var, font=FONT_SM, bg=BG, fg=MUTED,
            anchor="w",
        ).pack(fill="x")

        # ── Progress bar ─────────────────────────────────────────
        self._progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self._progress.pack(fill="x", pady=(4, PAD))

        # ── Log area ─────────────────────────────────────────────
        tk.Label(outer, text="Log", font=FONT_SM, bg=BG, fg=MUTED).pack(anchor="w")
        log_frame = tk.Frame(outer, bg=BG)
        log_frame.pack(fill="both", expand=True)

        self._log = tk.Text(
            log_frame, font=FONT_LOG, bg="white", fg=FG, relief="solid", bd=1,
            state="disabled", wrap="word", height=10,
        )
        scrollbar = ttk.Scrollbar(log_frame, command=self._log.yview)
        self._log.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log.pack(side="left", fill="both", expand=True)

        # Configure log text tags for colours
        self._log.tag_configure("ok", foreground=SUCCESS)
        self._log.tag_configure("skip", foreground=MUTED)
        self._log.tag_configure("err", foreground=ERROR)
        self._log.tag_configure("info", foreground=ACCENT)

    # ── Actions ──────────────────────────────────────────────────

    def _browse_folder(self):
        folder = filedialog.askdirectory(
            title="Choose download folder",
            initialdir=self._folder_var.get(),
        )
        if folder:
            self._folder_var.set(folder)

    def _on_start(self):
        url = self._url_var.get().strip()
        folder = self._folder_var.get().strip()

        if not url:
            messagebox.showwarning("Missing URL", "Please enter a Lever candidates URL.")
            return
        if not folder:
            messagebox.showwarning("Missing folder", "Please choose a download folder.")
            return

        # Clear log
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

        self._progress["value"] = 0
        self._start_btn.configure(state="disabled")
        self._cancel_btn.configure(state="normal")

        self._downloader = ResumeDownloader(
            lever_url=url,
            download_dir=Path(folder),
            on_progress=self._handle_progress,
        )

        self._thread = threading.Thread(target=self._run_download, daemon=True)
        self._thread.start()

    def _on_cancel(self):
        if self._downloader:
            self._downloader.stop()
        self._cancel_btn.configure(state="disabled")
        self._status_var.set("Cancelling ...")

    def _run_download(self):
        try:
            self._downloader.run()
        except Exception as exc:
            self._schedule(self._append_log, f"Fatal error: {exc}\n", "err")
        finally:
            self._schedule(self._download_finished)

    def _download_finished(self):
        self._start_btn.configure(state="normal")
        self._cancel_btn.configure(state="disabled")

    # ── Progress callback (called from background thread) ────────

    def _handle_progress(self, event: dict):
        etype = event.get("type", "")

        if etype == "status":
            self._schedule(self._status_var.set, event["message"])
            self._schedule(self._append_log, event["message"] + "\n", "info")

        elif etype == "login_waiting":
            self._schedule(self._status_var.set, f"Waiting for login ... ({event['elapsed']}s)")

        elif etype == "login_detected":
            self._schedule(self._status_var.set, "Logged in! Scraping candidates ...")
            self._schedule(self._append_log, "Login detected.\n", "ok")

        elif etype == "scrolling":
            self._schedule(self._status_var.set, f"Scrolling ... {event['count']} candidates loaded")

        elif etype == "candidates_found":
            count = event["count"]
            self._schedule(self._status_var.set, f"Found {count} candidate(s). Downloading ...")
            self._schedule(self._append_log, f"Found {count} candidate(s).\n", "info")
            self._schedule(self._set_progress_max, count)

        elif etype == "candidate_start":
            idx, total, name = event["index"], event["total"], event["name"]
            self._schedule(self._status_var.set, f"[{idx}/{total}] {name} ...")

        elif etype == "candidate_done":
            idx, total, name, result = event["index"], event["total"], event["name"], event["result"]
            tag = "ok" if result == "downloaded" else ("skip" if "no_" in result else "err")
            self._schedule(self._append_log, f"[{idx}/{total}] {name} - {result}\n", tag)
            self._schedule(self._set_progress_value, idx)

        elif etype == "complete":
            d, s, e = event["downloaded"], event["skipped"], event["errors"]
            msg = f"Done! {d} downloaded, {s} skipped, {e} errors."
            self._schedule(self._status_var.set, msg)
            self._schedule(self._append_log, f"\n{msg}\n", "ok")

        elif etype == "error":
            self._schedule(self._status_var.set, f"Error: {event['message']}")
            self._schedule(self._append_log, f"ERROR: {event['message']}\n", "err")

    # ── Thread-safe UI helpers ───────────────────────────────────

    def _schedule(self, fn, *args):
        """Schedule a function call on the main (Tk) thread."""
        self.after(0, fn, *args)

    def _append_log(self, text: str, tag: str = ""):
        self._log.configure(state="normal")
        self._log.insert("end", text, tag)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _set_progress_max(self, total: int):
        self._progress.configure(maximum=total, value=0)

    def _set_progress_value(self, value: int):
        self._progress["value"] = value


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
