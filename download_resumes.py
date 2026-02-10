#!/usr/bin/env python3
"""
Lever Resume Downloader
-----------------------
Opens Lever's candidate pipeline page, waits for you to log in,
then automatically visits each candidate profile and downloads
their resume PDF.

Usage:
    python download_resumes.py
"""

import os
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

# ── Configuration ────────────────────────────────────────────────
LEVER_URL = (
    "https://hire.lever.co/candidates"
    "?pipeline=applicant"
    "&postingIds%5B%5D=e22ee3a3-7660-4ba1-89ac-d03fdf95dd60"
    "&postingIds%5B%5D=3f4bfbd9-8145-4da8-aeda-70a4c015c80b"
    "&stageId=applicant-new"
)
DOWNLOAD_DIR = Path.home() / "Desktop" / "lever-resumes"
DELAY_BETWEEN_CANDIDATES = 1.5  # seconds – be polite to Lever
PAGE_LOAD_TIMEOUT = 30_000      # ms
# ─────────────────────────────────────────────────────────────────


def sanitize_filename(name: str) -> str:
    """Turn a candidate name into a safe filename."""
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)   # remove special chars
    name = re.sub(r"\s+", "_", name)        # spaces → underscores
    return name


def wait_for_login(page):
    """Navigate to Lever and wait until the candidates list is visible."""
    print("\n→ Opening Lever candidates page …")
    page.goto(LEVER_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)

    print(
        "\n╔══════════════════════════════════════════════════╗\n"
        "║  Please log in to Lever in the browser window.  ║\n"
        "║  The script will continue automatically once     ║\n"
        "║  it detects the candidates list has loaded.      ║\n"
        "╚══════════════════════════════════════════════════╝\n"
    )

    # Poll the page until we see candidate links (meaning login succeeded
    # and the candidates list rendered).  Wait up to 5 minutes.
    # Wrapped in try/except because navigations during login (SSO redirects)
    # can destroy the execution context.
    max_wait = 300  # seconds
    waited = 0
    while waited < max_wait:
        try:
            candidate_links = page.query_selector_all('a[href*="/candidates/"]')
            if len(candidate_links) >= 1:
                break
        except Exception:
            # Page is navigating (SSO redirect, etc.) – just keep waiting
            pass
        try:
            page.wait_for_timeout(3000)
        except Exception:
            time.sleep(3)
        waited += 3
        if waited % 12 == 0:
            print(f"  … still waiting for login ({waited}s elapsed)")

    if waited >= max_wait:
        raise RuntimeError("Timed out waiting for login (5 minutes). Please re-run the script.")

    # Give the page a moment to fully settle after login
    try:
        page.wait_for_timeout(3000)
    except Exception:
        time.sleep(3)
    print("✓ Authenticated – scraping candidates …\n")


def scroll_to_load_all_candidates(page):
    """Scroll the candidate list to trigger lazy-loading of all rows."""
    previous_count = 0
    stale_rounds = 0

    while stale_rounds < 6:
        # Count current candidate links
        candidate_links = page.query_selector_all(
            'a[href*="/candidates/"]'
        )
        current_count = len(candidate_links)
        print(f"  Scrolling … {current_count} candidate links loaded", flush=True)

        if current_count == previous_count:
            stale_rounds += 1
        else:
            stale_rounds = 0
            previous_count = current_count

        # Scroll the whole page
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

        # Also try scrolling any inner scrollable containers that hold the list
        # Lever often uses a scrollable div for the candidate list
        page.evaluate("""
            // Find all scrollable containers and scroll them to the bottom
            document.querySelectorAll('div, section, main').forEach(el => {
                if (el.scrollHeight > el.clientHeight + 100) {
                    el.scrollTop = el.scrollHeight;
                }
            });
        """)
        page.wait_for_timeout(1500)

    print(f"  Final count: {previous_count} candidate links", flush=True)
    return previous_count


