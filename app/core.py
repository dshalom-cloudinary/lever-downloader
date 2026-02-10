"""
core.py – Lever Resume Download Engine
---------------------------------------
Reusable class that drives the Playwright browser to scrape Lever
and download candidate resumes.  Communicates progress via a callback
so that any frontend (CLI, GUI, web) can display live status.
"""

import re
import time
import threading
from pathlib import Path
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# ── Defaults ─────────────────────────────────────────────────────
DEFAULT_LEVER_URL = (
    "https://hire.lever.co/candidates"
    "?pipeline=applicant"
    "&postingIds%5B%5D=e22ee3a3-7660-4ba1-89ac-d03fdf95dd60"
    "&postingIds%5B%5D=3f4bfbd9-8145-4da8-aeda-70a4c015c80b"
    "&stageId=applicant-new"
)
DEFAULT_DOWNLOAD_DIR = Path.home() / "Desktop" / "lever-resumes"
DELAY_BETWEEN_CANDIDATES = 1.5   # seconds
PAGE_LOAD_TIMEOUT = 30_000       # ms
LOGIN_TIMEOUT = 300              # seconds (5 min)
# ─────────────────────────────────────────────────────────────────


def sanitize_filename(name: str) -> str:
    """Turn a candidate name into a filesystem-safe filename."""
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"\s+", "_", name)
    return name


