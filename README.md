# Protokoll - Log File Tracker and Reader

A desktop application for managing and viewing log files across different projects. This application allows you to:

- Create and manage multiple log trackers for different projects
- Automatically track and display log files from specified directories
- View and search through log files with syntax highlighting
- Remember your last viewed log files between sessions
- Organize logs by project

## Features

- Cross-platform support (Windows, macOS, Linux)
- Modern GUI interface with dark theme
- Automatic log file discovery and tracking
- Project-based log organization
- Advanced log viewing and searching capabilities
- Persistent session state (remembers last selected tracker and log file)

## Installation

1. Ensure you have Python 3.8+ installed
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run the application:
   ```
   python run.py
   ```

## Building an executable

`build_exe.py` builds a single executable with [Nuitka](https://nuitka.net):
`dist/Protokoll.exe` on Windows, `dist/Protokoll` on macOS and Linux. It runs
on a machine without Python and uses the same settings, trackers and keys as
`python run.py`.

1. Use Python 3.11 and a C compiler (Visual Studio Build Tools on Windows,
   or let Nuitka download MinGW; Xcode Command Line Tools on macOS).
2. Build:
   ```
   python build_exe.py
   ```
   The script creates its own `.venv-build` from `requirements-build.txt`,
   compiles, copies the result to `dist/` and runs it once with
   `--smoke-test` in a scratch environment. Add `--with-oqs` for quantum-safe
   (OQS) key encapsulation; a build without it cannot read data encrypted with
   OQS keys. The log of each build is in `build/logs/`.
3. Publish it as a GitHub release (needs the GitHub CLI, `gh`):
   ```
   python scripts/package_release.py
   ```
   It rebuilds the executable if it is behind the checkout, stages it with its
   checksums and lock file, and creates a draft release after asking; rerun with
   `--publish` to publish the draft.

Where the executable keeps its files:

- Settings and trackers: `~/.protokoll` (as when run from source).
- Its unpacked runtime: `~/.protokoll/unpacked/protokoll-<build id>`. The first
  start of a new build unpacks it; that start also removes older builds'
  folders.
- Its own logs, and `faults.log` for native crashes: `%APPDATA%\protokoll\logs`
  on Windows, `~/.local/share/protokoll/logs` elsewhere. The first lines of
  each log name the version and build.

The build records the path of the checkout it was built from, which anyone
with the executable can read; a build warns at startup when that checkout has
moved on since.

## Encrypted state

Tracker definitions, the tracked log directories and the last-used tracker are
encrypted at rest. The keys for them are backed up automatically to an external
drive (set `PROTOKOLL_KEY_BACKUP_DIR` to choose where). Run
`python scripts/key_material.py` to check that backup's state, or `backup` to
take one by hand.

## Usage

1. Create a new Tracker for your project
2. Add log directories to track (the application will automatically find and display log files)
3. Select a tracker to view its log files
4. Use the search feature to find specific log entries
5. The application will remember your last selected tracker and log file 
