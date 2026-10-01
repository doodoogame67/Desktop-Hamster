#!/usr/bin/env python3
"""
Desktop Hamster: a small low-poly hamster that roams around your screen.

  Left-click        pet it
  Left-drag         pick it up and put it down somewhere else
  Shake the mouse   startles it
  Right-click       menu (feed, sleep, stats, party hat, names, hide, quiet mode, quit)

Runs on Linux (PyQt5 or PyQt6) and macOS (PyQt6).
Progress is saved to ~/.config/desktop-hamster/state.json, apart from the app's own files,
so updating or reinstalling the app keeps the same hamster.
"""
import collections
import datetime
import json
import math
import os
import queue
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile

# Wayland (default on Ubuntu 22.04+) does not let a window position itself.
# Run under XWayland instead so the hamster can move around freely.
if sys.platform.startswith("linux") and os.environ.get("WAYLAND_DISPLAY") \
        and not os.environ.get("QT_QPA_PLATFORM"):
    os.environ["QT_QPA_PLATFORM"] = "xcb"

try:
    from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QRect
    from PyQt5.QtGui import (QPainter, QColor, QFont, QPixmap, QFontMetrics, QBitmap, QRegion,
                             QCursor)
    from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QInputDialog, QAction
    QT6 = False
    _QT = "PyQt5"
except ImportError:
    from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QRect
    from PyQt6.QtGui import (QPainter, QColor, QFont, QPixmap, QFontMetrics, QBitmap, QRegion,
                             QCursor, QAction)
    from PyQt6.QtWidgets import QApplication, QWidget, QMenu, QInputDialog
    QT6 = True
    _QT = "PyQt6"
try:
    _net = __import__(f"{_QT}.QtNetwork", fromlist=["QLocalServer", "QLocalSocket"])
    QLocalServer, QLocalSocket = _net.QLocalServer, _net.QLocalSocket
except ImportError:
    QLocalServer = QLocalSocket = None

IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
APP_ID = "desktop-hamster"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_ID)
STATE_FILE = os.path.join(STATE_DIR, "state.json")
OLD_STATE_FILE = os.path.join(os.path.expanduser("~"), ".local", "share", APP_ID, "state.json")
VERSION_FILE = os.path.join(HERE, "version.json")

# Where updates come from: "owner/repo" on GitHub (a public repo). Empty = updates off.
UPDATE_REPO = ""
UPDATE_BRANCH = "main"
UPDATE_EVERY = 20 * 3600        # seconds between automatic checks
UPDATE_KEEP = {"message.txt"}   # files an update never overwrites


