#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Duo touchpad mode (2026-11-06, the keyboard-app goal: "the other screen ... is a touchpad with pan and zoom").
Turns ONE screen's touchscreen into a laptop touchpad: grabs the iptsd virtual touchscreen exclusively (the compositor
stops getting its touches) and drives a uinput mouse instead.
  1 finger move  -> pointer move (relative, with gain)        1 finger tap -> left click (tap + hold + move = drag)
  2 finger tap   -> right click                               2 finger move -> scroll / pan (hi-res wheel)
  2 finger pinch -> zoom (Ctrl + wheel, as VS Code / browsers / image viewers take it)
Ctrl+C / SIGTERM releases the grab = normal touch again. Needs py3-evdev and /dev/uinput (root, or the input group).
usage: hingeboard-touchpad.py [--device 045E:0C01 | /dev/input/eventN] [--rotate 0|90|180|270] [--gain 2.5]
--device: the screen by its digitizer ID (0C01 = right/camera screen DSI-2, 0C02 = left DSI-1) or an event node.
--rotate: how the screen is turned relative to the digitizer's own axes; 0 = the portrait phone layout we calibrated
          (screen x = -digitizer y, screen y = -digitizer x)."""
import argparse, math, signal, sys, time
import evdev
from evdev import ecodes as E, UInput, AbsInfo

ap = argparse.ArgumentParser()
ap.add_argument("--device", default="045E:0C01"); ap.add_argument("--rotate", type=int, default=0)
ap.add_argument("--gain", type=float, default=2.5); ap.add_argument("--scroll", type=float, default=6.0)
ap.add_argument("--zoom-step", type=float, default=0.06, help="relative pinch change per zoom wheel click")
ap.add_argument("--zoom", choices=["ctrl-wheel", "labwc"], default="ctrl-wheel",
                help="pinch = Ctrl+wheel (app zoom) or labwc's screen magnifier (Super+= / Super+-; VNC-style zoom whose "
                     "view pans with the pointer)")
a = ap.parse_args()

def find():
    if a.device.startswith("/dev/"):
        return evdev.InputDevice(a.device)
    for p in evdev.list_devices():
        d = evdev.InputDevice(p)
        if d.name.startswith("IPTSD Virtual Touchscreen") and a.device.upper() in d.name.upper():
            return d
    sys.exit("no IPTSD Virtual Touchscreen %s (have: %s)" % (a.device, [evdev.InputDevice(p).name for p in evdev.list_devices()]))

dev = find(); caps = dict(dev.capabilities()[E.EV_ABS])
xr, yr = caps[E.ABS_MT_POSITION_X], caps[E.ABS_MT_POSITION_Y]
span = max(xr.max - xr.min, yr.max - yr.min)
# screen delta from a digitizer delta (pixels-ish units: 1000 * fraction of the long side)
ROT = {0: lambda dx, dy: (-dy, -dx), 90: lambda dx, dy: (dx, -dy), 180: lambda dx, dy: (dy, dx), 270: lambda dx, dy: (-dx, dy)}[a.rotate]

ui = UInput({E.EV_KEY: [E.BTN_LEFT, E.BTN_RIGHT, E.BTN_MIDDLE, E.KEY_LEFTCTRL, E.KEY_LEFTMETA, E.KEY_EQUAL, E.KEY_MINUS],
             E.EV_REL: [E.REL_X, E.REL_Y, E.REL_WHEEL, E.REL_HWHEEL, E.REL_WHEEL_HI_RES, E.REL_HWHEEL_HI_RES]},
            name="Duo touchpad (%s)" % dev.name[-9:])
dev.grab()
# Put the pointer on the DESKTOP screen: it can start on the keyboard screen (DSI-1, parked far away in the layout so
# the pointer cannot wander under the keyboard). wlroots clamps a pointer move to the nearest point of the WHOLE layout,
# so one huge up-left move lands on the desktop screen's top-left corner (it sits at 0,0); then go to its middle.
# Also on a THREE-finger tap (request 2026-11-06: "the mouse is on the wrong side" = the pointer on the keyboard screen).
def home():
    for _ in range(4):
        ui.write(E.EV_REL, E.REL_X, -30000); ui.write(E.EV_REL, E.REL_Y, -30000); ui.syn(); time.sleep(0.02)
    for _ in range(10):
        ui.write(E.EV_REL, E.REL_X, 45); ui.write(E.EV_REL, E.REL_Y, 34); ui.syn(); time.sleep(0.01)
time.sleep(1.0)                      # let the compositor pick up the new mouse first
home()
print("touchpad mode on %s (%s), rotate %d - Ctrl+C to give the screen back" % (dev.path, dev.name, a.rotate), flush=True)

def stop(*_):
    try: dev.ungrab()
    except OSError: pass
    ui.close(); sys.exit(0)
signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)

slots, slot = {}, 0                    # slot -> [x, y] for active contacts
TAP_S, TAP_MOVE = 0.22, 0.012          # tap: shorter than 220 ms and moved < 1.2 % of the screen
EDGE, JUMP = 0.03, 0.06                 # edge band (fraction of each axis) and the per-frame glitch threshold
g = {"t0": 0, "maxf": 0, "moved": 0.0, "last": None, "dist0": None, "rem": [0.0, 0.0], "srem": [0.0, 0.0], "zrem": 0.0, "drag": False}

def emit(t, c, v): ui.write(t, c, v)
def click(btn):
    emit(E.EV_KEY, btn, 1); ui.syn(); emit(E.EV_KEY, btn, 0); ui.syn()

def frame():
    # both coordinates: a new contact can report X before Y (crashed the trackpad 2026-11-06 = "my mouse is gone")
    pts = [tuple(p) for p in slots.values() if p[0] is not None and p[1] is not None]
    n = len(pts)
    if n == 0:
        if g["last"] is not None:          # all fingers up: was it a tap?
            if time.monotonic() - g["t0"] < TAP_S * 1.5 and g["moved"] < TAP_MOVE and g["maxf"] >= 3:
                home()                                         # 3-finger tap: pointer back onto the desktop screen
            elif time.monotonic() - g["t0"] < TAP_S and g["moved"] < TAP_MOVE:
                click(E.BTN_RIGHT if g["maxf"] >= 2 else E.BTN_LEFT)
            if g["drag"]:
                emit(E.EV_KEY, E.BTN_LEFT, 0); ui.syn(); g["drag"] = False
        g.update(last=None, maxf=0, moved=0.0, dist0=None)
        return
    cx = sum(p[0] for p in pts) / n; cy = sum(p[1] for p in pts) / n
    if g["last"] is None or n != g["last"][2]:   # new gesture or finger count changed: re-anchor
        if g["last"] is None:
            g["t0"] = time.monotonic()
            # tap-and-hold (second touch within 300 ms of a tap) = drag
        g.update(last=(cx, cy, n), dist0=(math.dist(pts[0], pts[1]) if n >= 2 else None))
        g["maxf"] = max(g["maxf"], n); return
    dx, dy = (cx - g["last"][0]) / span, (cy - g["last"][1]) / span
    # The digitizer is unreliable within ~4 mm of its edges (positions collapse / jump - calibration 2026-11-06), so
    # (1) no motion while a finger is in the EDGE band (re-anchor, like a laptop pad's bezel) and (2) a jump of more than
    # JUMP of the pad in one frame is a glitch, not a swipe (request: "the track pad seems to be inconsistant near the edges")
    near_edge = any(min((p[0] - xr.min) / (xr.max - xr.min or 1), (xr.max - p[0]) / (xr.max - xr.min or 1),
                        (p[1] - yr.min) / (yr.max - yr.min or 1), (yr.max - p[1]) / (yr.max - yr.min or 1)) < EDGE
                    for p in pts)
    if near_edge or math.hypot(dx, dy) > JUMP:
        g["last"] = (cx, cy, n); g["maxf"] = max(g["maxf"], n)
        return
    g["moved"] += math.hypot(dx, dy); g["last"] = (cx, cy, n); g["maxf"] = max(g["maxf"], n)
    sx, sy = ROT(dx, dy)
    if n == 1:
        g["rem"][0] += sx * 1000 * a.gain; g["rem"][1] += sy * 1000 * a.gain
        ix, iy = int(g["rem"][0]), int(g["rem"][1])
        if ix or iy:
            g["rem"][0] -= ix; g["rem"][1] -= iy
            emit(E.EV_REL, E.REL_X, ix); emit(E.EV_REL, E.REL_Y, iy); ui.syn()
    elif n >= 2:
        d = math.dist(pts[0], pts[1]) / span
        if g["dist0"] and abs(d - g["dist0"] / span) > a.zoom_step:      # pinch -> Ctrl + wheel
            step = 1 if d > g["dist0"] / span else -1
            if a.zoom == "labwc":      # Super+= zoom in / Super+- zoom out (rc.xml keybinds -> magnifier)
                k = E.KEY_EQUAL if step > 0 else E.KEY_MINUS
                emit(E.EV_KEY, E.KEY_LEFTMETA, 1); emit(E.EV_KEY, k, 1); ui.syn()
                emit(E.EV_KEY, k, 0); emit(E.EV_KEY, E.KEY_LEFTMETA, 0); ui.syn()
            else:
                emit(E.EV_KEY, E.KEY_LEFTCTRL, 1); emit(E.EV_REL, E.REL_WHEEL, step); emit(E.EV_REL, E.REL_WHEEL_HI_RES, 120 * step)
                ui.syn(); emit(E.EV_KEY, E.KEY_LEFTCTRL, 0); ui.syn()
            g["dist0"] = d * span; g["moved"] += 1                         # a pinch is never a tap
            return
        g["srem"][0] += sx * 1000 * a.scroll; g["srem"][1] += sy * 1000 * a.scroll   # natural scrolling: content follows fingers
        hx, hy = int(g["srem"][0]), int(g["srem"][1])
        if hx or hy:
            g["srem"][0] -= hx; g["srem"][1] -= hy
            if hy: emit(E.EV_REL, E.REL_WHEEL_HI_RES, hy); emit(E.EV_REL, E.REL_WHEEL, int(hy / 120)) if abs(hy) >= 120 else None
            if hx: emit(E.EV_REL, E.REL_HWHEEL_HI_RES, -hx)
            ui.syn()

# "no touch" (the keyboard's button, e.g. while holding the phone to play): touches are read but ignored. State in
# $XDG_RUNTIME_DIR/hingeboard-notouch ("1" = off), re-read on SIGUSR1 and at start.
import os
NOTOUCH = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "hingeboard-notouch")
def read_notouch(*_):
    try:
        off = open(NOTOUCH).read().strip() == "1"
    except OSError:
        off = False
    if off and g["drag"]:
        emit(E.EV_KEY, E.BTN_LEFT, 0); ui.syn(); g["drag"] = False
    g["off"] = off
read_notouch()
signal.signal(signal.SIGUSR1, read_notouch)

for ev in dev.read_loop():
    if g["off"]:
        slots.clear(); g.update(last=None, maxf=0, moved=0.0, dist0=None)
        continue
    if ev.type == E.EV_ABS:
        if ev.code == E.ABS_MT_SLOT: slot = ev.value
        elif ev.code == E.ABS_MT_TRACKING_ID:
            if ev.value < 0: slots.pop(slot, None)
            else: slots[slot] = [None, None]
        elif ev.code == E.ABS_MT_POSITION_X and slot in slots: slots[slot][0] = ev.value
        elif ev.code == E.ABS_MT_POSITION_Y and slot in slots: slots[slot][1] = ev.value
    elif ev.type == E.EV_SYN and ev.code == E.SYN_REPORT:
        frame()
