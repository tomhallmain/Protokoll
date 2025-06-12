# Log Tracker

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
   python main.py
   ```

## Usage

1. Create a new Tracker for your project
2. Add log directories to track (the application will automatically find and display log files)
3. Select a tracker to view its log files
4. Use the search feature to find specific log entries
5. The application will remember your last selected tracker and log file 