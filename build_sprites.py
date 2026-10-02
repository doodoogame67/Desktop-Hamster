#!/usr/bin/env python3
"""
Renders the hamster and food sprites used by hamster.py.

Low-poly faceted meshes + a coarse "pixel mosaic" texture defined in 3D + warm key
light with blue ambient shadows, in the style of Valheim's creatures.

Needs numpy and Pillow. Only required if you want to change the art:
    python3 build_sprites.py
writes PNGs into ./sprites/
"""
import math
import os

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites")

# sprite canvas (logical px) - must match hamster.py
W, SPRITE_H = 160, 116
ANCHOR = (W / 2, 102)
# tall canvas = the whole hamster window: standing up, on the wheel, in the nest, and the items
BIG_W, BIG_H = 220, 180
BIG_ANCHOR = (BIG_W / 2, 166)
FOOD_SIZE = 34
DPR = 2          # sprites are saved at 2x for sharp HiDPI/Retina display
SSAA = 3         # supersampling for smooth edges
PPU = 34.0       # logical px per model unit (hamster)
TEX = 0.10      # texel size in model units: the pixel-mosaic grain

YAW = 34         # degrees the hamster is turned toward the viewer
PITCH = 16       # camera looks down this much

# --------------------------------------------------------------------------- palette (sRGB 0..1)
def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])

GOLD = rgb("#C08A4E")
DARK = rgb("#7E5030")
CREAM = rgb("#F0E4CC")
PINK = rgb("#DDA49B")
EARIN = rgb("#D08E88")
EYE = rgb("#140E0C")
NOSE = rgb("#C07472")
RASP = rgb("#B3263A")
RASP_D = rgb("#7C1426")
LEAF = rgb("#5E7B34")
CAP = rgb("#A8322A")
STEM = rgb("#E6DAC0")
CARROT = rgb("#DB7A2C")
HAT1 = rgb("#2F7F8C")
HAT2 = rgb("#E0B33C")
POM = rgb("#F3EBDD")
WOOD = rgb("#B98A55")
WOOD_D = rgb("#7A5632")
STAND = rgb("#5C4630")
STRAW = rgb("#D9B978")
STRAW_D = rgb("#A8823F")

KEY_DIR = np.array([0.55, 0.72, 0.55]); KEY_DIR /= np.linalg.norm(KEY_DIR)
KEY_COL = np.array([1.00, 0.91, 0.76]) * 1.08
SKY_COL = np.array([0.40, 0.56, 0.78])
BOUNCE_COL = np.array([0.34, 0.27, 0.20])

MATS = ["fur", "muzzle", "pink", "earin", "eye", "lid", "nose",
        "rasp", "leaf", "cap", "stem", "carrot", "hat", "pom", "wood", "wood2", "stand", "straw"]
MID = {m: i + 1 for i, m in enumerate(MATS)}


