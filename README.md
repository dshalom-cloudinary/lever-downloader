# Lever Resume Downloader

A desktop tool that bulk-downloads candidate resumes from [Lever](https://hire.lever.co).

It opens a browser window for you to log in, then automatically visits each candidate profile, finds the resume file, and saves it to a local folder.

---

## For HR Users (Pre-built App)

1. Download the latest **Lever Resume Downloader.app** from the team's shared drive
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

### Run the GUI

```bash
python -m app.gui
```

### Run the CLI (original script)

```bash
python download_resumes.py
```

### Build the Desktop App

```bash
python build.py
```

This produces a standalone `.app` (macOS) in `dist/`. The app bundles Python, Playwright, and Chromium — no dependencies needed on the target machine.

---

## Project Structure

```
lever-downloader/
├── app/
│   ├── __init__.py
│   ├── core.py          # Download engine (ResumeDownloader class)
│   └── gui.py           # Tkinter desktop GUI
├── download_resumes.py  # Original CLI script (standalone)
├── build.py             # PyInstaller build script
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