def read_version(path=VERSION_FILE):
    """(version number, list of 'what's new' lines) from a version.json."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return int(d.get("version", 0)), [str(n) for n in d.get("notes", [])]
    except (OSError, ValueError, AttributeError):
        return 0, []


VERSION, VERSION_NOTES = read_version()
AUTOSTART_FILE = os.path.join(os.path.expanduser("~"), ".config", "autostart", APP_ID + ".desktop")
MESSAGE_FILE = os.path.join(HERE, "message.txt")

FPS = 30
SPRITE_W, SPRITE_H = 160, 116   # sprite canvas (see build_sprites.py)
SPRITE_FEET_Y = 102             # feet line inside the sprite canvas
W, H = 220, 180                 # hamster window; the top part is room for speech bubbles
SX = (W - SPRITE_W) // 2        # sprite x offset inside the window
FEET = H - SPRITE_H + SPRITE_FEET_Y   # feet line inside the window
MOUTH = 60                      # px from body centre to where food goes when eating
BUBBLE_MAX_W = 196

INK = "#3A2A1A"

FOODS = {
    "raspberry": {"label": "Raspberries", "hunger": 18, "happy": 5, "chub": 8},
    "mushroom":  {"label": "Mushroom",    "hunger": 24, "happy": 3, "chub": 12},
    "carrot":    {"label": "Carrot",      "hunger": 34, "happy": 4, "chub": 14},
}

# stat change per second
DECAY_HUNGER = 0.012      # full -> empty in ~2.3 h
DECAY_HAPPY = 0.007
DECAY_HAPPY_HUNGRY = 0.012
DECAY_ENERGY = 0.010
REGEN_ENERGY = 0.08
CHUB_BURN = 0.015         # chubbiness lost per second of walking
OVERFED = 80              # eating when food is above this makes it chubbier
CHUB_UP, CHUB_DOWN = (35, 75), (28, 68)   # tier thresholds, with a gap so it doesn't flicker
CHUB_SPEED = (1.0, 0.9, 0.78)

# ---------------------------------------------------------------------------- things it says
# {name} = the hamster's name, {you} = what it calls you
LINES = [
    "*scritch scritch*",
    "hm.",
    "i'm guarding this spot",
    "what's that little arrow doing",
    "i hid a seed somewhere. forgot where",
    "the air smells like mushrooms today",
    "you've been staring at that screen a while",
    "have you had water today?",
    "i could run on a wheel for hours",
    "tiny paws, big dreams",
    "*sniffs everything*",
    "this is my desktop now",
    "i heard there are trolls in the black forest",
    "someday i'll be big",
    "*grooms whiskers*",
    "don't mind me. just vibing",
    "{name} is thinking about seeds",
    "is it snack o'clock?",
    "you're doing great",
    "i found a crumb earlier. best day",
    "if you need me i'll be over here",
    "do you ever just... sit",
    "*stretches*",
]
YOU_LINES = [
    "hi {you}!",
    "whatcha working on, {you}?",
    "{you}, have you eaten today?",
    "don't work too hard, {you}",
    "psst. {you}.",
    "{you}! look! i'm small",
    "thanks for letting me live here, {you}",
    "i like it when {you} is around",
    "{you} smells like snacks",
    "proud of you, {you}",
    "{you}, stretch your legs a bit",
    "i'd share my seeds with {you}. maybe",
]
HUNGRY_LINES = ["my tummy is rumbling", "any berries around here?", "{you}, feed me? please?",
                "i'd eat a whole carrot right now", "*stares at you hungrily*"]
SLEEPY_LINES = ["*yawn*", "eyes... getting heavy", "nap soon", "so... cozy..."]
HAPPY_LINES = ["life is good", "{you} is my favorite human", "best day ever", "*happy squeak*"]
SAD_LINES = ["{you}? pet me?", "kinda lonely down here", "*sad squeak*", "hello? anyone?"]
NIGHT_LINES = ["it's so late, {you}. bed?", "the moon's out. go to sleep", "why are we awake"]
MORNING_LINES = ["good morning, {you}!", "breakfast?", "*stretches*"]
CHUB_LINES = ["i'm not chubby, i'm fluffy", "maybe one less berry today", "*waddles*",
              "my cheeks have cheeks", "i should go for a walk"]
VERY_CHUB_LINES = ["i am extremely round now", "i'm built like a dumpling", "*rolls a little*"]
FOLLOW_LINES = ["ooh, what's that?", "wait for me!", "whatcha got?", "i'm coming!"]
STARTLE_LINES = ["eek!", "whoa!", "!!", "don't scare me like that", "yikes"]
POKE_LINES = ["i'm right here, {you}!", "hi hi hi!", "you called?", "still here!"]
# unlocked the longer you keep it: (days together needed, line)
TIMED_LINES = [
    (3, "i know every corner of this desktop now"),
    (5, "remember when i first got here? i was so nervous"),
    (7, "a week ago i didn't even know you, {you}"),
    (10, "{you}, you're kind of my best friend"),
    (14, "i've been here two weeks and i still love it"),
    (21, "i've named all the icons. don't ask"),
    (30, "a whole month of snacks. thank you, {you}"),
    (45, "i'm basically a veteran desktop hamster now"),
    (60, "{you}, i hope you keep me forever"),
    (100, "we've been through a lot, huh"),
]
# day number -> what it says on that day (from day 7 on it also wears the party hat that day)
MILESTONES = {
    1: ["day two! i think i like it here"],
    3: ["three days together, {you}!"],
    7: ["one whole week with you, {you}!", "i found a party hat. it's mine now"],
    14: ["two weeks! party time"],
    30: ["one month together, {you}!", "best month ever"],
    50: ["fifty days! that's a lot of days"],
    100: ["ONE HUNDRED DAYS, {you}!", "i'm so glad i live here"],
    182: ["half a year together!"],
    365: ["one year, {you}. happy anniversary!", "thanks for keeping me around"],
}
HAT_UNLOCK_DAY = 7
ACTION_LINES = {"*grooms whiskers*": "groom", "*scritch scritch*": "groom", "*stretches*": "stretch"}


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def tflags(*fs):
    """Combine Qt flag enums into an int (works on PyQt5 and PyQt6)."""
    return sum(f.value if hasattr(f, "value") else int(f) for f in fs)


def global_pos(e):
    return e.globalPosition().toPoint() if QT6 else e.globalPos()


def today():
    return datetime.date.today()


def read_message():
    """Lines of message.txt (the note shown on first launch). Lines starting with # are skipped."""
    try:
        with open(MESSAGE_FILE, encoding="utf-8") as f:
            return [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    except OSError:
        return []


def fullscreen_app_active(own_ids):
    """True if the focused window is fullscreen (X11/XWayland windows only). None if unknown."""
    try:
        out = subprocess.run(["xprop", "-root", "_NET_ACTIVE_WINDOW"], capture_output=True,
                             text=True, timeout=1).stdout
        wid = out.strip().split()[-1].rstrip(",")
        if not wid.startswith("0x"):
            return False
        n = int(wid, 16)
        if n == 0 or n in own_ids:
            return False
        st = subprocess.run(["xprop", "-id", hex(n), "_NET_WM_STATE"], capture_output=True,
                            text=True, timeout=1).stdout
        return "_NET_WM_STATE_FULLSCREEN" in st
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


# =========================================================================== sprites

SPRITE_DIR = os.path.join(HERE, "sprites")
SPRITE_DPR = 2  # PNGs are rendered at 2x (see build_sprites.py)


class Sprites:
    """Pre-rendered frames from ./sprites (made by build_sprites.py), loaded on first use.

    File names look like  walk_2_c1h_r.png : pose_frame, chub level (c0-c2), h = party hat,
    r/l = facing right/left.
    """

    def __init__(self):
        self.frames = {}
        self.shapes = {}     # clickable outline of each frame, in logical px
        self.food = {k: self._load(f"food_{k}.png") for k in FOODS}
        self.get("idle_0", 1, "c0")  # fail early if the folder is missing

    @staticmethod
    def _load(fname):
        path = os.path.join(SPRITE_DIR, fname)
        pm = QPixmap(path)
        if pm.isNull():
            sys.exit(f"Missing sprite {path}. Keep the 'sprites' folder next to hamster.py.")
        pm.setDevicePixelRatio(SPRITE_DPR)
        return pm

    def get(self, name, facing, variant):
        key = (name, facing, variant)
        if key not in self.frames:
            self.frames[key] = self._load(f"{name}_{variant}_{'r' if facing > 0 else 'l'}.png")
        return self.frames[key]

    def shape(self, name, facing, variant):
        key = (name, facing, variant)
        if key not in self.shapes:
            img = self.get(name, facing, variant).toImage().scaled(SPRITE_W, SPRITE_H)
            self.shapes[key] = QRegion(QBitmap.fromImage(img.createAlphaMask()))
        return self.shapes[key]


# =========================================================================== pixel-art UI bits

HEART = (".XX.XX.",
         "XXXXXXX",
         "XXXXXXX",
         ".XXXXX.",
         "..XXX..",
         "...X...")


def draw_heart(p, x, y, px, alpha):
    c = QColor("#B8343A")
    c.setAlpha(int(alpha))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for r, row in enumerate(HEART):
        for col, ch in enumerate(row):
            if ch == "X":
                p.drawRect(QRectF(x + (col - 3.5) * px, y + (r - 3) * px, px, px))


def ui_font(px, bold=True):
    f = QFont("Georgia" if IS_MAC else "DejaVu Serif")
    f.setStyleHint(QFont.StyleHint.Serif)
    f.setPixelSize(px)
    f.setBold(bold)
    return f


# =========================================================================== windows

def _pet_window_flags(w):
    w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                     | Qt.WindowType.Tool)
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    if IS_MAC:
        # Tool windows vanish on macOS whenever the app loses focus unless told otherwise.
        w.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)