# --------------------------------------------------------------------------- geometry
def rot_x(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

def rot_y(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

def rot_z(d):
    a = math.radians(d); c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


_SPHERES = {}

def unit_sphere(detail):
    """Geodesic sphere: icosahedron subdivided `detail` times. Even triangular facets."""
    if detail in _SPHERES:
        return _SPHERES[detail]
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t),
         (0, -1, -t), (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4),
         (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8),
         (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    for _ in range(detail):
        cache, NF = {}, []
        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = V[a] + V[b]
                V.append(m / np.linalg.norm(m))
                cache[k] = len(V) - 1
            return cache[k]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            NF += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = NF
    _SPHERES[detail] = (np.array(V), np.array(F, int))
    return _SPHERES[detail]


class Part:
    def __init__(self, c, r, mat, R=None, lon=10, lat=7, taper=0.0, egg=0.0):
        self.c = np.array(c, float)
        self.rest = self.c.copy()      # texture is anchored to the rest position
        self.r = np.array(r, float)
        self.mat = mat
        self.R = np.eye(3) if R is None else R
        self.detail = 1
        self.taper, self.egg = taper, egg

    def triangles(self):
        U, T = unit_sphere(self.detail)
        U = U.copy()
        rng = np.random.default_rng(len(U) + int(abs(self.rest).sum() * 1000) % 9973)
        U *= 1 + rng.uniform(-0.035, 0.035, (len(U), 1))
        if self.egg:
            s = 1 - self.egg * U[:, 0]
            U[:, 1] *= s
            U[:, 2] *= s
        if self.taper:
            s = 1 - self.taper * np.clip(U[:, 0], 0, 1)
            U[:, 1] *= s
            U[:, 2] *= s
        local = U * self.r
        world = local @ self.R.T + self.c
        rest = local + self.rest
        return world[T], rest[T], self.c


class Cone(Part):
    """Low-poly cone (party hat). `c` is the centre of the base."""

    def __init__(self, base, height, radius, mat, R=None, seg=9):
        super().__init__(base, (radius, height, radius), mat, R)
        self.h, self.rad, self.seg = height, radius, seg

    def triangles(self):
        seg = self.seg
        V = [(0, self.h, 0)]
        V += [(self.rad * math.cos(2 * math.pi * i / seg), 0, self.rad * math.sin(2 * math.pi * i / seg))
              for i in range(seg)]
        V.append((0, 0, 0))
        V = np.array(V, float)
        T = [(0, 1 + i, 1 + (i + 1) % seg) for i in range(seg)]
        T += [(seg + 1, 1 + (i + 1) % seg, 1 + i) for i in range(seg)]
        T = np.array(T)
        world = V @ self.R.T + self.c
        rest = V + self.rest
        return world[T], rest[T], self.c + self.R @ np.array([0, self.h / 4, 0])


class Box(Part):
    """Rectangular block. `r` holds the half-sizes along its own x, y, z."""

    _T = np.array([q for a, b, c, d in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6),
                                        (0, 2, 6, 4), (1, 3, 7, 5)) for q in ((a, b, c), (a, c, d))])

    def triangles(self):
        V = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], float) * self.r
        world = V @ self.R.T + self.c
        rest = V + self.rest
        return world[self._T], rest[self._T], self.c


def pose(parts, pivot, R, dy=0.0):
    pivot = np.array(pivot, float)
    for p in parts:
        p.c = R @ (p.c - pivot) + pivot
        p.c[1] += dy
        p.R = R @ p.R


# --------------------------------------------------------------------------- the hamster
def party_hat(base, R):
    base = np.array(base, float)
    h = 0.70
    return [Cone(base, h, 0.25, "hat", R=R),
            Part(base + R @ np.array([0, h, 0]), (0.085, 0.085, 0.085), "pom", lon=6, lat=4)]


