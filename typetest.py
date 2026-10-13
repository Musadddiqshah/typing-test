#!/usr/bin/env python3
"""Animated terminal typing test for Termux.

Run:  python typetest.py
Menu:     Up/Down move, Enter select, Ctrl+C quit
Test:     type the words, Enter restarts, Esc goes back to the menu
Scores and settings are saved in ~/.typetest.json
"""
import curses
import json
import os
import random
import time

os.environ.setdefault("ESCDELAY", "25")

DATA_PATH = os.path.expanduser("~/.typetest.json")

WORDS = """the of and to in is you that it he was for on are as with his they at be this
have from or one had by word but not what all were we when your can said there use an
each which she do how their if will up other about out many then them these so some her
would make like him into time has look two more write go see number no way could people
my than first water been call who oil its now find long down day did get come made may
part over new sound take only little work know place year live me back give most very
after thing our just name good sentence man think say great where help through much
before line right too mean old any same tell boy follow came want show also around form
three small set put end does another well large must big even such because turn here
why ask went men read need land different home us move try kind hand picture again
change off play spell air away animal house point page letter mother answer found study
still learn should world high""".split()

MODES = [15, 25, 30, 50, 60]          # word counts shown in the menu
TIME_CAPS = [0, 30, 60, 120]          # 0 = no time limit
HISTORY_KEEP = 50
SPARK = "▁▂▃▄▅▆▇█"
BLOCK, SHADE, EMPTY = "█", "▓", "░"
ENTER_KEYS = (10, 13, curses.KEY_ENTER)
BACKSPACE_KEYS = (8, 127, curses.KEY_BACKSPACE)
ESC = 27
COL_W = 34


# ---------- saved data ----------

def default_data():
    return {"bests": {}, "history": [], "settings": {"blink": True, "time_cap": 0}}


def load_data():
    data = default_data()
    try:
        with open(DATA_PATH) as f:
            saved = json.load(f)
        data["bests"] = saved.get("bests", {})
        data["history"] = saved.get("history", [])
        data["settings"].update(saved.get("settings", {}))
    except (OSError, ValueError):
        pass
    return data