def collect_candidate_links(page):
    """Return a list of (name, url) tuples for every candidate on the page."""
    scroll_to_load_all_candidates(page)

    candidates = []
    seen_urls = set()

    # Dump the current URL for debugging
    print(f"  Current page URL: {page.url}")

    # Grab ALL <a> tags on the page and inspect their hrefs to find candidates
    all_links = page.query_selector_all("a[href]")
    print(f"  Total <a> tags on page: {len(all_links)}")

    # Collect unique href patterns for debugging (first 10)
    sample_hrefs = []
    for link in all_links[:30]:
        href = link.get_attribute("href") or ""
        sample_hrefs.append(href)
    print(f"  Sample hrefs: {sample_hrefs[:10]}")

    for link in all_links:
        href = link.get_attribute("href") or ""

        # Lever candidate profile URLs contain /candidates/ followed by a UUID
        if "/candidates/" not in href:
            continue

        # Extract just the candidate path, ignoring query params
        # Match patterns like /candidates/<uuid> (36-char hex with dashes)
        match = re.search(r"/candidates/([0-9a-f-]{36})", href)
        if not match:
            continue

        # Normalize the URL to just the candidate base (no query params or sub-paths)
        candidate_id = match.group(1)
        canonical_url = f"https://hire.lever.co/candidates/{candidate_id}"

        if canonical_url in seen_urls:
            continue

        # Get the visible text of the link as the candidate name
        name = ""
        try:
            name = link.inner_text().strip()
        except Exception:
            pass

        # Skip links with no meaningful text (nav links, icons, etc.)
        # A candidate name should be at least 2 chars
        if len(name) < 2:
            continue

        # Skip if text looks like a tab label or navigation element
        skip_texts = {"overview", "notes", "feedback", "emails", "forms",
                      "talent fit", "candidates", "jobs", "interviews",
                      "referrals", "visual insights", "more", "archive"}
        if name.lower() in skip_texts:
            continue

        candidates.append((name, canonical_url))
        seen_urls.add(canonical_url)

    # Deduplicate by name (some candidates may appear multiple times)
    # Keep the first occurrence
    final = []
    seen_names = set()
    for name, url in candidates:
        if name not in seen_names:
            final.append((name, url))
            seen_names.add(name)

    return final


def find_and_click_resume_file(page) -> bool:
    """Click the resume file link on the candidate profile to open the viewer."""

    # Look for links whose text ends in .pdf / .docx / .doc (the filename)
    all_links = page.query_selector_all("a[href]")
    for link in all_links:
        text = link.inner_text().strip()
        if re.search(r"\.(pdf|docx?|rtf)$", text, re.IGNORECASE):
            link.click()
            return True

    # Look for links with resume/file-related hrefs
    for selector in [
        'a[href*="/resumes/"]',
        'a[href*="/files/"]',
        'a[href*=".pdf"]',
    ]:
        links = page.query_selector_all(selector)
        if links:
            links[0].click()
            return True

    return False