class Food(QWidget):
    SIZE = 34
    FEET = SIZE - 6   # ground line inside the food sprite

    def __init__(self, sprites, kind, gx, gy):
        """Drops in and lands with its base at screen point (gx, gy)."""
        super().__init__()
        _pet_window_flags(self)
        self.pix = sprites.food[kind]
        self.kind = kind
        self.resize(self.SIZE, self.SIZE)
        self.fx = gx - self.SIZE / 2
        self.land_y = gy - self.FEET
        self.fy = self.land_y - 70
        self.vy = 0.0
        self.landed = False
        self.taken = False     # in the hamster's paws
        self.move(int(self.fx), int(self.fy))
        self.show()

    @property
    def ground(self):
        return self.fx + self.SIZE / 2, self.fy + self.FEET

    def step(self):
        if self.landed:
            return
        self.vy = min(self.vy + 0.9, 18)
        self.fy += self.vy
        if self.fy >= self.land_y:
            self.fy = self.land_y
            if self.vy > 4:
                self.vy = -self.vy * 0.3
            else:
                self.landed = True
        self.move(int(self.fx), int(self.fy))

    def paintEvent(self, _):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.pix)


class Hamster(QWidget):
    def __init__(self, app, sprites):
        super().__init__()
        self.app = app
        self.sprites = sprites
        _pet_window_flags(self)
        self.resize(W, H)

        geo = app.primaryScreen().availableGeometry()
        self.screen_rect = geo
        # window position limits: the hamster itself stays on screen, the empty margins may not
        self.xmin, self.xmax = geo.left() - SX - 10, geo.right() + 1 - W + SX + 10
        self.ymin, self.ymax = geo.top(), geo.bottom() + 1 - FEET - 4

        first_run = not (os.path.exists(STATE_FILE) or os.path.exists(OLD_STATE_FILE))
        self.name = "Hammy"
        self.hunger = 80.0
        self.happy = 80.0
        self.energy = 100.0
        self.chatty = True
        self.owner = ""          # what the hamster calls you
        self.asked_owner = False
        self.gift_shown = False
        self.first_seen = today()
        self.celebrated = []     # milestone days already celebrated
        self.party_date = None   # wears the hat all day on a milestone day
        self.hat_on = False      # worn by choice (after it's unlocked)
        self.chub = 0.0
        self.chub_tier = 0
        self.updated_from = None       # set when the app is newer than the save
        self.last_update_check = 0.0
        self.update_busy = False
        self.update_manual = False
        self.update_results = queue.Queue()
        self.staged = None             # (folder, temp dir) of a downloaded update
        self.restart_cd = 0
        self.load()

        self.px = float(random.randint(self.xmin + 100, self.xmax - 100))
        self.py = float(random.randint(self.ymin + 100, self.ymax))
        self.facing = 1
        self.state = "idle"
        self.state_t = FPS * 2
        self.target = (self.px, self.py)
        self.run = 1.0           # speed multiplier (running away)
        self.target_food = None
        self.eating_kind = "raspberry"
        self.frame = 0
        self.blink_t = 0
        self.lift = 0.0
        self.foods = []
        self.hearts = []
        self.bubble = None       # (kind, ticks_left, payload)
        self.queue = collections.deque()   # lines waiting to be said, in order
        self.ask_after_queue = False
        self.chat_cd = random.randint(FPS * 12, FPS * 30)
        self.last_line = None
        self.drag_off = None
        self.press_pos = None
        self._mask_key = None
        self._fm = QFontMetrics(ui_font(12))
        # mouse tracking
        self.last_cursor = None
        self.cursor_seen = -10 ** 6      # frame when the cursor last moved
        self.swings = collections.deque()  # (frame, direction) of fast horizontal mouse moves
        self.startle_cd = 0
        # hiding
        self.hidden = None       # None, "fullscreen" or "manual"
        self.hide_until = 0.0

        self.move(int(self.px), int(self.py))

        self.tick_timer = QTimer(self)
        self.tick_timer.timeout.connect(self.tick)
        self.tick_timer.start(1000 // FPS)
        self.stat_timer = QTimer(self)
        self.stat_timer.timeout.connect(self.stat_tick)
        self.stat_timer.start(1000)
        self.save_timer = QTimer(self)
        self.save_timer.timeout.connect(self.save)
        self.save_timer.start(30_000)
        self.fs_timer = None
        if IS_LINUX and fullscreen_app_active(set()) is not None:
            self.fs_timer = QTimer(self)
            self.fs_timer.timeout.connect(self.check_fullscreen)
            self.fs_timer.start(1500)

        self.show()
        self.greet(first_run)
        self.check_milestone()
        QTimer.singleShot(20_000, self.auto_update_check)

    # ---- persistence
    def load(self):
        # saves used to live inside the app folder; still read from there once
        path = STATE_FILE if os.path.exists(STATE_FILE) else OLD_STATE_FILE
        try:
            with open(path) as f:
                d = json.load(f)
        except (OSError, ValueError):
            return
        if d.get("version", VERSION) < VERSION:
            self.updated_from = d.get("version")
        self.last_update_check = d.get("last_update_check", 0.0)
        self.name = d.get("name", self.name)
        self.chatty = d.get("chatty", True)
        self.owner = d.get("owner", "")
        self.asked_owner = d.get("asked_owner", bool(self.owner))
        self.gift_shown = d.get("gift_shown", True)   # older saves: don't replay the note
        try:
            self.first_seen = datetime.date.fromisoformat(d.get("first_seen", ""))
        except ValueError:
            self.first_seen = today()
        self.celebrated = d.get("celebrated", [])
        self.party_date = d.get("party_date")
        self.hat_on = d.get("hat_on", False)
        self.chub = d.get("chub", 0.0)
        self.chub_tier = self.tier_for(self.chub, 0)
        elapsed = max(0.0, time.time() - d.get("saved_at", time.time()))
        # Time away counts, but never leaves the hamster fully starving.
        self.hunger = max(min(d.get("hunger", 80), 10), d.get("hunger", 80) - elapsed * DECAY_HUNGER)
        self.happy = max(min(d.get("happy", 80), 20), d.get("happy", 80) - elapsed * DECAY_HAPPY)
        self.energy = 100.0

    def save(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"name": self.name, "hunger": self.hunger, "happy": self.happy,
                       "energy": self.energy, "chatty": self.chatty, "owner": self.owner,
                       "asked_owner": self.asked_owner, "gift_shown": self.gift_shown,
                       "first_seen": self.first_seen.isoformat(), "celebrated": self.celebrated,
                       "party_date": self.party_date, "hat_on": self.hat_on, "chub": self.chub,
                       "version": VERSION, "last_update_check": self.last_update_check,
                       "saved_at": time.time()}, f)
        os.replace(tmp, STATE_FILE)

    # ---- helpers
    @property
    def ground(self):
        """Screen point under the hamster's belly."""
        return self.px + W / 2, self.py + FEET

    @property
    def you(self):
        return self.owner or "friend"

    @property
    def days(self):
        """Whole days since you got it (0 on the first day)."""
        return max(0, (today() - self.first_seen).days)

    @property
    def hat_unlocked(self):
        return self.days >= HAT_UNLOCK_DAY

    @property
    def wearing_hat(self):
        return self.party_date == today().isoformat() or (self.hat_on and self.hat_unlocked)

    @property
    def variant(self):
        return f"c{self.chub_tier}{'h' if self.wearing_hat else ''}"

    @staticmethod
    def tier_for(chub, current):
        tier = current
        while tier < 2 and chub >= CHUB_UP[tier]:
            tier += 1
        while tier > 0 and chub < CHUB_DOWN[tier - 1]:
            tier -= 1
        return tier

    def fmt(self, line):
        return line.format(name=self.name, you=self.you)

    def clamp_pos(self, x, y):
        return clamp(x, self.xmin, self.xmax), clamp(y, self.ymin, self.ymax)

    def set_state(self, s, ticks=0):
        self.state = s
        self.state_t = ticks
        if s != "walk":
            self.run = 1.0

    def say(self, text, seconds=None):
        if seconds is None:
            seconds = 2.5 + len(text) / 14
        self.bubble = ("text", int(seconds * FPS), text)

    def say_later(self, *lines):
        """Queue lines to be said one after another."""
        self.queue.extend(self.fmt(ln) for ln in lines)

    def greet(self, first_run):
        hour = time.localtime().tm_hour
        who = f", {self.owner}" if self.owner else ""
        greet = "good morning" if 5 <= hour < 12 else "hi" if first_run else "hi again"
        self.say_later(f"{greet}{who}! it's me, {self.name}")
        if self.updated_from is not None:
            self.say_later("i learned new tricks!", *VERSION_NOTES)
        if not self.gift_shown:
            self.say_later(*read_message())
            self.gift_shown = True
        if not self.asked_owner:
            self.ask_after_queue = True

    def check_milestone(self):
        d = self.days
        if d in MILESTONES and d not in self.celebrated:
            self.celebrated.append(d)
            if d >= HAT_UNLOCK_DAY:
                self.party_date = today().isoformat()
            self.say_later(*MILESTONES[d])
            self.add_hearts(6)
            self.save()

    def pick_line(self):
        hour = time.localtime().tm_hour
        pools = []
        if self.hunger < 30:
            pools.append((HUNGRY_LINES, 0.6))
        if self.energy < 35:
            pools.append((SLEEPY_LINES, 0.5))
        if self.happy < 30:
            pools.append((SAD_LINES, 0.5))
        elif self.happy > 85:
            pools.append((HAPPY_LINES, 0.25))
        if 0 <= hour < 5:
            pools.append((NIGHT_LINES, 0.3))
        elif 6 <= hour < 10:
            pools.append((MORNING_LINES, 0.2))
        if self.chub_tier == 2:
            pools.append((VERY_CHUB_LINES + CHUB_LINES, 0.25))
        elif self.chub_tier == 1:
            pools.append((CHUB_LINES, 0.2))
        unlocked = [ln for day, ln in TIMED_LINES if self.days >= day]
        if unlocked:
            pools.append((unlocked, 0.2))
        if self.owner:
            pools.append((YOU_LINES, 0.3))
        pool = LINES
        for lines, chance in pools:
            if random.random() < chance:
                pool = lines
                break
        choices = [ln for ln in pool if ln != self.last_line] or pool
        line = random.choice(choices)
        self.last_line = line
        return line

    def chatter(self):
        line = self.pick_line()
        action = ACTION_LINES.get(line)
        if action and self.state == "idle":
            self.set_state(action, int(FPS * (2.6 if action == "groom" else 1.6)))
        self.say(self.fmt(line))

    def add_hearts(self, n=4):
        for _ in range(n):
            self.hearts.append([W / 2 + random.uniform(-30, 30), FEET - 60 + random.uniform(-6, 6), 255.0])

    def spawn_food(self, kind):
        gx, gy = self.ground
        g = self.screen_rect
        for _ in range(20):
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(160, 420)
            fx, fy = gx + math.cos(ang) * dist, gy + math.sin(ang) * dist * 0.7
            if g.left() + 90 < fx < g.right() - 90 and g.top() + 110 < fy < g.bottom() - 8:
                break
        fx = clamp(fx, g.left() + 90, g.right() - 90)
        fy = clamp(fy, g.top() + 110, g.bottom() - 8)
        self.foods.append(Food(self.sprites, kind, fx, fy))
        if self.state == "sleep" and self.hunger < 60:
            self.set_state("idle", FPS)
            self.say("*sniff sniff*")

    # ---- hiding (fullscreen apps, or asked to)
    def check_fullscreen(self):
        if self.hidden == "manual":
            if time.time() >= self.hide_until:
                self.unhide("i'm back!")
            return
        own = {int(self.winId())} | {int(f.winId()) for f in self.foods}
        fs = fullscreen_app_active(own)
        if fs and self.hidden is None:
            self.hide_all("fullscreen")
        elif fs is False and self.hidden == "fullscreen":
            self.unhide()

    def hide_all(self, reason, minutes=0):
        self.hidden = reason
        if reason == "manual":
            self.hide_until = time.time() + minutes * 60
            if self.fs_timer is None:   # no fullscreen check running to wake it up: use a one-off
                QTimer.singleShot(int(minutes * 60 * 1000), self._manual_hide_over)
        self.hide()
        for f in self.foods:
            f.hide()

    def _manual_hide_over(self):
        if self.hidden == "manual" and time.time() >= self.hide_until - 1:
            self.unhide("i'm back!")

    def unhide(self, line=None):
        self.hidden = None
        self.show()
        for f in self.foods:
            if not f.taken:
                f.show()
        if line:
            self.say(self.fmt(line))

    def poke(self):
        """Someone launched the app again while it was running."""
        if self.hidden:
            self.unhide()
        if self.state in ("sleep", "idle", "walk"):
            self.set_state("happy", int(FPS * 1.2))
            self.add_hearts(3)
        self.say(self.fmt(random.choice(POKE_LINES)))

    # ---- simulation
    def stat_tick(self):
        asleep = self.state == "sleep"
        self.hunger = clamp(self.hunger - DECAY_HUNGER * (0.5 if asleep else 1))
        self.happy = clamp(self.happy - (DECAY_HAPPY_HUNGRY if self.hunger < 25 else DECAY_HAPPY))
        self.energy = clamp(self.energy + REGEN_ENERGY) if asleep else clamp(self.energy - DECAY_ENERGY)
        if self.state in ("walk", "seek", "follow") and not self.hidden:
            self.set_chub(self.chub - CHUB_BURN)
        if self.frame % (FPS * 60) < FPS:   # about once a minute: did the date change?
            self.check_milestone()
            self.auto_update_check()

    # ---- updates
    def auto_update_check(self):
        if time.time() - self.last_update_check > UPDATE_EVERY:
            self.check_for_updates()

    def check_for_updates(self, manual=False):
        if self.update_busy or self.staged or not updates_possible():
            return
        self.update_busy = True
        self.update_manual = manual
        self.last_update_check = time.time()
        if manual:
            self.say("let me look...")

        def work():     # network and unpacking happen off the UI thread
            try:
                found = find_update()
                self.update_results.put(("ready", found) if found else ("none", None))
            except Exception:
                self.update_results.put(("error", None))
        threading.Thread(target=work, daemon=True).start()

    def poll_update(self):
        try:
            kind, found = self.update_results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.update_busy = False
            if kind == "ready":
                self.staged = found
                self.restart_cd = FPS * 4
                self.say("i learned something new! one sec...")
            elif self.update_manual:
                self.say("i'm all up to date!" if kind == "none" else "i couldn't reach the internet")
        if self.staged and self.drag_off is None and self.state in ("idle", "walk", "sleep", "groom", "stretch"):
            self.restart_cd -= 1
            if self.restart_cd <= 0:
                self.install_update()

    def install_update(self):
        (root, tmp), self.staged = self.staged, None
        try:
            apply_update(root)
        except OSError:
            self.say("hm, that update didn't work")
            return
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        # start again as the new version; the save file carries everything over
        self.save()
        for f in self.foods:
            f.close()
        server = getattr(self.app, "poke_server", None)
        if server is not None:
            server.close()
        os.execv(sys.executable, [sys.executable, os.path.join(HERE, "hamster.py")])

    def set_chub(self, value):
        self.chub = clamp(value)
        new = self.tier_for(self.chub, self.chub_tier)
        if new != self.chub_tier:
            grew = new > self.chub_tier
            self.chub_tier = new
            if grew:
                self.say_later("i think i'm getting... rounder" if new == 1 else "i am extremely round now")
            else:
                self.say_later("i feel lighter!")

    def cursor_fresh(self):
        return self.frame - self.cursor_seen < FPS * 2

    def cursor_dist(self):
        if self.last_cursor is None:
            return 1e9
        return math.dist(self.last_cursor, (self.px + W / 2, self.py + FEET - 35))

    def choose_next(self):
        landed = [f for f in self.foods if f.landed and not f.taken]
        if landed:
            gx, gy = self.ground
            self.target_food = min(landed, key=lambda f: math.dist(f.ground, (gx, gy)))
            self.set_state("seek")
            return
        if self.energy < 20:
            self.say("so sleepy...")
            self.set_state("sleep")
            return
        if self.hunger < 30 and random.random() < 0.4 and not self.bubble:
            self.bubble = ("hungry", FPS * 3, None)
        d = self.cursor_dist()
        if self.cursor_fresh() and 90 < d < 520 and random.random() < 0.3:
            self.set_state("follow", FPS * 6)
            if self.chatty and not self.bubble and random.random() < 0.5:
                self.say(self.fmt(random.choice(FOLLOW_LINES)))
            return
        r = random.random()
        if r < 0.10:
            self.set_state("groom", int(FPS * 2.6))
        elif r < 0.15:
            self.set_state("stretch", int(FPS * 1.6))
        elif r < 0.28:
            # a big trip to anywhere on the screen
            self.target = (random.uniform(self.xmin, self.xmax), random.uniform(self.ymin, self.ymax))
            self.set_state("walk")
        elif r < 0.65:
            ang = random.uniform(0, 2 * math.pi)
            dist = random.uniform(100, 480)
            self.target = self.clamp_pos(self.px + math.cos(ang) * dist,
                                         self.py + math.sin(ang) * dist * 0.75)
            self.set_state("walk")
        else:
            self.set_state("idle", random.randint(FPS * 2, FPS * 7))

    def walk_toward(self, tx, ty, speed):
        dx, dy = tx - self.px, ty - self.py
        d = math.hypot(dx, dy)
        if d <= speed:
            self.px, self.py = tx, ty
            return True
        if abs(dx) > 0.5:
            self.facing = 1 if dx > 0 else -1
        self.px += speed * dx / d
        self.py += speed * dy / d
        return False

    def track_cursor(self):
        cur = QCursor.pos()
        c = (cur.x(), cur.y())
        if self.last_cursor is not None and c != self.last_cursor:
            dx = c[0] - self.last_cursor[0]
            self.cursor_seen = self.frame
            if abs(dx) > 14:
                direction = 1 if dx > 0 else -1
                if not self.swings or self.swings[-1][1] != direction:
                    self.swings.append((self.frame, direction))
        self.last_cursor = c
        while self.swings and self.frame - self.swings[0][0] > FPS * 0.8:
            self.swings.popleft()
        if self.startle_cd > 0:
            self.startle_cd -= 1

        near = self.cursor_dist() < 200
        # shaking the mouse right next to it: startled, then it scurries off
        if (len(self.swings) >= 4 and near and self.startle_cd == 0 and self.drag_off is None
                and self.state in ("idle", "walk", "follow", "groom", "stretch")):
            self.swings.clear()
            self.startle_cd = FPS * 6
            self.set_state("startled", int(FPS * 0.7))
            self.facing = 1 if self.last_cursor[0] > self.px + W / 2 else -1
            self.say(self.fmt(random.choice(STARTLE_LINES)), 1.4)
            return
        # glance at the cursor when it moves nearby
        if self.state == "idle" and self.cursor_fresh() and self.cursor_dist() < 280:
            dx = self.last_cursor[0] - (self.px + W / 2)
            if abs(dx) > 30:
                self.facing = 1 if dx > 0 else -1

    def tick(self):
        self.frame += 1
        if self.hidden:
            return
        speed = (1.4 if self.hunger < 25 else 2.2) * CHUB_SPEED[self.chub_tier]

        for f in self.foods:
            f.step()
        self.track_cursor()

        s = self.state
        if s in ("idle", "groom", "stretch"):
            self.state_t -= 1
            if self.state_t <= 0 or any(f.landed and not f.taken for f in self.foods):
                self.choose_next()
        elif s == "walk":
            if self.walk_toward(*self.target, speed * self.run):
                self.set_state("idle", random.randint(FPS, FPS * 4))
            elif any(f.landed and not f.taken for f in self.foods):
                self.choose_next()
        elif s == "follow":
            self.state_t -= 1
            cx, cy = self.last_cursor
            side = 1 if cx > self.px + W / 2 else -1
            goal = self.clamp_pos(cx - W / 2 - side * 70, cy - FEET + 40)
            if self.walk_toward(*goal, speed * 1.2) or self.state_t <= 0:
                self.facing = side
                self.set_state("idle", random.randint(FPS * 2, FPS * 4))
        elif s == "startled":
            self.state_t -= 1
            if self.state_t <= 0:
                # run a short way from the cursor
                cx, cy = self.last_cursor
                bx, by = self.px + W / 2, self.py + FEET - 35
                ang = math.atan2(by - cy, bx - cx) + random.uniform(-0.5, 0.5)
                dist = random.uniform(180, 280)
                self.target = self.clamp_pos(self.px + math.cos(ang) * dist, self.py + math.sin(ang) * dist)
                self.set_state("walk")
                self.run = 2.2
        elif s == "seek":
            f = self.target_food
            if f not in self.foods:
                self.set_state("idle", FPS // 2)
            else:
                fgx, fgy = f.ground
                side = 1 if fgx > self.ground[0] else -1
                goal = self.clamp_pos(fgx - W / 2 - side * MOUTH, fgy - FEET)
                if self.walk_toward(*goal, speed * 1.4):
                    self.facing = 1 if fgx > self.ground[0] else -1
                    self.eating_kind = f.kind
                    f.taken = True
                    f.hide()  # it's in the hamster's paws now
                    self.set_state("eat", int(FPS * 2.5))
        elif s == "eat":
            self.state_t -= 1
            if self.state_t <= 0:
                f = self.target_food
                if f in self.foods:
                    info = FOODS[f.kind]
                    if self.hunger >= OVERFED:
                        self.set_chub(self.chub + info["chub"])
                    self.hunger = clamp(self.hunger + info["hunger"])
                    self.happy = clamp(self.happy + info["happy"])
                    self.foods.remove(f)
                    f.close()
                    f.deleteLater()
                    if f.kind == "raspberry":
                        self.add_hearts(3)
                    self.say("yum!" if self.hunger < 95 else "so full...", 1.8)
                self.target_food = None
                self.set_state("idle", FPS)
        elif s == "sleep":
            if self.energy >= 100:
                self.say("*yawn*")
                self.set_state("idle", FPS * 2)
            elif self.frame % (FPS * 4) == 0 and not self.bubble:
                self.bubble = ("zzz", FPS * 3, None)
        elif s == "happy":
            self.state_t -= 1
            if self.state_t <= 0:
                self.set_state("idle", FPS)
        elif s == "land":
            # set down after being carried: a small plop, no falling
            self.lift = max(0.0, self.lift - 3)
            if self.lift == 0:
                self.say(random.choice(("oof!", "wheee", "new spot!", "thanks for the lift")), 1.6)
                self.set_state("idle", FPS)

        self.poll_update()

        # queued lines (the note, milestones) go first, then idle chatter
        if not self.bubble and self.queue:
            self.say(self.queue.popleft())
        elif not self.bubble and not self.queue and self.ask_after_queue:
            self.ask_after_queue = False
            QTimer.singleShot(600, self.ask_owner)
        elif self.state in ("idle", "walk") and not self.bubble:
            self.chat_cd -= 1
            if self.chat_cd <= 0:
                if self.chatty:
                    self.chatter()
                self.chat_cd = random.randint(FPS * 35, FPS * 90)

        if self.blink_t > 0:
            self.blink_t -= 1
        elif random.random() < 0.012:
            self.blink_t = 4

        if self.bubble:
            kind, t, payload = self.bubble
            self.bubble = (kind, t - 1, payload) if t > 1 else None
        for h in self.hearts:
            h[1] -= 1.1
            h[2] -= 5
        self.hearts = [h for h in self.hearts if h[2] > 0]

        self.move(int(self.px), int(self.py))
        self.update_mask()
        self.update()

    def current_sprite(self):
        """(sprite name, vertical offset in px)"""
        s, f = self.state, self.frame
        if s in ("walk", "seek", "follow"):
            return f"walk_{(f // (3 if self.run > 1 else 4)) % 4}", 0
        if s == "eat":
            return f"eat_{self.eating_kind}_{(f // 6) % 2}", 0
        if s == "groom":
            return f"groom_{(f // 7) % 2}", 0
        if s == "stretch":
            return "stretch_0", 0
        if s == "startled":
            return "alert_0", -abs(math.sin(self.state_t * 0.22)) * 10
        if s == "sleep":
            return f"sleep_{(f // 40) % 2}", 0
        if s == "dragged":
            return "dangle_0", 0
        if s == "land":
            return ("dangle_0" if self.lift > 4 else "idle_0"), -self.lift
        if s == "happy":
            return "happy_0", -abs(math.sin(f * 0.35)) * 12
        if self.happy < 30:
            return "sad_0", 0
        return f"idle_{1 if self.blink_t else 0}", 0

    # ---- speech bubble geometry (shared by painting and the click mask)
    def bubble_rect(self):
        if not self.bubble:
            return None
        kind, _, payload = self.bubble
        bottom = H - SPRITE_H - 8
        if kind == "stats":
            w, h = 150, 60
        elif kind == "text":
            br = self._fm.boundingRect(QRect(0, 0, BUBBLE_MAX_W - 18, 400),
                                       tflags(Qt.TextFlag.TextWordWrap, Qt.AlignmentFlag.AlignCenter),
                                       payload)
            w, h = br.width() + 18, br.height() + 10
        else:
            w, h = 40, 32
        return QRectF(round((W - w) / 2), bottom - h, round(w), h)

    def update_mask(self):
        """Only the hamster (and its bubble) catch clicks; the rest of the window is click-through."""
        name, dy = self.current_sprite()
        br = self.bubble_rect()
        key = (name, self.facing, self.variant, int(dy), None if br is None else br.getRect(),
               bool(self.hearts), self.state == "dragged")
        if key == self._mask_key:
            return
        self._mask_key = key
        region = self.sprites.shape(name, self.facing, self.variant).translated(SX, H - SPRITE_H + int(dy))
        if self.state != "dragged":
            region = region.united(QRegion(int(W / 2 - 48), FEET - 8, 96, 16))  # ground shadow
        if br is not None:
            region = region.united(QRegion(br.toRect().adjusted(-3, -3, 3, 10)))
        if self.hearts:
            region = region.united(QRegion(0, FEET - 120, W, 70))
        self.setMask(region)

    # ---- painting
    def paintEvent(self, _):
        p = QPainter(self)
        name, dy = self.current_sprite()
        if self.state != "dragged":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 55))
            p.drawEllipse(QPointF(W / 2 + 4 * self.facing, FEET - 1), 42 + 5 * self.chub_tier, 6)
        p.drawPixmap(QPointF(SX, H - SPRITE_H + dy), self.sprites.get(name, self.facing, self.variant))

        for x, y, a in self.hearts:
            draw_heart(p, x, y, 2, a)
        if self.bubble:
            self._paint_bubble(p, *self.bubble)

    def _paint_bubble(self, p, kind, _t, payload):
        rect = self.bubble_rect()
        p.setFont(ui_font(12))

        # square parchment panel with a stepped pixel tail
        tail_x = round(W / 2 + 10 * self.facing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(INK))
        p.drawRect(rect.adjusted(-2, -2, 2, 2))
        for i, wdt in enumerate((10, 6, 2)):
            p.drawRect(QRectF(tail_x - wdt / 2, rect.bottom() + 2 + i * 2, wdt, 2))
        p.setBrush(QColor("#E2D1A6"))
        p.drawRect(rect)
        for i, wdt in enumerate((6, 2)):
            p.drawRect(QRectF(tail_x - wdt / 2, rect.bottom() + i * 2, wdt, 2))

        p.setPen(QColor(INK))
        center = Qt.AlignmentFlag.AlignCenter
        if kind == "text":
            p.drawText(rect.adjusted(9, 5, -9, -5),
                       tflags(Qt.TextFlag.TextWordWrap, center), payload)
        elif kind == "zzz":
            p.drawText(rect, center, "z z Z")
        elif kind == "hungry":
            pm = self.sprites.food["raspberry"]
            p.drawPixmap(QPointF(rect.center().x() - Food.SIZE / 2,
                                 rect.center().y() - Food.SIZE / 2 + 3), pm)
        elif kind == "stats":
            p.setFont(ui_font(11))
            p.drawText(QRectF(rect.left(), rect.top() + 3, rect.width(), 14), center,
                       f"{self.name} · day {self.days + 1}")
            p.setFont(ui_font(9, bold=False))
            rows = (("food", self.hunger, "#C7812E"), ("joy", self.happy, "#B8343A"),
                    ("rest", self.energy, "#4F7A8C"))
            for i, (label, val, col) in enumerate(rows):
                y = rect.top() + 21 + i * 12
                p.setPen(QColor(INK))
                p.drawText(QRectF(rect.left() + 7, y - 2, 30, 12),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
                bar = QRectF(rect.left() + 38, y, rect.width() - 46, 8)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(INK))
                p.drawRect(bar.adjusted(-1, -1, 1, 1))
                p.setBrush(QColor("#BFAE85"))
                p.drawRect(bar)
                p.setBrush(QColor(col))
                p.drawRect(QRectF(bar.left(), bar.top(), round(bar.width() * val / 100), bar.height()))

    # ---- mouse
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.press_pos = global_pos(e)
            self.drag_off = self.press_pos - self.pos()

    def mouseMoveEvent(self, e):
        if self.drag_off is None:
            return
        gp = global_pos(e)
        if self.state != "dragged" and (gp - self.press_pos).manhattanLength() > 5:
            if self.state == "eat" and self.target_food in self.foods:
                self.target_food.taken = False
                self.target_food.show()  # drops its food
            self.set_state("dragged")
            self.say("eep!", 1)
        if self.state == "dragged":
            pos = gp - self.drag_off
            # carried: drawn 14px higher than where it will be set down
            self.px, self.py = self.clamp_pos(pos.x(), pos.y() + 14)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self.drag_off is None:
            return
        self.drag_off = None
        self.swings.clear()
        if self.state == "dragged":
            self.lift = 14.0
            self.set_state("land")
        else:
            self.pet()

    def pet(self):
        if self.state == "sleep":
            self.bubble = ("zzz", FPS * 2, None)
            return
        if self.state in ("eat", "land", "dragged"):
            return
        self.happy = clamp(self.happy + 6)
        self.add_hearts()
        self.set_state("happy", int(FPS * 1.2))

    def contextMenuEvent(self, e):
        m = QMenu()
        feed = m.addMenu("Feed")
        for kind, info in FOODS.items():
            feed.addAction(info["label"], lambda k=kind: self.spawn_food(k))
        m.addAction("Pet", self.pet)
        if self.state == "sleep":
            m.addAction("Wake up", self.wake)
        else:
            m.addAction("Go to sleep", lambda: self.set_state("sleep"))
        m.addAction("How are you?", lambda: setattr(self, "bubble", ("stats", FPS * 5, None)))
        m.addAction("Say something", self.chatter)
        if self.hat_unlocked:
            hat = QAction("Party hat", m)
            hat.setCheckable(True)
            hat.setChecked(self.wearing_hat)
            hat.toggled.connect(self.set_hat)
            m.addAction(hat)
        m.addSeparator()
        names = m.addMenu("Names")
        names.addAction(f"Rename {self.name}...", self.rename)
        names.addAction("What should I call you?...", self.ask_owner)
        if read_message():
            m.addAction("Read the note again", lambda: self.say_later(*read_message()))
        hide = m.addMenu("Hide for a while")
        for label, minutes in (("30 minutes", 30), ("1 hour", 60), ("2 hours", 120)):
            hide.addAction(label, lambda mins=minutes: self.hide_all("manual", mins))
        quiet = QAction("Quiet mode", m)
        quiet.setCheckable(True)
        quiet.setChecked(not self.chatty)
        quiet.toggled.connect(self.set_quiet)
        m.addAction(quiet)
        if IS_LINUX:
            auto = QAction("Start on login", m)
            auto.setCheckable(True)
            auto.setChecked(os.path.exists(AUTOSTART_FILE))
            auto.toggled.connect(set_autostart)
            m.addAction(auto)
        if updates_possible():
            m.addAction(f"Check for updates (v{VERSION})", lambda: self.check_for_updates(True))
        m.addAction("Say goodbye (quit)", self.quit)
        m.exec(e.globalPos())

    def set_hat(self, on):
        self.hat_on = on
        if not on:
            self.party_date = None
        self.save()
        self.say("party time!" if on else "hat off")

    def set_quiet(self, on):
        self.chatty = not on
        self.save()
        self.say("i'll keep it down" if on else "yay, talking!")

    def wake(self):
        self.say("*yawn*")
        self.set_state("idle", FPS * 2)

    def rename(self):
        name, ok = QInputDialog.getText(None, "Rename", "New name:", text=self.name)
        if ok and name.strip():
            self.name = name.strip()[:16]
            self.save()
            self.say(f"i'm {self.name}!")

    def ask_owner(self):
        self.asked_owner = True
        name, ok = QInputDialog.getText(None, self.name, f"What should {self.name} call you?",
                                        text=self.owner)
        if ok:
            self.owner = name.strip()[:20]
            self.say(f"nice to meet you, {self.you}!" if self.owner else "okay, friend!")
        self.save()

    def quit(self):
        self.save()
        for f in self.foods:
            f.close()
        self.app.quit()


