# Lever Resume Downloader

A tool that bulk-downloads candidate resumes from [Lever](https://hire.lever.co).

It opens a browser window for you to log in, then automatically visits each candidate profile, finds the resume file, and saves it to a local folder.

---

## For HR Users — Terminal (Recommended)

The fastest way to get started. Open **Terminal** (press `Cmd + Space`, type "Terminal", hit Enter) and paste this single command:

```bash
git clone -b desktop https://github.com/dshalom-cloudinary/lever-downloader.git ~/.lever-downloader 2>/dev/null; ~/.lever-downloader/install-and-run.sh
```

**What it does (automatically):**

1. Downloads the tool to `~/.lever-downloader/` (or updates it if already there)
2. Checks that Python 3 is installed (macOS includes it)
3. Sets up an isolated environment (nothing installed globally)
4. Installs the Chromium browser (~150 MB, one-time only)
5. Launches the downloader — prompts you for the Lever URL and download folder

**To run it again later**, just paste the same command — it will skip the setup and launch instantly.

### Step-by-step walkthrough

1. The tool asks for your **Lever URL** — paste the candidates page URL from your browser, or press Enter to use the default
2. It asks for a **download folder** — press Enter to use `~/Desktop/lever-resumes/`
3. A **browser window** opens — log in to Lever with your credentials
4. Once logged in, the tool automatically scrolls, finds all candidates, and downloads their resumes
5. When done, check your download folder — each resume is saved as `CandidateName_Resume.pdf`
6. A **results.txt** summary file is also saved in the folder

---

## For HR Users — Desktop App (macOS)

> **Note:** The `.app` may be blocked by corporate security policies. Use the Terminal method above if that happens.

1. Download the latest **Lever Resume Downloader.app** from [GitHub Releases](https://github.com/dshalom-cloudinary/lever-downloader/releases)
2. Double-click to open
3. Paste the Lever candidates URL (or use the default)
4. Choose a download folder
5. Click **Download Resumes**
6. A browser window opens — log in with your Lever credentials
7. The app downloads all resumes automatically and shows progress

---

## For Developers

### Prerequisites

- Python 3.9+
- pip

### Setup

```bash
git clone https://github.com/dshalom-cloudinary/lever-downloader.git
cd lever-downloader
git checkout desktop
pip install -r requirements.txt
playwright install chromium
```

### Run the interactive CLI

```bash
python run.py
```

### Run the GUI

```bash
python -m app.gui
```

### Run the original CLI (hardcoded URL)

```bash
python download_resumes.py
```

### Build the Desktop App

```bash
python build.py
```

This produces a standalone `.app` (macOS) in `dist/`.

---

## Project Structure

```
lever-downloader/
├── app/
│   ├── __init__.py
│   ├── core.py            # Download engine (ResumeDownloader class)
│   └── gui.py             # Tkinter desktop GUI
├── run.py                 # Interactive CLI frontend
├── install-and-run.sh     # One-command install & launch script
├── download_resumes.py    # Original CLI script (standalone)
├── build.py               # PyInstaller build script
├── requirements.txt
└── README.md
```

## How It Works

1. Launches a visible Chromium browser via Playwright
2. Navigates to the Lever candidates page
3. Waits for the user to log in (auto-detects when the candidate list loads)
4. Scrolls to load all candidates
5. Visits each candidate profile, clicks the resume file to open the viewer
6. Downloads the file via the authenticated session
7. Saves to the chosen folder as `CandidateName_Resume.pdf`
8. Writes a `results.txt` summary report