def hamster(pose_name, frame=0, held=None, hat=False, chub=0):
    """Build the hamster's parts. chub: 0 normal, 1 chubby, 2 very round."""
    k = chub
    closed = pose_name in ("blink", "happy", "groom", "stretch", "sleep", "roll", "rollside")
    sploot = pose_name == "sploot"
    on_back = pose_name in ("roll", "rollside")

    # ---- sleeping: curled up loaf
    if pose_name == "sleep":
        br = 0.04 * frame
        ry = (0.70 + br) * (1 + 0.12 * k)
        body = [Part((-0.15 - 0.03 * k, 0.02 + ry, 0), (1.32 * (1 + 0.07 * k), ry, 1.05 * (1 + 0.17 * k)),
                     "fur", egg=0.12)]
        up = ry - 0.70
        head = [Part((1.02, 0.78 + up, 0), (0.70, 0.62, 0.70), "fur"),
                Part((1.25, 0.58 + up, 0.36 + 0.05 * k), (0.46, 0.36, 0.40), "fur"),
                Part((1.25, 0.58 + up, -0.36 - 0.05 * k), (0.46, 0.36, 0.40), "fur"),
                Part((1.58, 0.60 + up, 0), (0.33, 0.26, 0.30), "muzzle"),
                Part((1.88, 0.62 + up, 0), (0.07, 0.06, 0.08), "nose")]
        for z in (0.44, -0.44):
            head += [Part((0.72, 1.30 + up, z), (0.11, 0.20, 0.21), "fur", R=rot_z(40)),
                     Part((0.78, 1.28 + up, z), (0.05, 0.15, 0.15), "earin", R=rot_z(40)),
                     Part((1.40, 0.92 + up, z * 0.97), (0.13, 0.025, 0.08), "lid")]
        if hat:
            head += party_hat((0.92, 1.33 + up, 0), rot_z(38))
        return body + head + [Part((-1.52 - 0.1 * k, 0.55 + up, 0), (0.13, 0.11, 0.11), "pink")]

    # ---- awake poses
    stretch = pose_name == "stretch"
    rx, ry, rz = 1.25 * (1 + 0.07 * k), 0.84 * (1 + 0.12 * k), 0.98 * (1 + 0.17 * k)
    if stretch:
        rx, ry = rx * 1.14, ry * 0.86
    if sploot:                           # pancake: flat on its belly, legs out
        rx, ry, rz = rx * 1.10, ry * 0.72, rz * 1.08
    up = ry - 0.84                       # head rides higher on a rounder body
    fwd = (rx - 1.25) * 0.6 + (0.22 if stretch else 0) + (0.2 if sploot else 0)
    body = [Part((-0.15 - 0.03 * k, 0.02 + ry, 0), (rx, ry, rz), "fur", egg=0.14),
            Part((-1.55 - (rx - 1.25) * 0.9, 0.85 + up * 0.6, 0), (0.14, 0.12, 0.12), "pink")]

    eat = pose_name == "eat"
    cheek = np.array((0.60, 0.52, 0.56) if eat else (0.50, 0.42, 0.42)) * (1 + 0.12 * k)
    cz = (0.48 if eat else 0.38) + 0.06 * k
    hx, hy = 1.02 + fwd, 1.30 + up - (0.30 if sploot else 0)
    head = [
        Part((hx, hy, 0), (0.74, 0.70, 0.72), "fur"),
        Part((hx + 0.26, hy - 0.30, cz), cheek, "fur"),
        Part((hx + 0.26, hy - 0.30, -cz), cheek, "fur"),
        Part((hx + 0.70, hy - 0.18, 0), (0.34, 0.28, 0.30), "muzzle"),
        Part((hx + 1.02, hy - 0.13, 0), (0.075, 0.065, 0.085), "nose"),
    ]
    for z in (0.46, -0.46):
        if pose_name == "sad":      # ears folded back
            head += [Part((hx - 0.30, hy + 0.55, z), (0.11, 0.24, 0.22), "fur", R=rot_z(62)),
                     Part((hx - 0.25, hy + 0.56, z), (0.05, 0.18, 0.16), "earin", R=rot_z(62))]
        else:
            tall = 1.25 if pose_name == "alert" else 1.0
            head += [Part((hx - 0.20, hy + 0.62 + 0.06 * (tall - 1), z), (0.11, 0.25 * tall, 0.23), "fur", R=rot_z(10)),
                     Part((hx - 0.14, hy + 0.61 + 0.06 * (tall - 1), z), (0.05, 0.19 * tall, 0.17), "earin", R=rot_z(10))]
        if closed:
            head.append(Part((hx + 0.50, hy + 0.12, z * 0.95), (0.13, 0.025, 0.08), "lid"))
        else:
            er = {"dangle": 0.19, "alert": 0.20, "sad": 0.13}.get(pose_name, 0.16)
            ey = hy + (0.08 if pose_name == "sad" else 0.14)
            head.append(Part((hx + 0.48, ey, z * 0.95), (er * 0.9, er, er * 0.8), "eye"))
    hat_parts = []
    if hat and pose_name == "roll":      # it fell off; it sits on the ground beside the hamster
        hat_parts = party_hat((-0.9, 0.0, 1.25), rot_z(14))
    elif hat:
        head += party_hat((hx - 0.04, hy + 0.63, 0), rot_z(-12))

    if pose_name == "sad":
        pose(head, (hx - 0.4, hy - 0.3, 0), rot_z(-13), dy=-0.05)
    if pose_name == "alert":
        pose(head, (hx - 0.4, hy - 0.3, 0), rot_z(6), dy=0.05)
    if stretch:
        pose(head, (hx - 0.4, hy - 0.3, 0), rot_z(10))

    fz = 1 + 0.12 * k
    feet = []
    if pose_name == "dangle" or on_back:
        wig = (0.14 if frame else -0.14) if pose_name == "roll" else 0.0
        for sgn, z in ((1, 0.42), (-1, -0.42)):
            feet.append(Part((1.00 + wig * sgn, 0.02, z * fz), (0.12, 0.28, 0.12), "pink"))
        for sgn, z in ((1, 0.58), (-1, -0.58)):
            feet.append(Part((-0.70 - wig * sgn, 0.00, z * 0.85 * fz), (0.15, 0.32, 0.15), "pink"))
    elif sploot:
        for z in (0.50, -0.50):
            feet.append(Part((hx + 0.72, 0.09, z * fz), (0.30, 0.09, 0.13), "pink"))
            feet.append(Part((-0.15 - rx - 0.12, 0.09, z * fz), (0.36, 0.09, 0.16), "pink"))
    else:
        ph = frame * math.pi / 2 if pose_name == "walk" else None
        sit = pose_name in ("eat", "groom", "stand")
        for side, z in ((1, 0.42), (-1, -0.42)):
            dx = dy = 0.0
            if ph is not None:
                s = math.sin(ph + (0 if side > 0 else math.pi))
                dx, dy = 0.17 * s, max(0.0, 0.08 * math.cos(ph + (0 if side > 0 else math.pi)))
            if stretch:
                dx = 0.55
            if not sit:
                feet.append(Part((0.80 + dx + fwd * 0.5, 0.17 + dy, z * 0.85 * fz), (0.20, 0.15, 0.14), "pink"))
        for side, z in ((1, 0.60), (-1, -0.60)):
            dx = dy = 0.0
            if ph is not None:
                s = math.sin(ph + (math.pi if side > 0 else 0))
                dx, dy = 0.17 * s, max(0.0, 0.08 * math.cos(ph + (math.pi if side > 0 else 0)))
            if stretch:
                dx = -0.25
            feet.append(Part((-0.72 + dx, 0.14 + dy, z * 0.8 * fz), (0.30, 0.13, 0.17), "pink"))

    upper = body + head
    if on_back:
        everything = upper + feet
        pivot = (0, 0.02 + ry, 0)
        if pose_name == "rollside":      # halfway: lying on its side, belly toward the viewer
            pose(everything, pivot, rot_x(-90), dy=rz - ry)
        else:                            # on its back, belly up, paws in the air
            pose(everything, pivot, rot_x(180))
            lift = 0.74 - head[0].c[1]   # the head rests on the ground instead of sinking into it
            for q in head:
                q.c[1] += max(0.0, lift)
        return everything + hat_parts
    if pose_name == "stand":             # up on its hind legs, paws at its chest, sniffing
        paws = [Part((hx + 0.50, hy - 0.72, z), (0.12, 0.16, 0.11), "pink") for z in (0.22, -0.22)]
        pose(upper + paws, (-0.9, 0.1, 0), rot_z(48))
        pose(head, head[0].c.copy(), rot_z(-30 + (7 if frame else -3)))
        everything = upper + feet + paws
        for q in everything:
            q.c[0] += 0.55               # keep it over its shadow
        return everything
    if pose_name == "walk":
        for p in upper:
            p.c[1] += 0.05 * abs(math.sin(frame * math.pi / 2))

    if pose_name in ("eat", "groom"):
        # sit up on the haunches; paws (and food) move with the upper body
        if eat:
            paws = [Part((hx + 0.76, hy - 0.58, z), (0.13, 0.17, 0.11), "pink") for z in (0.22, -0.22)]
            extra = food(held, scale=0.46, at=(hx + 1.00, hy - 0.68, 0))
            ang = 11 + 3 * frame
        else:   # grooming: paws rub the face
            px, py, pz = (hx + 0.98, hy - 0.22, 0.20) if frame == 0 else (hx + 0.90, hy + 0.04, 0.26)
            paws = [Part((px, py, z), (0.14, 0.18, 0.12), "pink") for z in (pz, -pz)]
            extra = []
            ang = 14
        pose(upper + paws + extra, (-0.9, 0.1, 0), rot_z(ang))
        return upper + feet + paws + extra
    return upper + feet