def set_autostart(enabled):
    if enabled:
        os.makedirs(os.path.dirname(AUTOSTART_FILE), exist_ok=True)
        with open(AUTOSTART_FILE, "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Desktop Hamster\n"
                    f"Exec=python3 {os.path.abspath(__file__)}\n"
                    "X-GNOME-Autostart-enabled=true\nNoDisplay=false\n")
    elif os.path.exists(AUTOSTART_FILE):
        os.remove(AUTOSTART_FILE)


# =========================================================================== updates from GitHub
# The repo holds this folder's files. To publish an update: change the files, raise the number
# in version.json (its "notes" are what the hamster says afterwards), and push.

def update_urls():
    override = os.environ.get("HAMSTER_UPDATE_URLS")   # "version-url|zip-url", for testing
    if override:
        return tuple(override.split("|", 1))
    if not UPDATE_REPO:
        return None
    return (f"https://raw.githubusercontent.com/{UPDATE_REPO}/{UPDATE_BRANCH}/version.json",
            f"https://github.com/{UPDATE_REPO}/archive/refs/heads/{UPDATE_BRANCH}.zip")


def updates_possible():
    # a copy with a .git folder is someone's working copy: never overwrite it
    return (update_urls() is not None and os.access(HERE, os.W_OK)
            and not os.path.exists(os.path.join(HERE, ".git")))