def download_resume(page, candidate_name: str, candidate_url: str, download_dir: Path) -> str:
    """
    Visit a candidate's profile, click the resume file to open the viewer,
    then use the download button (top-right) to save the file.
    Returns a status string: 'downloaded', 'no_resume', or 'error: <msg>'.
    """
    try:
        page.goto(candidate_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
        page.wait_for_timeout(2000)  # let the profile render

        # Step 1: Click on the resume file link to open the viewer
        if not find_and_click_resume_file(page):
            return "no_resume"

        # Wait for the resume viewer page to load
        page.wait_for_timeout(3000)

        safe_name = sanitize_filename(candidate_name)
        target_path = download_dir / f"{safe_name}_Resume.pdf"

        # Step 2: Find the download button/link in the viewer (top-right area)
        # Try multiple strategies to find the download button
        download_el = None

        # Look for a link/button with "download" in text, title, aria-label, or href
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
                download_el = el
                break

        # Also try finding by visible text
        if not download_el:
            for el in page.query_selector_all("a, button"):
                text = el.inner_text().strip().lower()
                if "download" in text:
                    download_el = el
                    break

        # Also look for a download icon (common: a link with a download SVG icon)
        if not download_el:
            # Try any link in the top area that has an SVG child (icon buttons)
            for selector in [
                'a[href*="/resumes/"][href*="/download"]',
                'a[href*="/files/"][href*="/download"]',
            ]:
                el = page.query_selector(selector)
                if el:
                    download_el = el
                    break

        if not download_el:
            # Last resort: dump all links on the page for debugging
            links = page.query_selector_all("a[href]")
            link_info = []
            for l in links:
                href = l.get_attribute("href") or ""
                text = l.inner_text().strip()[:50]
                title = l.get_attribute("title") or ""
                if href and ("download" in href.lower() or "download" in text.lower() or "download" in title.lower()):
                    link_info.append(f"  href={href} text={text} title={title}")
            if link_info:
                print(f"\n    DEBUG download-ish links found: {link_info}")
            return "no_download_button"

        # Step 3: Trigger the download
        href = download_el.get_attribute("href") or ""

        if href and href != "#":
            # It's a link – download directly via HTTP using the session cookies
            full_url = href if href.startswith("http") else f"https://hire.lever.co{href}"
            response = page.request.get(full_url)
            if response.ok:
                # Try to get the filename from Content-Disposition header
                content_disp = response.headers.get("content-disposition", "")
                fname_match = re.search(r'filename[*]?="?([^";]+)', content_disp)
                if fname_match:
                    orig_filename = fname_match.group(1).strip()
                    ext = Path(orig_filename).suffix or ".pdf"
                    target_path = download_dir / f"{safe_name}_Resume{ext}"

                target_path.write_bytes(response.body())
                return "downloaded"
            else:
                return f"error: HTTP {response.status}"
        else:
            # It's a button – click it and catch the download event
            with page.expect_download(timeout=15_000) as download_info:
                download_el.click()
            download = download_info.value
            download.save_as(str(target_path))
            return "downloaded"

    except PwTimeout:
        return "error: timeout"
    except Exception as e:
        return f"error: {e}"


def main():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 55)
    print("  Lever Resume Downloader")
    print("=" * 55)
    print(f"  Download folder: {DOWNLOAD_DIR}")
    print(f"  Target URL:      {LEVER_URL[:70]}…")
    print("=" * 55)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,          # visible window for login
            slow_mo=300,             # slight slowdown so you can follow along
        )
        context = browser.new_context(
            accept_downloads=True,   # enable file downloads
        )
        page = context.new_page()

        # Step 1 – Login
        wait_for_login(page)

        # Step 2 – Collect candidates
        candidates = collect_candidate_links(page)
        total = len(candidates)
        print(f"Found {total} candidate(s).\n")

        if total == 0:
            print("No candidates found. Check that the page loaded correctly.")
            browser.close()
            return

        # Step 3 – Visit each candidate and download resume
        downloaded = 0
        skipped = 0
        errors = []

        for idx, (name, url) in enumerate(candidates, 1):
            print(f"[{idx}/{total}] {name} … ", end="", flush=True)
            status = download_resume(page, name, url, DOWNLOAD_DIR)

            if status == "downloaded":
                downloaded += 1
                print("downloaded")
            elif status == "no_resume":
                skipped += 1
                print("no resume found – skipped")
            else:
                errors.append((name, status))
                print(status)

            time.sleep(DELAY_BETWEEN_CANDIDATES)

        # Step 4 – Summary
        print("\n" + "=" * 55)
        print("  Summary")
        print("=" * 55)
        print(f"  Total candidates:  {total}")
        print(f"  Downloaded:        {downloaded}")
        print(f"  Skipped (no file): {skipped}")
        print(f"  Errors:            {len(errors)}")
        if errors:
            print("\n  Failed candidates:")
            for name, err in errors:
                print(f"    - {name}: {err}")
        print("=" * 55)
        print(f"\n  Resumes saved to: {DOWNLOAD_DIR}\n")

        browser.close()


if __name__ == "__main__":
    main()