# --------------------------------------------------------------------------- items
WHEEL_C = (0.2, 2.42)      # axle position (x, y); the hamster runs in the x-y plane
WHEEL_R = 2.0
WHEEL_HALF_W = 1.14
SLATS = 16
WHEEL_FLOOR = WHEEL_C[1] - WHEEL_R + 0.07     # height of the running surface at the bottom


def wheel(frame=0):
    """An open wooden wheel: rungs between two side rings, on a back stand.

    Rungs with gaps keep the hamster visible. 4 frames = one rung spacing.
    """
    cx, cy = WHEEL_C
    seg = 2 * math.pi / SLATS
    phase = -frame * seg / 4                  # the bottom moves backwards under the feet
    parts = []
    for i in range(SLATS):
        a = i * seg + phase
        mid = (cx + WHEEL_R * math.sin(a), cy - WHEEL_R * math.cos(a))
        R = rot_z(math.degrees(a))
        q = Box((*mid, 0), (0.13, 0.07, WHEEL_HALF_W), "wood", R=R)             # rung
        q.rest = np.array((i * 3.0, 10.0, 0.0))
        parts.append(q)
        for z in (WHEEL_HALF_W, -WHEEL_HALF_W):                                  # side rings
            a2 = a + seg / 2
            q = Box((cx + WHEEL_R * math.sin(a2), cy - WHEEL_R * math.cos(a2), z),
                    (WHEEL_R * math.tan(seg / 2) * 1.04, 0.10, 0.07), "wood2", R=rot_z(math.degrees(a2)))
            q.rest = np.array((i * 3.0, 30.0 + z, 0.0))
            parts.append(q)
    zb = -WHEEL_HALF_W - 0.09
    for j in range(3):                        # spokes on the back
        q = Box((cx, cy, zb), (WHEEL_R, 0.10, 0.05), "wood2", R=rot_z(math.degrees(phase * 4) + j * 60))
        q.rest = np.array((j * 5.0, 20.0, 0.0))
        parts.append(q)
    parts.append(Part((cx, cy, zb + 0.02), (0.26, 0.26, 0.16), "stand"))
    parts.append(Box((cx, cy / 2, zb - 0.14), (0.13, cy / 2, 0.06), "stand"))            # post
    parts.append(Box((cx, 0.07, zb - 0.14), (1.45, 0.07, 0.13), "stand"))                # base
    parts.append(Box((cx, 0.06, -0.1), (0.15, 0.06, WHEEL_HALF_W + 0.3), "stand"))       # foot
    return parts