def _fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": APP_ID})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def find_update():
    """Download a newer version and check that it runs.

    Returns (folder with the new files, temp dir to delete afterwards), or None if up to date.
    Raises if the download is broken or the new version fails its self-test.
    """
    version_url, zip_url = update_urls()
    latest = int(json.loads(_fetch(version_url).decode("utf-8")).get("version", 0))
    if latest <= VERSION:
        return None
    tmp = tempfile.mkdtemp(prefix="hamster-update-")
    try:
        zpath = os.path.join(tmp, "update.zip")
        with open(zpath, "wb") as f:
            f.write(_fetch(zip_url, 120))
        with zipfile.ZipFile(zpath) as z:
            z.extractall(os.path.join(tmp, "x"))
        root = next((d for d, _, files in os.walk(os.path.join(tmp, "x")) if "hamster.py" in files), None)
        if root is None or read_version(os.path.join(root, "version.json"))[0] <= VERSION:
            raise RuntimeError("not a newer hamster")
        # run the new version headless, with a throwaway home folder, before trusting it
        home = os.path.join(tmp, "home")
        os.makedirs(home)
        env = dict(os.environ, HOME=home, QT_QPA_PLATFORM="offscreen")
        env.pop("HAMSTER_UPDATE_URLS", None)
        test = subprocess.run([sys.executable, os.path.join(root, "hamster.py"), "--selftest"],
                              env=env, capture_output=True, timeout=120)
        if test.returncode != 0:
            raise RuntimeError("new version failed its self-test")
        return root, tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def apply_update(root):
    """Copy the new files over the installed ones (hamster.py last)."""
    for name in sorted(os.listdir(root), key=lambda n: n == "hamster.py"):
        src, dst = os.path.join(root, name), os.path.join(HERE, name)
        if name.startswith(".") or (name in UPDATE_KEEP and os.path.exists(dst)):
            continue
        new, old = dst + ".new", dst + ".old"
        if os.path.isdir(src):
            shutil.rmtree(new, ignore_errors=True)
            shutil.copytree(src, new)
            shutil.rmtree(old, ignore_errors=True)
            if os.path.exists(dst):
                os.rename(dst, old)
            os.rename(new, dst)
            shutil.rmtree(old, ignore_errors=True)
        else:
            shutil.copy2(src, new)
            os.replace(new, dst)


