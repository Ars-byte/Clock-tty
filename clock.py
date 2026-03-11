#!/usr/bin/env python3
"""
TTY-CLOCK - Python port
Original C version: Copyright © 2008-2018 tty-clock contributors
Python port: faithful translation of the original logic
"""

import curses
import time
import argparse
import signal
import sys
from datetime import datetime, timezone

# Constants
NORMFRAMEW = 35
SECFRAMEW  = 54
DATEWINH   = 3
AMSIGN     = " [AM]"
PMSIGN     = " [PM]"

# Digit bitmaps (5 rows x 3 cols = 15 cells each)
NUMBER = [
    [1,1,1, 1,0,1, 1,0,1, 1,0,1, 1,1,1],  # 0
    [0,0,1, 0,0,1, 0,0,1, 0,0,1, 0,0,1],  # 1
    [1,1,1, 0,0,1, 1,1,1, 1,0,0, 1,1,1],  # 2
    [1,1,1, 0,0,1, 1,1,1, 0,0,1, 1,1,1],  # 3
    [1,0,1, 1,0,1, 1,1,1, 0,0,1, 0,0,1],  # 4
    [1,1,1, 1,0,0, 1,1,1, 0,0,1, 1,1,1],  # 5
    [1,1,1, 1,0,0, 1,1,1, 1,0,1, 1,1,1],  # 6
    [1,1,1, 0,0,1, 0,0,1, 0,0,1, 0,0,1],  # 7
    [1,1,1, 1,0,1, 1,1,1, 1,0,1, 1,1,1],  # 8
    [1,1,1, 1,0,1, 1,1,1, 0,0,1, 1,1,1],  # 9
]

# Color map: curses color index by number key
COLORS = [
    curses.COLOR_BLACK,   # 0
    curses.COLOR_RED,     # 1
    curses.COLOR_GREEN,   # 2
    curses.COLOR_YELLOW,  # 3
    curses.COLOR_BLUE,    # 4
    curses.COLOR_MAGENTA, # 5
    curses.COLOR_CYAN,    # 6
    curses.COLOR_WHITE,   # 7
]

COLOR_NAMES = [
    "Black", "Red", "Green", "Yellow",
    "Blue",  "Magenta", "Cyan", "White",
]