def hamster_on_wheel(frame, hat, chub):
    ham = hamster("walk", frame, hat=hat, chub=chub)
    for q in ham:
        q.c[1] += WHEEL_FLOOR
    return wheel(frame) + ham


NEST_C, NEST_RX, NEST_RZ, NEST_Z = 0.1, 2.3, 1.45, -0.3


def nest():
    """A ring of straw clumps around a straw floor."""
    rng = np.random.default_rng(7)
    parts = [Part((NEST_C, 0.10, NEST_Z), (NEST_RX - 0.2, 0.14, NEST_RZ - 0.15), "straw")]
    n = 14
    for i in range(n):
        a = 2 * math.pi * i / n
        q = Part((NEST_C + NEST_RX * math.cos(a), 0.30 + rng.uniform(-0.04, 0.08), NEST_Z + NEST_RZ * math.sin(a)),
                 (0.66, 0.34 + rng.uniform(0, 0.08), 0.38), "straw",
                 R=rot_y(-(math.degrees(a) + 90)) @ rot_z(rng.uniform(-12, 12)))
        q.rest = rng.uniform(-40, 40, 3)
        parts.append(q)
    for i in range(9):                        # loose straws poking out
        a = rng.uniform(0, 2 * math.pi)
        q = Part((NEST_C + (NEST_RX + 0.15) * math.cos(a), 0.42 + rng.uniform(0, 0.15),
                  NEST_Z + (NEST_RZ + 0.1) * math.sin(a)), (0.48, 0.045, 0.045), "straw",
                 R=rot_y(rng.uniform(0, 360)) @ rot_z(rng.uniform(-35, 35)))
        q.rest = rng.uniform(-40, 40, 3)
        parts.append(q)
    return parts


def hamster_in_nest(frame, hat, chub):
    ham = hamster("sleep", frame, hat=hat, chub=chub)
    for q in ham:
        q.c[1] += 0.16
        q.c[0] += NEST_C
        q.c[2] += NEST_Z
    return nest() + ham


