# Typing Test (Termux)

An animated typing test for the terminal. It runs in Termux on Android and needs only Python.

## Author

**Musaddiq Shah**

Created with the help of Claude Code AI.

## Features

- Word modes: 15, 25, 30, 50, and 60 words
- Live words per minute (WPM), accuracy, and progress while you type
- Correct letters in green, mistakes in red and underlined
- Cursor letter turns bold and pops when it moves onto a new letter
- Best score for each mode
- History of your last tests
- Settings for Animate (on or off) and an optional time limit (30, 60, or 120 seconds)
- Results screen with a WPM graph

## Requirements

- Termux
- Python 3

## Install and run

```
pkg update && pkg install python
python typetest.py
```

## Controls

**Menu**

| Key | Action |
|---|---|
| Up / Down | Move the selection |
| Enter | Start a test, or open History, Settings, or Exit |
| Ctrl+C | Quit |

**Test**

| Key | Action |
|---|---|
| Enter | Restart the test |
| Esc | Back to the menu |
| Ctrl+C | Quit |

## Settings

Open **Settings** from the menu.

- **Animate:** turns the cursor pop and the progress bar shimmer on or off.
- **Time limit:** cycles through off, 30, 60, and 120 seconds. A test ends when the time runs out.

## Saved data

Scores, history, and settings are saved to `~/.typetest.json` in your Termux home folder. Delete that file to reset everything.

## License

Free to use and change.