class TTYClock:
    def __init__(self, opts):
        self.running = True
        self.opt = opts

        # Geometry
        self.geo_x = 0
        self.geo_y = 0
        self.geo_w = SECFRAMEW if opts.second else NORMFRAMEW
        self.geo_h = 7
        self.geo_a = 1  # rebound direction x
        self.geo_b = 1  # rebound direction y

        # Time state
        self.hour   = [0, 0]
        self.minute = [0, 0]
        self.second = [0, 0]
        self.datestr = ""
        self.old_datestr = ""
        self.meridiem = ""

        # Curses windows (set in init)
        self.stdscr   = None
        self.framewin = None
        self.datewin  = None
        self.bg = -1
        self.color = opts.color  # curses color number
        self._color_flash_until = 0.0  # timestamp until which to show color name

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------
    def init(self, stdscr):
        self.stdscr = stdscr
        curses.cbreak()
        curses.noecho()
        stdscr.keypad(True)
        curses.start_color()
        curses.curs_set(0)
        stdscr.clear()
        stdscr.nodelay(True)

        try:
            curses.use_default_colors()
            self.bg = -1
        except Exception:
            self.bg = curses.COLOR_BLACK

        self._init_colors()

        self.geo_w = SECFRAMEW if self.opt.second else NORMFRAMEW
        self.geo_h = 7
        self.geo_a = 1
        self.geo_b = 1

        self.update_hour()

        self.framewin = curses.newwin(self.geo_h, self.geo_w, self.geo_x, self.geo_y)
        if self.opt.box:
            self.framewin.box()

        dw_x = self.geo_x + self.geo_h - 1
        dw_y = self.geo_y + (self.geo_w // 2) - (len(self.datestr) // 2) - 1
        self.datewin = curses.newwin(DATEWINH, len(self.datestr) + 2, dw_x, dw_y)
        if self.opt.box and self.opt.date:
            self.datewin.box()
        self.datewin.clearok(True)

        self.set_center(self.opt.center)

        if self.opt.date:
            self.datewin.refresh()
        self.framewin.refresh()

    def _init_colors(self):
        color = COLORS[self.color % 8]
        curses.init_pair(0, self.bg, self.bg)
        curses.init_pair(1, self.bg, color)
        curses.init_pair(2, color, self.bg)

    def _set_color(self, idx):
        self.color = idx % 8
        self._init_colors()
        self._color_flash_until = time.time() + 4.0  # mostrar por 4 segundos

    def _draw_color_hint(self):
        """Show color name for 4 seconds after a change, then clear."""
        max_rows, max_cols = self.stdscr.getmaxyx()
        label = f" Color: {COLOR_NAMES[self.color]} ({self.color}) — Tab/Space to cycle "
        label = label[:max_cols - 1]
        row = max_rows - 1
        if time.time() <= self._color_flash_until:
            attr = curses.color_pair(2) | curses.A_BOLD
            try:
                self.stdscr.addstr(row, 0, label, attr)
                self.stdscr.refresh()
            except curses.error:
                pass
        else:
            try:
                # Limpiar toda la última fila
                self.stdscr.addstr(row, 0, ' ' * (max_cols - 1))
                self.stdscr.refresh()
            except curses.error:
                pass

    # ------------------------------------------------------------------
    # Time update
    # ------------------------------------------------------------------
    def update_hour(self):
        if self.opt.utc:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()

        ihour = now.hour
        self.old_datestr = self.datestr

        if self.opt.twelve:
            self.meridiem = PMSIGN if ihour >= 12 else AMSIGN
            ihour = ihour - 12 if ihour > 12 else ihour
            ihour = 12 if ihour == 0 else ihour
        else:
            self.meridiem = ""

        self.hour[0]   = ihour // 10
        self.hour[1]   = ihour % 10
        self.minute[0] = now.minute // 10
        self.minute[1] = now.minute % 10
        self.second[0] = now.second // 10
        self.second[1] = now.second % 10

        fmt = self.opt.format
        try:
            date_part = now.strftime(fmt)
        except Exception:
            date_part = str(now.date())
        self.datestr = date_part + self.meridiem

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def draw_number(self, n, x, y):
        sy = y
        for i in range(30):
            if sy == y + 6:
                sy = y
                x += 1
            cell = NUMBER[n][i // 2]
            pair = curses.color_pair(1 if cell else 0)
            if self.opt.bold:
                pair |= curses.A_BOLD
            try:
                self.framewin.addch(x, sy, ' ', pair)
            except curses.error:
                pass
            sy += 1
        self.framewin.refresh()

    def draw_clock(self):
        # Redraw date window position if date string changed
        if (self.opt.date and not self.opt.rebound and
                self.datestr != self.old_datestr):
            self.clock_move(self.geo_x, self.geo_y, self.geo_w, self.geo_h)

        # Hours
        self.draw_number(self.hour[0], 1, 1)
        self.draw_number(self.hour[1], 1, 8)

        # Separator dots (blink if enabled)
        if self.opt.blink and int(time.time()) % 2 == 0:
            dot_pair = curses.color_pair(2)
        else:
            dot_pair = curses.color_pair(1)
        if self.opt.bold:
            dot_pair |= curses.A_BOLD

        try:
            self.framewin.addstr(2, 16, "  ", dot_pair)
            self.framewin.addstr(4, 16, "  ", dot_pair)
        except curses.error:
            pass

        # Minutes
        self.draw_number(self.minute[0], 1, 20)
        self.draw_number(self.minute[1], 1, 27)

        # Date
        if self.opt.date:
            date_attr = curses.color_pair(2)
            if self.opt.bold:
                date_attr |= curses.A_BOLD
            try:
                self.datewin.addstr(DATEWINH // 2, 1, self.datestr, date_attr)
                self.datewin.refresh()
            except curses.error:
                pass

        # Seconds
        if self.opt.second:
            try:
                self.framewin.addstr(2, NORMFRAMEW, "  ", dot_pair)
                self.framewin.addstr(4, NORMFRAMEW, "  ", dot_pair)
            except curses.error:
                pass
            self.draw_number(self.second[0], 1, 39)
            self.draw_number(self.second[1], 1, 46)

        self._draw_color_hint()

    # ------------------------------------------------------------------
    # Movement / layout
    # ------------------------------------------------------------------
    def clock_move(self, x, y, w, h):
        # Clear old positions
        self.framewin.bkgdset(curses.color_pair(0))
        self.framewin.border(' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ')
        self.framewin.erase()
        self.framewin.refresh()

        if self.opt.date:
            self.datewin.bkgdset(curses.color_pair(0))
            self.datewin.border(' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ')
            self.datewin.erase()
            self.datewin.refresh()

        self.geo_x, self.geo_y, self.geo_w, self.geo_h = x, y, w, h

        try:
            self.framewin.mvwin(x, y)
            self.framewin.resize(h, w)
        except curses.error:
            pass

        if self.opt.date:
            dw_x = x + h - 1
            dw_y = y + (w // 2) - (len(self.datestr) // 2) - 1
            try:
                self.datewin.mvwin(max(0, dw_x), max(0, dw_y))
                self.datewin.resize(DATEWINH, len(self.datestr) + 2)
            except curses.error:
                pass
            if self.opt.box:
                self.datewin.box()

        if self.opt.box:
            self.framewin.box()

        self.framewin.refresh()
        if self.opt.date:
            self.datewin.refresh()

    def clock_rebound(self):
        if not self.opt.rebound:
            return
        max_rows, max_cols = self.stdscr.getmaxyx()

        if self.geo_x < 1:
            self.geo_a = 1
        if self.geo_x > (max_rows - self.geo_h - DATEWINH):
            self.geo_a = -1
        if self.geo_y < 1:
            self.geo_b = 1
        if self.geo_y > (max_cols - self.geo_w - 1):
            self.geo_b = -1

        self.clock_move(self.geo_x + self.geo_a,
                        self.geo_y + self.geo_b,
                        self.geo_w, self.geo_h)

    def set_second(self):
        self.opt.second = not self.opt.second
        new_w = SECFRAMEW if self.opt.second else NORMFRAMEW
        max_rows, max_cols = self.stdscr.getmaxyx()
        y_adj = 0
        while (self.geo_y - y_adj) > (max_cols - new_w - 1):
            y_adj += 1
        self.clock_move(self.geo_x, self.geo_y - y_adj, new_w, self.geo_h)
        self.set_center(self.opt.center)

    def set_center(self, b):
        self.opt.center = b
        if b:
            self.opt.rebound = False
            max_rows, max_cols = self.stdscr.getmaxyx()
            self.clock_move(max_rows // 2 - self.geo_h // 2,
                            max_cols // 2 - self.geo_w // 2,
                            self.geo_w, self.geo_h)

    def set_box(self, b):
        self.opt.box = b
        self.framewin.bkgdset(curses.color_pair(0))
        self.datewin.bkgdset(curses.color_pair(0))
        if b:
            self.framewin.box()
            self.datewin.box()
        else:
            self.framewin.border(' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ')
            self.datewin.border(' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ')
        self.framewin.refresh()
        self.datewin.refresh()

    # ------------------------------------------------------------------
    # Key handling
    # ------------------------------------------------------------------
    def key_event(self):
        self.stdscr.timeout(self.opt.delay * 1000)
        c = self.stdscr.getch()

        if self.opt.screensaver:
            if c != curses.ERR and not self.opt.noquit:
                self.running = False
            else:
                if ord('0') <= c <= ord('7'):
                    self._set_color(c - ord('0'))
            return

        max_rows, max_cols = self.stdscr.getmaxyx()

        if c == curses.KEY_RESIZE:
            self._color_flash_until = 0.0
            self.stdscr.erase()
            self.stdscr.refresh()
            # Recrear las ventanas en posición 0,0 y luego centrar
            try:
                self.framewin.erase()
                self.framewin.refresh()
                del self.framewin
            except Exception:
                pass
            try:
                self.datewin.erase()
                self.datewin.refresh()
                del self.datewin
            except Exception:
                pass
            self.geo_x, self.geo_y = 0, 0
            self.framewin = curses.newwin(self.geo_h, self.geo_w, 0, 0)
            dw_y = max(0, (self.geo_w // 2) - (len(self.datestr) // 2) - 1)
            self.datewin = curses.newwin(DATEWINH, max(len(self.datestr) + 2, 2),
                                         self.geo_h - 1, dw_y)
            self.datewin.clearok(True)
            if self.opt.box:
                self.framewin.box()
            self.set_center(self.opt.center)

        elif c in (curses.KEY_UP, ord('k'), ord('K')):
            if self.geo_x >= 1 and not self.opt.center:
                self.clock_move(self.geo_x - 1, self.geo_y, self.geo_w, self.geo_h)

        elif c in (curses.KEY_DOWN, ord('j'), ord('J')):
            if self.geo_x <= (max_rows - self.geo_h - DATEWINH) and not self.opt.center:
                self.clock_move(self.geo_x + 1, self.geo_y, self.geo_w, self.geo_h)

        elif c in (curses.KEY_LEFT, ord('h'), ord('H')):
            if self.geo_y >= 1 and not self.opt.center:
                self.clock_move(self.geo_x, self.geo_y - 1, self.geo_w, self.geo_h)

        elif c in (curses.KEY_RIGHT, ord('l'), ord('L')):
            if self.geo_y <= (max_cols - self.geo_w - 1) and not self.opt.center:
                self.clock_move(self.geo_x, self.geo_y + 1, self.geo_w, self.geo_h)

        elif c in (ord('q'), ord('Q')):
            if not self.opt.noquit:
                self.running = False

        elif c in (ord('s'), ord('S')):
            self.set_second()

        elif c in (ord('t'), ord('T')):
            self.opt.twelve = not self.opt.twelve
            self.update_hour()
            self.clock_move(self.geo_x, self.geo_y, self.geo_w, self.geo_h)

        elif c in (ord('c'), ord('C')):
            self.set_center(not self.opt.center)

        elif c in (ord('b'), ord('B')):
            self.opt.bold = not self.opt.bold

        elif c in (ord('r'), ord('R')):
            self.opt.rebound = not self.opt.rebound
            if self.opt.rebound and self.opt.center:
                self.opt.center = False

        elif c in (ord('x'), ord('X')):
            self.set_box(not self.opt.box)

        elif c in (ord('\t'), ord(' ')):           # Tab / Space → siguiente color
            self._set_color(self.color + 1)

        elif c == curses.KEY_BTAB:                 # Shift+Tab → color anterior
            self._set_color(self.color - 1)

        elif ord('0') <= c <= ord('7'):
            self._set_color(c - ord('0'))

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self, stdscr):
        self.init(stdscr)
        while self.running:
            self.clock_rebound()
            self.update_hour()
            self.draw_clock()
            self.key_event()
        curses.endwin()


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="TTY-Clock - a terminal clock (Python port)")
    p.add_argument('-s', dest='second',     action='store_true', help='Show seconds')
    p.add_argument('-S', dest='screensaver',action='store_true', help='Screensaver mode')
    p.add_argument('-x', dest='box',        action='store_true', help='Show box')
    p.add_argument('-c', dest='center',     action='store_true', default=True, help='Center the clock (default: on)')
    p.add_argument('-b', dest='bold',       action='store_true', help='Bold colors')
    p.add_argument('-t', dest='twelve',     action='store_true', help='12-hour format')
    p.add_argument('-u', dest='utc',        action='store_true', help='Use UTC time')
    p.add_argument('-r', dest='rebound',    action='store_true', help='Rebound mode')
    p.add_argument('-n', dest='noquit',     action='store_true', help="Don't quit on keypress")
    p.add_argument('-D', dest='date',       action='store_false', default=True,
                                                                  help='Hide date')
    p.add_argument('-B', dest='blink',      action='store_true', help='Blinking colon')
    p.add_argument('-C', dest='color',      type=int, default=2,
                   choices=range(8), metavar='[0-7]', help='Clock color (default: 2=green)')
    p.add_argument('-f', dest='format',     default='%Y-%m-%d',  help='Date format string')
    p.add_argument('-d', dest='delay',      type=int, default=1,  help='Redraw delay in seconds')
    p.add_argument('-a', dest='nsdelay',    type=int, default=0,  help='Extra nanosecond delay (ignored in Python)')
    return p.parse_args()


def main():
    opts = parse_args()
    clock = TTYClock(opts)

    def _sig(signum, frame):
        clock.running = False

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT,  _sig)

    try:
        curses.wrapper(clock.run)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