def food(kind, scale=1.0, at=(0, 0, 0)):
    at = np.array(at, float)
    parts = []
    if kind == "raspberry":
        rng = np.random.default_rng(3)
        for cx, cz, cr in ((0.0, 0.0, 0.42), (0.55, 0.30, 0.36), (0.15, 0.62, 0.34)):
            parts.append(Part((cx, cr, cz), (cr * 0.9, cr, cr * 0.9), "rasp", lon=7, lat=5))
            for _ in range(10):
                v = rng.normal(size=3); v /= np.linalg.norm(v)
                if v[1] < -0.3:
                    continue
                parts.append(Part((cx + v[0] * cr * 0.85, cr + v[1] * cr * 0.95, cz + v[2] * cr * 0.85),
                                  (0.12, 0.12, 0.12), "rasp", lon=5, lat=4))
            parts.append(Part((cx, cr * 2.0, cz), (0.14, 0.04, 0.14), "leaf", lon=5, lat=3))
    elif kind == "mushroom":
        parts += [Part((0, 0.32, 0), (0.17, 0.34, 0.17), "stem", lon=7, lat=5),
                  Part((0, 0.70, 0), (0.55, 0.30, 0.55), "cap", lon=10, lat=6)]
    else:  # carrot lying down, tip toward +x
        parts += [Part((0.0, 0.22, 0), (0.75, 0.22, 0.22), "carrot", lon=8, lat=6, taper=0.85)]
        for a, z in ((30, 0.05), (55, -0.08), (75, 0.02)):
            parts.append(Part((-0.82, 0.30, z), (0.28, 0.06, 0.06), "leaf", R=rot_z(180 - a), lon=5, lat=3))
    for p in parts:
        p.c = p.c * scale + at
        p.rest = p.rest * scale + at
        p.r = p.r * scale
    return parts