def selftest(app):
    """Used by the updater: build the hamster and run it briefly without a screen."""
    h = Hamster(app, Sprites())
    for t in (h.tick_timer, h.stat_timer, h.save_timer):
        t.stop()
    for kind in FOODS:
        h.spawn_food(kind)
    for i in range(900):
        h.tick()
        if i % 30 == 0:
            h.stat_tick()
            h.grab()
    print("selftest ok")


# =========================================================================== one hamster only

SOCKET_NAME = f"{APP_ID}-{os.getuid() if hasattr(os, 'getuid') else 'user'}"


def already_running():
    """If another copy is running, poke it (it says hi) and return True."""
    if QLocalSocket is None:
        return False
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if sock.waitForConnected(400):
        sock.write(b"poke")
        sock.flush()
        sock.waitForBytesWritten(400)
        sock.disconnectFromServer()
        return True
    return False


def listen_for_pokes(hamster):
    if QLocalServer is None:
        return None
    QLocalServer.removeServer(SOCKET_NAME)   # clear a stale socket left by a crash
    server = QLocalServer()
    if not server.listen(SOCKET_NAME):
        return None

    def on_connect():
        conn = server.nextPendingConnection()
        if conn is not None:
            conn.disconnected.connect(conn.deleteLater)
            conn.close()
        hamster.poke()
    server.newConnection.connect(on_connect)
    return server


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setQuitOnLastWindowClosed(False)
    if "--selftest" in sys.argv:
        selftest(app)
        return
    if already_running():
        return
    sprites = Sprites()
    h = Hamster(app, sprites)
    app.poke_server = listen_for_pokes(h)   # keep a reference so it stays alive
    app.aboutToQuit.connect(h.save)
    signal.signal(signal.SIGINT, lambda *_: h.quit())
    keepalive = QTimer()
    keepalive.timeout.connect(lambda: None)
    keepalive.start(250)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
