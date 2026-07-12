# University Backup — Canvas + OneDrive

Save **everything** from your university Canvas and OneDrive before you lose access at graduation — all your lecture slides, notes, practice questions, past papers, assignments, grades, and videos — neatly organised into folders on your own computer.

One program. A simple menu. No coding needed.

- **Canvas:** grabs every course's files, slides, pages, assignments, your submissions, grades, and Canvas-hosted videos — then sorts them into tidy folders (`Lecture Slides & Notes`, `Practice & Tutorials`, `Solutions`, `Past Exam Papers`, `Videos`). It even works if your university has hidden the "Files" or "Pages" tabs (it recovers them anyway).
- **OneDrive:** copies your OneDrive to your computer. You **pick which folders** — everything, or just the ones you choose.

Your Canvas token and files never leave your computer. Nothing is uploaded anywhere.

---

## Quick start (about 10 minutes)

### 1. Install Python
If you don't already have it, get Python 3.9 or newer from **https://www.python.org/downloads/**.
- On Windows, during install **tick "Add Python to PATH"**.
- To check it worked, open a terminal (see below) and type `python --version`.

**Opening a terminal:**
- **Windows:** press Start, type `PowerShell`, open it.
- **macOS:** press Cmd+Space, type `Terminal`, open it.
- **Linux:** open your Terminal app.

### 2. Download this tool
Either:
- Click the green **Code** button on this page → **Download ZIP** → unzip it, **or**
- If you have git: `git clone <this repo's URL>`

Then in your terminal, go into the folder:
```
cd path/to/canvas-backup
```

### 3. Install the two small libraries it needs
```
pip install -r requirements.txt
```
(If `pip` isn't found, try `python -m pip install -r requirements.txt`.)

### 4. Get your Canvas access token
1. Log into Canvas in your browser.
2. Go to **Account → Settings**.
3. Scroll to **Approved Integrations** → click **+ New Access Token**.
4. Give it any name (e.g. "backup"), optionally set an expiry, click **Generate Token**.
5. **Copy the token now** — Canvas only shows it once.

### 5. Run it
```
python backup.py
```
The first time, it asks for:
- your **Canvas web address** (e.g. `https://canvas.yourschool.edu`),
- your **access token** (paste it),
- **where to save** the backup (press Enter for the default: a `UniBackup` folder in your home directory).

Each time you start a backup it also asks **where to save** (press Enter to keep
your usual location, or type a new path — e.g. an external drive).

Then pick **1** from the menu to back up Canvas. Done!

---

## Backing up OneDrive (optional)

OneDrive backup uses a free tool called **rclone**.

1. Install rclone from **https://rclone.org/downloads/**
   - Windows: `winget install Rclone.Rclone` (or download the .exe and add it to PATH)
   - macOS: `brew install rclone`
   - Linux: `curl https://rclone.org/install.sh | sudo bash`
2. Run `python backup.py` and choose **2**.
3. A browser opens — **sign in with your university account**. Accept the default answers to any questions in the terminal.
4. It lists your OneDrive folders and lets you **pick which to download** (type `0` for everything, or e.g. `1,3,4`).
5. Afterwards it asks **"Also collect all documents & folders shared with you by others? [y/N]"** — answer `y` to also back up everything teammates/staff shared with you (group projects, shared folders, etc.), saved to an `OneDrive Shared/` folder. This finds them via the reliable "Shared with you" feed, and skips items your institution blocks from download (e.g. view-only videos).

---

## Where your files end up

Courses that bundle several topics (e.g. "Structures, Structural Dynamics and
FEA") are split by **section** first, then by type inside each section, so each
subject stays separate:

```
UniBackup/
├── Canvas/
│   └── <Term>/
│       └── CODE (Course Name)/
│           ├── Lecture Materials & Files/
│           │   ├── Structural Dynamics/         <- a course section
│           │   │   ├── Lecture Slides & Notes/
│           │   │   ├── Practice & Tutorials/
│           │   │   └── Solutions/
│           │   ├── Finite Element Analysis/     <- another section
│           │   │   └── Lecture Slides & Notes/
│           │   └── Other Materials/
│           ├── Pages/            (Canvas pages saved as HTML)
│           ├── My Submissions/
│           ├── YouTube Links/
│           └── grades_and_quizzes.json
└── OneDrive/
    └── (the folders you chose)
```

Single-topic courses skip the section layer and are organised by type directly
(`Lecture Slides & Notes/`, `Practice & Tutorials/`, `Solutions/`,
`Past Exam Papers/`, `Videos/`, `Images & Misc/`).

---

## Menu options
1. **Back up Canvas** and organise the files
2. **Back up OneDrive** (choose folders)
3. **Do both**
4. **Re-organise** already-downloaded Canvas files
5. **Change settings** (Canvas address / token / save folder)
6. **Quit**

---

## Good to know

- **Safe to re-run.** It skips files you already have, so you can run it again anytime to pick up new content.
- **Your Office files don't expire.** A `.docx` / `.pptx` / `.xlsx` saved to your computer opens forever — you only lose the *cloud* copies at graduation, which is exactly what this backs up.
- **Videos:** Canvas-hosted lecture videos are downloaded. Videos that only *stream* from your university's SharePoint/Microsoft Stream usually **cannot** be downloaded (the university blocks it) — those stay watchable in your browser only while your account is active.
- **Privacy:** your token is stored in a local `config.yaml` that is never uploaded (it's in `.gitignore`). Delete the token in Canvas → Settings when you're finished.

---

## Troubleshooting

- **"Could not log in to Canvas"** — check the web address (include `https://`) and that the token was copied fully. Tokens can expire; make a new one if needed.
- **`pip` or `python` not found** — reinstall Python and tick "Add Python to PATH" (Windows), or use `python3` / `pip3` (macOS/Linux).
- **Some files are missing** — a few universities delete old content on their side; those can't be recovered by anyone. Everything your account can still see is downloaded.

---

*Not affiliated with Instructure/Canvas or Microsoft. Use with your own account only. MIT licensed.*