# --------------------------------------------------------------------------- rendering
def _hash(q, salt):
    q = q.astype(np.int64) + np.array(salt, np.int64)
    h = (q[..., 0] * 73856093) ^ (q[..., 1] * 19349663) ^ (q[..., 2] * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    h = h ^ (h >> 16)
    return (h & 0xFFFF) / 65535.0


def _albedo(mat, rest):
    q = np.floor(rest / TEX)
    c = (q + 0.5) * TEX
    n1, n2, n3 = _hash(q, (0, 0, 0)), _hash(q, (17, 31, 7)), _hash(q, (5, 11, 23))
    out = np.zeros(rest.shape)
    x, y = c[..., 0], c[..., 1]

    def mix(a, b, t):
        return a + (b - a) * t[..., None]

    m = mat == MID["fur"]
    if m.any():
        line = 0.76 + 0.40 * np.clip(x[m] - 0.35, 0, 1.1)
        belly = np.clip((line - y[m]) / 0.20 + (n1[m] - 0.5) * 1.0, 0, 1)
        dark = np.clip((y[m] - 1.40) / 0.40 + (n2[m] - 0.5) * 0.9, 0, 1) * (x[m] < 1.35)
        col = mix(np.broadcast_to(GOLD, (m.sum(), 3)), CREAM, belly)
        col = mix(col, DARK, dark * 0.75)
        out[m] = col
    flat = {"muzzle": CREAM, "pink": PINK, "earin": EARIN, "eye": EYE, "lid": DARK,
            "nose": NOSE, "leaf": LEAF, "stem": STEM, "carrot": CARROT,
            "wood": WOOD, "wood2": WOOD_D, "stand": STAND}
    for name, col in flat.items():
        mm = mat == MID[name]
        out[mm] = col
    mm = mat == MID["rasp"]
    out[mm] = mix(np.broadcast_to(RASP, (mm.sum(), 3)), RASP_D, (n1[mm] > 0.55).astype(float) * 0.8)
    mm = mat == MID["cap"]
    out[mm] = mix(np.broadcast_to(CAP, (mm.sum(), 3)), STEM, ((n1[mm] > 0.86) & (y[mm] > 0.75)).astype(float))
    mm = mat == MID["straw"]
    out[mm] = mix(np.broadcast_to(STRAW, (mm.sum(), 3)), STRAW_D, n1[mm] * 0.9)
    mm = mat == MID["hat"]
    stripe = (np.floor((y[mm] + 0.45 * x[mm]) / 0.14) % 2).astype(float)
    out[mm] = mix(np.broadcast_to(HAT1, (mm.sum(), 3)), HAT2, stripe)
    mm = mat == MID["pom"]
    out[mm] = POM
    mm = mat == MID["carrot"]
    out[mm] *= (0.85 + 0.15 * (np.floor(x[mm] / (TEX * 2)) % 2))[..., None]

    # per-texel variation: this is what makes it read as a pixel texture
    jitter = 0.87 + 0.24 * n3
    warm = (n2 - 0.5) * 0.06
    out = out * jitter[..., None]
    out[..., 0] += warm
    out[..., 2] -= warm
    return np.clip(out, 0, 1)


def render(parts, facing, w, h, anchor, ppu):
    S = DPR * SSAA
    Wp, Hp = int(w * S), int(h * S)
    R = rot_x(PITCH) @ rot_y(-YAW if facing > 0 else 180 + YAW)

    zbuf = np.full((Hp, Wp), -np.inf)
    rest_buf = np.zeros((Hp, Wp, 3))
    nrm_buf = np.zeros((Hp, Wp, 3))
    mat_buf = np.zeros((Hp, Wp), int)

    ax, ay = anchor[0] * S, anchor[1] * S
    for p in parts:
        tri_w, tri_r, center = p.triangles()
        cam = tri_w @ R.T
        cen = center @ R.T
        n = np.cross(cam[:, 1] - cam[:, 0], cam[:, 2] - cam[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        outward = np.einsum("ij,ij->i", n, cam.mean(axis=1) - cen) < 0
        n[outward] *= -1
        sx = ax + cam[..., 0] * ppu * S
        sy = ay - cam[..., 1] * ppu * S
        sz = cam[..., 2]
        mid = MID[p.mat]
        for t in range(len(cam)):
            if n[t, 2] < -0.05:
                continue  # facing away
            x0, x1 = int(max(0, np.floor(sx[t].min()))), int(min(Wp - 1, np.ceil(sx[t].max())))
            y0, y1 = int(max(0, np.floor(sy[t].min()))), int(min(Hp - 1, np.ceil(sy[t].max())))
            if x1 < x0 or y1 < y0:
                continue
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            (ax0, ax1, ax2), (ay0, ay1, ay2) = sx[t], sy[t]
            area = (ax1 - ax0) * (ay2 - ay0) - (ay1 - ay0) * (ax2 - ax0)
            if abs(area) < 1e-9:
                continue
            w0 = ((ax1 - X) * (ay2 - Y) - (ay1 - Y) * (ax2 - X)) / area
            w1 = ((ax2 - X) * (ay0 - Y) - (ay2 - Y) * (ax0 - X)) / area
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not inside.any():
                continue
            z = w0 * sz[t, 0] + w1 * sz[t, 1] + w2 * sz[t, 2]
            zb = zbuf[y0:y1 + 1, x0:x1 + 1]
            upd = inside & (z > zb)
            if not upd.any():
                continue
            zb[upd] = z[upd]
            rr = tri_r[t]
            rest = w0[..., None] * rr[0] + w1[..., None] * rr[1] + w2[..., None] * rr[2]
            rest_buf[y0:y1 + 1, x0:x1 + 1][upd] = rest[upd]
            nrm_buf[y0:y1 + 1, x0:x1 + 1][upd] = n[t]
            mat_buf[y0:y1 + 1, x0:x1 + 1][upd] = mid

    cover = mat_buf > 0
    col = np.zeros((Hp, Wp, 3))
    if cover.any():
        N = nrm_buf[cover]
        alb = _albedo(mat_buf[cover], rest_buf[cover])
        ndl = N @ KEY_DIR
        diff = np.clip((ndl + 0.10) / 1.10, 0, 1)
        hemi = 0.5 + 0.5 * N[:, 1]
        light = (KEY_COL * diff[:, None] * 0.92
                 + SKY_COL * (0.50 * hemi + 0.18)[:, None]
                 + BOUNCE_COL * (0.30 * (1 - hemi))[:, None])
        shaded = alb * light
        rim = np.clip(1 - N[:, 2], 0, 1) ** 3 * 0.22
        shaded += rim[:, None] * np.array([0.45, 0.62, 0.95])
        glossy = np.isin(mat_buf[cover], [MID["eye"], MID["nose"]])
        H = KEY_DIR + np.array([0, 0, 1.0]); H /= np.linalg.norm(H)
        spec = np.clip(N @ H, 0, 1) ** 30 * 1.3 * glossy
        shaded += spec[:, None]
        col[cover] = np.clip(shaded, 0, 1)

    # downsample
    a = cover.astype(float).reshape(h * DPR, SSAA, w * DPR, SSAA).mean(axis=(1, 3))
    c = (col * cover[..., None]).reshape(h * DPR, SSAA, w * DPR, SSAA, 3).sum(axis=(1, 3))
    cnt = cover.reshape(h * DPR, SSAA, w * DPR, SSAA).sum(axis=(1, 3))
    c = c / np.maximum(cnt, 1)[..., None]
    img = np.dstack([c, a])
    return Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA")


FOODS = ("raspberry", "mushroom", "carrot")

POSES = ([(f"walk_{f}", "walk", f, None) for f in range(4)]
         + [("idle_0", "idle", 0, None), ("idle_1", "blink", 0, None), ("happy_0", "happy", 0, None),
            ("dangle_0", "dangle", 0, None), ("sleep_0", "sleep", 0, None), ("sleep_1", "sleep", 1, None),
            ("groom_0", "groom", 0, None), ("groom_1", "groom", 1, None), ("sad_0", "sad", 0, None),
            ("stretch_0", "stretch", 0, None), ("alert_0", "alert", 0, None)]
         + [("roll_0", "roll", 0, None), ("roll_1", "roll", 1, None), ("rollside_0", "rollside", 0, None),
            ("sploot_0", "sploot", 0, None)]
         + [(f"eat_{k}_{f}", "eat", f, k) for k in FOODS for f in (0, 1)])
# rendered on the tall canvas
BIG_POSES = ([("stand_0", "stand", 0, None), ("stand_1", "stand", 1, None)]
             + [(f"wheel_{f}", "wheel", f, None) for f in range(4)]
             + [(f"nestsleep_{f}", "nest", f, None) for f in range(2)])


def variant(chub, hat):
    return f"c{chub}{'h' if hat else ''}"


def _render_job(job):
    name, pose_name, frame, held, chub, hat, big = job
    facings = ((1, "r"), (-1, "l"))
    if pose_name == "wheel":         # on an item it always faces right, so the item never flips
        parts, facings = hamster_on_wheel(frame, hat, chub), facings[:1]
    elif pose_name == "nest":
        parts, facings = hamster_in_nest(frame, hat, chub), facings[:1]
    else:
        parts = hamster(pose_name, frame, held, hat=hat, chub=chub)
    size = (BIG_W, BIG_H, BIG_ANCHOR) if big else (W, SPRITE_H, ANCHOR)
    for facing, suffix in facings:
        render(parts, facing, *size, PPU).save(
            os.path.join(OUT, f"{name}_{variant(chub, hat)}_{suffix}.png"))
    return name


def main():
    from multiprocessing import Pool
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(os.path.join(OUT, f))
    jobs = [(n, p, f, h, c, hat, big) for big, poses in ((False, POSES), (True, BIG_POSES))
            for (n, p, f, h) in poses for c in (0, 1, 2) for hat in (False, True)]
    with Pool() as pool:
        for i, _ in enumerate(pool.imap_unordered(_render_job, jobs), 1):
            if i % 20 == 0 or i == len(jobs):
                print(f"rendered {i}/{len(jobs)}")
    for k in FOODS:
        render(food(k), 1, FOOD_SIZE, FOOD_SIZE, (FOOD_SIZE / 2, FOOD_SIZE - 6), 26.0) \
            .save(os.path.join(OUT, f"food_{k}.png"))
    render(wheel(0), 1, BIG_W, BIG_H, BIG_ANCHOR, PPU).save(os.path.join(OUT, "item_wheel.png"))
    render(nest(), 1, BIG_W, BIG_H, BIG_ANCHOR, PPU).save(os.path.join(OUT, "item_nest.png"))
    print("done ->", OUT)


if __name__ == "__main__":
    main()