def save_data(data):
    try:
        with open(DATA_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


# ---------- typing game ----------

class Game:
    def __init__(self, words, data):
        self.words = words
        self.data = data
        self.restart()

    def restart(self):
        self.cap = self.data["settings"]["time_cap"]
        self.target = " ".join(random.choice(WORDS) for _ in range(self.words))
        self.typed = []
        self.start = None
        self.end_time = None
        self.total_keys = 0
        self.wrong_keys = 0
        self.samples = []
        self.last_sec = -1
        self.flash_until = 0.0
        self.created = time.time()

    def label(self):
        return f"{self.words} words"

    def elapsed(self):
        if self.start is None:
            return 0.0
        end = self.end_time or time.time()
        e = end - self.start
        return min(e, self.cap) if self.cap else e

    def time_left(self):
        if not self.cap or self.start is None:
            return None
        return max(0.0, self.cap - (time.time() - self.start))

    def finished(self):
        if self.end_time is not None:
            return True
        if self.start is None:
            return False
        if len(self.typed) >= len(self.target):
            return True
        return bool(self.cap) and time.time() - self.start >= self.cap

    def correct(self):
        return sum(1 for i, c in enumerate(self.typed) if c == self.target[i])

    def words_done(self):
        return min(self.words, "".join(self.typed).count(" ") + (1 if self.finished() else 0))

    def wpm(self):
        e = self.elapsed()
        if e <= 0:
            return 0
        return round(self.correct() / 5 / (e / 60))

    def acc(self):
        if self.total_keys == 0:
            return 100
        return round((self.total_keys - self.wrong_keys) / self.total_keys * 100)

    def key(self, ch):
        if self.finished():
            return
        if ch in BACKSPACE_KEYS:
            if self.typed:
                self.typed.pop()
            return
        if 32 <= ch <= 126 and len(self.typed) < len(self.target):
            if self.start is None:
                self.start = time.time()
            c = chr(ch)
            self.total_keys += 1
            if c != self.target[len(self.typed)]:
                self.wrong_keys += 1
                self.flash_until = time.time() + 0.18
            self.typed.append(c)

    def tick(self):
        if self.start is not None and self.end_time is None and self.finished():
            self.end_time = time.time()
            if self.cap:
                self.end_time = min(self.end_time, self.start + self.cap)
            self.record()
        sec = int(self.elapsed())
        if self.start is not None and sec != self.last_sec:
            self.last_sec = sec
            self.samples.append(self.wpm())

    def record(self):
        """Save the finished test to best scores and history."""
        key = str(self.words)
        self.data["bests"][key] = max(self.data["bests"].get(key, 0), self.wpm())
        self.data["history"].append({
            "when": time.strftime("%Y-%m-%d %H:%M"),
            "words": self.words,
            "wpm": self.wpm(),
            "acc": self.acc(),
            "mistakes": self.wrong_keys,
            "time": round(self.elapsed(), 1),
        })
        self.data["history"] = self.data["history"][-HISTORY_KEEP:]
        save_data(self.data)

    def best(self):
        return self.data["bests"].get(str(self.words), 0)


# ---------- drawing helpers ----------

def layout(text, width):
    """Positions for each character, wrapping at spaces so words stay whole."""
    pos, y, x = [], 0, 0
    n, i = len(text), 0
    while i < n:
        if text[i] == " ":
            pos.append((y, x))
            x += 1
            if x >= width:
                y, x = y + 1, 0
            i += 1
            continue
        j = text.find(" ", i)
        j = n if j == -1 else j
        if x > 0 and x + (j - i) > width:
            y, x = y + 1, 0
        for k in range(i, j):
            pos.append((y, x))
            x += 1
            if x >= width and k < j - 1:
                y, x = y + 1, 0
        i = j
    return pos


def make_put(scr):
    h, w = scr.getmaxyx()

    def put(y, x, s, attr=0):
        if 0 <= y < h and 0 <= x < w - 1:
            try:
                scr.addnstr(y, x, s, w - x - 1, attr)
            except curses.error:
                pass

    def center(y, s, attr=0):
        put(y, max(0, (w - len(s)) // 2), s, attr)

    return put, center, h, w


def attrs():
    return {
        "accent": curses.color_pair(4) | curses.A_BOLD,
        "dim": curses.color_pair(3) | curses.A_DIM,
        "green": curses.color_pair(1) | curses.A_BOLD,
        "red": curses.color_pair(2) | curses.A_BOLD,
        "cyan": curses.color_pair(6) | curses.A_BOLD,
    }


def pulse(color, now, data):
    """Blink between bold and dim in one color, once a second.

    Many terminals ignore the blink attribute, so the on/off change is
    done with bold and dim, which every terminal shows.
    """
    if not data["settings"]["blink"]:
        return curses.color_pair(color) | curses.A_BOLD
    if int(now * 2) % 2 == 0:
        return curses.color_pair(color) | curses.A_BOLD
    return curses.color_pair(color) | curses.A_DIM


def render_block(put, center, h, w, lines):
    """Center a list of (text, attr) rows as one aligned block."""
    block_w = max(len(s) for s, _ in lines)
    x0 = max(0, (w - block_w) // 2)
    y0 = max(1, (h - len(lines)) // 2)
    for i, (s, attr) in enumerate(lines):
        if s:
            put(y0 + i, x0, s, attr)


# ---------- screens ----------

def menu_items(data):
    """Rows for the main menu: word modes, History, Settings, Exit."""
    items = []
    for n in MODES:
        best = data["bests"].get(str(n))
        items.append((f"{n} words", f"best {best} wpm" if best else "no score yet"))
    items.append(("History", f"{len(data['history'])} tests"))
    items.append(("Settings", ""))
    items.append(("Exit", ""))
    return items


def draw_menu(scr, sel, items, data, now):
    scr.erase()
    put, center, h, w = make_put(scr)
    a = attrs()
    title = pulse(4, now, data)
    author = pulse(6, now, data)
    top = max(1, h // 2 - len(items) // 2 - 5)

    author_x = max(0, (w - len("Author: AM")) // 2)
    put(top, author_x, "Author: ", a["dim"])
    put(top, author_x + len("Author: "), "AM", author)
    center(top + 1, "T Y P E T E S T", title)
    center(top + 2, "Up/Down move · Enter select · Ctrl+C quit", a["dim"])

    col = COL_W // 2
    x = max(0, (w - COL_W) // 2)
    for i, (label, score) in enumerate(items):
        marker = "> " if i == sel else "  "
        row = (marker + label).ljust(col) + score
        put(top + 4 + i * 2, x, row, (a["accent"] | curses.A_BOLD) if i == sel else a["dim"])

    scr.refresh()


def draw_settings(scr, sel, data, now):
    scr.erase()
    put, center, h, w = make_put(scr)
    a = attrs()
    s = data["settings"]
    cap = f"{s['time_cap']}s" if s["time_cap"] else "off"
    rows = [
        (f"Blink: {'on' if s['blink'] else 'off'}", "Enter toggles"),
        (f"Time limit: {cap}", "Enter cycles 0 / 30 / 60 / 120s"),
        ("Back", ""),
    ]
    lines = [("SETTINGS", a["accent"]), ("", 0)]
    for i, (label, hint) in enumerate(rows):
        marker = "> " if i == sel else "  "
        attr = (a["accent"] | curses.A_BOLD) if i == sel else a["dim"]
        lines.append(((marker + label).ljust(COL_W) + hint, attr))
    lines += [("", 0), ("Esc back", a["dim"])]
    render_block(put, center, h, w, lines)
    scr.refresh()


def draw_history(scr, data, now):
    scr.erase()
    put, center, h, w = make_put(scr)
    a = attrs()
    lines = [("HISTORY", a["accent"]), ("", 0)]
    recent = list(reversed(data["history"][-10:]))
    if not recent:
        lines.append(("No tests yet. Finish one to see it here.", a["dim"]))
    for t in recent:
        row = (f"{t['when']}  {t['words']:>3}w  {t['wpm']:>3} wpm  "
               f"{t['acc']:>3}%  {t['mistakes']} miss")
        lines.append((row, a["dim"]))
    lines += [("", 0), ("Enter or Esc back", a["dim"])]
    render_block(put, center, h, w, lines)
    scr.refresh()


def draw_test(scr, g, now, data):
    scr.erase()
    put, center, h, w = make_put(scr)
    a = attrs()

    put(0, 1, " TYPETEST ", a["accent"] | curses.A_REVERSE)
    cap_text = f" · {g.cap}s cap" if g.cap else ""
    put(0, 12, f"{g.words} words{cap_text}", a["accent"])
    put(1, 1, "Enter restart · Esc menu · Ctrl+C quit", a["dim"])

    if g.end_time is not None:
        draw_results(g, now, center, put, w, h, a, data)
        scr.refresh()
        return

    flashing = now < g.flash_until
    put(3, 2, f"{g.wpm():>3} wpm", a["green"])
    put(3, 14, f"{g.acc():>3}% acc", curses.A_BOLD)
    put(3, 26, f"{g.words_done()}/{g.words} words", a["accent"])
    left = g.time_left()
    if left is not None:
        put(3, 44, f"{left:4.0f}s left", a["accent"])
    if flashing:
        put(3, 58, "✗ miss", a["red"])

    # Progress bar with a shimmering leading edge
    bar_w = max(10, min(w - 12, 60))
    frac = len(g.typed) / len(g.target)
    filled = int(frac * bar_w)
    shimmer = int(now * 12) % 3 if data["settings"]["blink"] else 0
    bar_attr = curses.color_pair(1) if frac < 0.75 else curses.color_pair(2)
    put(5, 2, BLOCK * max(0, filled - 1), bar_attr)
    if filled > 0:
        put(5, 2 + filled - 1, SHADE if shimmer else BLOCK, bar_attr | curses.A_BOLD)
    put(5, 2 + filled, EMPTY * (bar_w - filled), a["dim"])

    # WPM sparkline
    recent = g.samples[-bar_w:]
    top = max(recent + [1])
    spark = "".join(SPARK[min(7, round(v / top * 7))] if v > 0 else " " for v in recent)
    put(6, 2, spark, a["accent"])
    if not g.start:
        put(6, 2, "start typing to begin", a["dim"])

    # Text area: typewriter reveal on launch, auto-scroll to cursor
    tw = max(20, min(w - 4, 72))
    pos = layout(g.target, tw)
    cur = len(g.typed)
    cy = pos[min(cur, len(pos) - 1)][0]
    top_row = 8
    visible = h - top_row - 2
    start_line = max(0, cy - visible // 3)
    reveal = min(len(g.target), int((now - g.created) * 80))
    blink_on = (int(now * 2) % 2 == 0) if data["settings"]["blink"] else True

    for i, ch in enumerate(g.target):
        y, x = pos[i]
        sy = y - start_line + top_row
        if sy < top_row or sy >= h - 1:
            continue
        if i < cur:
            if g.typed[i] == ch:
                attr, shown = a["green"], ch
            else:
                attr, shown = a["red"] | curses.A_UNDERLINE, ("_" if ch == " " else ch)
        elif i == cur:
            attr = (curses.color_pair(5) if blink_on else a["accent"]) | curses.A_BOLD
            shown = ch
        elif i < reveal:
            attr, shown = a["dim"], ch
        else:
            continue
        put(sy, 2 + x, shown, attr)

    status = "type the words above" if not g.start else f"{cur} chars  {int(frac * 100)}% through"
    put(h - 1, 2, status, a["dim"])
    scr.refresh()


def draw_results(g, now, center, put, w, h, a, data):
    final = g.wpm()
    t = now - g.end_time
    shown = int(final * min(1.0, t / 1.2))

    lines = [
        (f"RESULTS · {g.words} words", a["accent"]),
        (f"{shown} wpm", a["green"]),
        ("", 0),
    ]
    if t > 0.8:
        lines += [
            (f"accuracy   {g.acc()}%", 0),
            (f"correct    {g.correct()} chars", 0),
            (f"mistakes   {g.wrong_keys}", 0),
            (f"time       {g.elapsed():.1f}s", 0),
            (f"best       {g.best()} wpm", a["dim"]),
        ]
    if t > 1.5:
        top = max(g.samples + [1])
        spark = "".join(SPARK[min(7, round(v / top * 7))] if v > 0 else " "
                        for v in g.samples)[:40]
        lines += [
            ("", 0),
            (spark, a["accent"]),
            ("", 0),
            ("Enter again · Esc menu", a["dim"]),
        ]
    render_block(put, center, h, w, lines)


# ---------- main loop ----------

def main(scr):
    curses.curs_set(0)
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    curses.init_pair(1, curses.COLOR_GREEN, bg)
    curses.init_pair(2, curses.COLOR_RED, bg)
    curses.init_pair(3, curses.COLOR_WHITE, bg)
    curses.init_pair(4, curses.COLOR_YELLOW, bg)
    curses.init_pair(5, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(6, curses.COLOR_CYAN, bg)

    scr.keypad(True)
    scr.timeout(30)

    data = load_data()
    screen = "menu"
    sel = 0
    ssel = 0
    g = None

    while True:
        ch = scr.getch()
        now = time.time()

        if screen == "menu":
            items = menu_items(data)
            count = len(items)
            if ch == curses.KEY_UP:
                sel = (sel - 1) % count
            elif ch == curses.KEY_DOWN:
                sel = (sel + 1) % count
            elif ch in ENTER_KEYS:
                if sel < len(MODES):
                    g = Game(MODES[sel], data)
                    screen = "test"
                elif sel == len(MODES):
                    screen = "history"
                elif sel == len(MODES) + 1:
                    screen, ssel = "settings", 0
                else:
                    break
            draw_menu(scr, sel, items, data, now)

        elif screen == "history":
            if ch in ENTER_KEYS or ch == ESC:
                screen = "menu"
            draw_history(scr, data, now)

        elif screen == "settings":
            s = data["settings"]
            if ch == ESC:
                screen = "menu"
            elif ch == curses.KEY_UP:
                ssel = (ssel - 1) % 3
            elif ch == curses.KEY_DOWN:
                ssel = (ssel + 1) % 3
            elif ch in ENTER_KEYS:
                if ssel == 0:
                    s["blink"] = not s["blink"]
                    save_data(data)
                elif ssel == 1:
                    i = TIME_CAPS.index(s["time_cap"]) if s["time_cap"] in TIME_CAPS else 0
                    s["time_cap"] = TIME_CAPS[(i + 1) % len(TIME_CAPS)]
                    save_data(data)
                else:
                    screen = "menu"
            draw_settings(scr, ssel, data, now)

        else:  # test
            if ch == ESC:
                screen = "menu"
                continue
            if ch in ENTER_KEYS:
                g.restart()
            elif ch != -1:
                g.key(ch)
            g.tick()
            draw_test(scr, g, now, data)


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