class ResumeDownloader:
    """
    Drives a Playwright browser to download resumes from Lever.

    Parameters
    ----------
    lever_url : str
        Full Lever candidates page URL (with pipeline/posting filters).
    download_dir : Path
        Local folder where resume files will be saved.
    on_progress : callable, optional
        Callback invoked with a dict describing each progress event.
        See *Progress Events* below.

    Progress Events
    ---------------
    {"type": "status",           "message": str}
    {"type": "login_waiting",    "elapsed": int}
    {"type": "login_detected"}
    {"type": "scrolling",        "count": int}
    {"type": "candidates_found", "count": int}
    {"type": "candidate_start",  "index": int, "total": int, "name": str}
    {"type": "candidate_done",   "index": int, "total": int, "name": str, "result": str}
    {"type": "complete",         "downloaded": int, "skipped": int, "errors": int}
    {"type": "error",            "message": str}
    """

    def __init__(
        self,
        lever_url: str = DEFAULT_LEVER_URL,
        download_dir: Path = DEFAULT_DOWNLOAD_DIR,
        on_progress: Optional[Callable[[dict], None]] = None,
    ):
        self.lever_url = lever_url
        self.download_dir = Path(download_dir)
        self._on_progress = on_progress or (lambda e: None)
        self._stop_event = threading.Event()

    # ── Public API ───────────────────────────────────────────────

    def run(self):
        """Execute the full download flow (blocking)."""
        self._stop_event.clear()
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._emit({"type": "status", "message": "Launching browser ..."})

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=False, slow_mo=200)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            try:
                # Step 1 – Navigate & wait for login
                self._wait_for_login(page)
                if self._stopped():
                    return

                # Step 2 – Collect candidates
                candidates = self._collect_candidate_links(page)
                total = len(candidates)
                self._emit({"type": "candidates_found", "count": total})

                if total == 0:
                    self._emit({"type": "error", "message": "No candidates found. Check the URL or page."})
                    return

                # Step 3 – Download resumes
                downloaded = 0
                skipped = 0
                errors = 0

                for idx, (name, url) in enumerate(candidates, 1):
                    if self._stopped():
                        self._emit({"type": "status", "message": "Cancelled by user."})
                        break

                    self._emit({"type": "candidate_start", "index": idx, "total": total, "name": name})
                    result = self._download_resume(page, name, url)
                    self._emit({"type": "candidate_done", "index": idx, "total": total, "name": name, "result": result})

                    if result == "downloaded":
                        downloaded += 1
                    elif "error" in result:
                        errors += 1
                    else:
                        skipped += 1

                    time.sleep(DELAY_BETWEEN_CANDIDATES)

                self._emit({"type": "complete", "downloaded": downloaded, "skipped": skipped, "errors": errors})

            except Exception as exc:
                self._emit({"type": "error", "message": str(exc)})
            finally:
                browser.close()

    def stop(self):
        """Signal the download loop to stop after the current candidate."""
        self._stop_event.set()

    # ── Internal helpers ─────────────────────────────────────────

    def _emit(self, event: dict):
        self._on_progress(event)

    def _stopped(self) -> bool:
        return self._stop_event.is_set()

    # -- Login ---------------------------------------------------

    def _wait_for_login(self, page):
        self._emit({"type": "status", "message": "Opening Lever – please log in in the browser window ..."})
        page.goto(self.lever_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)

        waited = 0
        while waited < LOGIN_TIMEOUT:
            if self._stopped():
                return
            try:
                links = page.query_selector_all('a[href*="/candidates/"]')
                if len(links) >= 1:
                    break
            except Exception:
                pass
            try:
                page.wait_for_timeout(3000)
            except Exception:
                time.sleep(3)
            waited += 3
            if waited % 12 == 0:
                self._emit({"type": "login_waiting", "elapsed": waited})

        if waited >= LOGIN_TIMEOUT:
            raise RuntimeError("Timed out waiting for login (5 minutes).")

        try:
            page.wait_for_timeout(3000)
        except Exception:
            time.sleep(3)

        self._emit({"type": "login_detected"})

    # -- Scroll & collect ----------------------------------------

    def _scroll_to_load_all(self, page):
        previous_count = 0
        stale_rounds = 0

        while stale_rounds < 6:
            if self._stopped():
                return previous_count
            try:
                links = page.query_selector_all('a[href*="/candidates/"]')
                current_count = len(links)
            except Exception:
                current_count = previous_count

            self._emit({"type": "scrolling", "count": current_count})

            if current_count == previous_count:
                stale_rounds += 1
            else:
                stale_rounds = 0
                previous_count = current_count

            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            page.evaluate("""
                document.querySelectorAll('div, section, main').forEach(el => {
                    if (el.scrollHeight > el.clientHeight + 100) {
                        el.scrollTop = el.scrollHeight;
                    }
                });
            """)
            page.wait_for_timeout(1500)

        return previous_count

    def _collect_candidate_links(self, page):
        self._emit({"type": "status", "message": "Scrolling to load all candidates ..."})
        self._scroll_to_load_all(page)

        candidates = []
        seen_urls = set()

        all_links = page.query_selector_all("a[href]")

        skip_texts = {
            "overview", "notes", "feedback", "emails", "forms",
            "talent fit", "candidates", "jobs", "interviews",
            "referrals", "visual insights", "more", "archive",
        }

        for link in all_links:
            href = link.get_attribute("href") or ""
            if "/candidates/" not in href:
                continue
            match = re.search(r"/candidates/([0-9a-f-]{36})", href)
            if not match:
                continue

            candidate_id = match.group(1)
            canonical_url = f"https://hire.lever.co/candidates/{candidate_id}"
            if canonical_url in seen_urls:
                continue

            try:
                name = link.inner_text().strip()
            except Exception:
                name = ""

            if len(name) < 2 or name.lower() in skip_texts:
                continue

            candidates.append((name, canonical_url))
            seen_urls.add(canonical_url)

        # Deduplicate by name
        final, seen_names = [], set()
        for name, url in candidates:
            if name not in seen_names:
                final.append((name, url))
                seen_names.add(name)

        return final

    # -- Resume download -----------------------------------------

    def _find_and_click_resume_file(self, page) -> bool:
        all_links = page.query_selector_all("a[href]")
        for link in all_links:
            text = link.inner_text().strip()
            if re.search(r"\.(pdf|docx?|rtf)$", text, re.IGNORECASE):
                link.click()
                return True

        for selector in ['a[href*="/resumes/"]', 'a[href*="/files/"]', 'a[href*=".pdf"]']:
            links = page.query_selector_all(selector)
            if links:
                links[0].click()
                return True

        return False

    def _find_download_element(self, page):
        for selector in [
            'a[download]',
            'a[href*="download"]',
            'a[title*="ownload" i]',
            'a[aria-label*="ownload" i]',
            'button[title*="ownload" i]',
            'button[aria-label*="ownload" i]',
            '[data-testid*="download" i]',
        ]:
            el = page.query_selector(selector)
            if el:
                return el

        for el in page.query_selector_all("a, button"):
            try:
                if "download" in el.inner_text().strip().lower():
                    return el
            except Exception:
                pass

        for selector in [
            'a[href*="/resumes/"][href*="/download"]',
            'a[href*="/files/"][href*="/download"]',
        ]:
            el = page.query_selector(selector)
            if el:
                return el

        return None

    def _download_resume(self, page, candidate_name: str, candidate_url: str) -> str:
        try:
            page.goto(candidate_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            page.wait_for_timeout(2000)

            if not self._find_and_click_resume_file(page):
                return "no_resume"

            page.wait_for_timeout(3000)

            safe_name = sanitize_filename(candidate_name)
            target_path = self.download_dir / f"{safe_name}_Resume.pdf"

            download_el = self._find_download_element(page)
            if not download_el:
                return "no_download_button"

            href = download_el.get_attribute("href") or ""

            if href and href != "#":
                full_url = href if href.startswith("http") else f"https://hire.lever.co{href}"
                response = page.request.get(full_url)
                if response.ok:
                    content_disp = response.headers.get("content-disposition", "")
                    fname_match = re.search(r'filename[*]?="?([^";]+)', content_disp)
                    if fname_match:
                        orig = fname_match.group(1).strip()
                        ext = Path(orig).suffix or ".pdf"
                        target_path = self.download_dir / f"{safe_name}_Resume{ext}"
                    target_path.write_bytes(response.body())
                    return "downloaded"
                else:
                    return f"error: HTTP {response.status}"
            else:
                with page.expect_download(timeout=15_000) as dl_info:
                    download_el.click()
                dl_info.value.save_as(str(target_path))
                return "downloaded"

        except PwTimeout:
            return "error: timeout"
        except Exception as e:
            return f"error: {e}"
