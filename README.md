# Hingeboard

Laptop mode for a two-screen phone. One screen becomes a permanent on-screen keyboard; the other becomes the
desktop, driven like a laptop: its touchscreen turns into a touchpad (relative pointer, tap to click, two-finger
scroll, pinch to zoom).

Built for the Microsoft Surface Duo (first generation) running mainline Linux with postmarketOS and Phosh. Screen
names and touch devices are settings, so other dual-screen devices can use it.

## What it does

- **Keyboard** (`hingeboard`): a full-screen GTK4 layer-shell overlay on one screen, drawn for laptop posture (hinge
  at the top). It never takes keyboard focus; keys go to the app on the other screen (or an HDMI display) through a
  virtual keyboard.
  - Standard laptop layout, latching Shift / Ctrl / Alt / Super, Caps Lock, hold to repeat.
  - Gamepad mode: D-pad, A B X Y, L R, Select / Start as a virtual gamepad, multi-touch.
  - Microphone key: offline dictation with Vosk (`hingeboard-dictate.py`); nothing leaves the device.
  - Exit puts both screens back to phone mode.
- **Display modes** (`hingeboard-display-mode keyboard|phone`): while the keyboard runs, the other screen becomes
  Phosh's primary display in landscape.
- **Touchpad** (`hingeboard-touchpad.py`): grabs one screen's touchscreen and drives a virtual mouse.
  - 1 finger: move, tap = click, tap + hold + move = drag. 2 fingers: tap = right click, move = scroll,
    pinch = zoom.
- **Laptop session** (`hingeboard-session desktop|phone`): switches the whole graphical session between Phosh and a
  labwc + LXQt desktop (keyboard on one screen, landscape desktop and touchpad on the other). The "Hingeboard"
  app launcher starts it; Exit on the keyboard comes back.
- **Swap and flip** (laptop session): two keyboard buttons. Swap moves the keyboard to the other screen and the
  desktop to this one; flip turns both upside down. The choice is remembered (`~/.config/hingeboard/layout`).
- **TV / monitor** (laptop session): an external display mirrors the desktop screen by default. A screens button
  appears on the keyboard while one is connected; it switches to **TV only**, where the phone's desktop screen turns
  off and stays a touchpad, and the desktop and pointer live on the TV alone (and back).
- **Dock watcher** (`hingeboard-dock-watch`): plugging in a USB-C dock (DisplayPort / HDMI) while in Phosh switches
  to the laptop session.

## Requirements

postmarketOS (Alpine) with Phosh. Packages:

    apk add py3-gobject3 py3-cairo py3-evdev gtk4-layer-shell wlr-randr doas
    apk add labwc lxqt-panel pcmanfm-qt lxqt-powermanagement breeze-icons wl-mirror   # laptop session
    apk add py3-vosk-api vosk-model-small-en-us                                # dictation (optional)

The session user must be in the `input` group (the udev rule gives it `/dev/uinput`). On the Surface Duo the
touchscreens come from iptsd (multitouch) and the Duo's touch driver.

## Install

On the device, as root:

    sh install.sh                 # everything
    sh install.sh --no-desktop    # keyboard, touchpad and dock watcher only

Into a mounted root from another system: `ROOT=/mnt/root sh install.sh`. The session user defaults to `user`
(postmarketOS's default); set `HB_USER=name` otherwise. `hingeboard-session` restarts tinydm and ends that user's
processes when it switches sessions.

The programs go to `/usr/local/bin`; `install.sh` writes the small configuration files itself (uinput udev rule,
app launcher, dock-watcher autostart, session entry, doas rule, labwc and LXQt settings). Repository contents:

| File | What it is |
|---|---|
| `hingeboard` | the keyboard (Python, GTK4 layer-shell) |
| `hingeboard-touchpad.py` | touchscreen to touchpad |
| `hingeboard-display-mode` | phone / keyboard display layout (Phosh) |
| `hingeboard-dictate.py` | offline dictation for the microphone key |
| `hingeboard-dock-watch` | dock plugged in = keyboard mode |
| `hingeboard-session` | the laptop session: switch, start, layout (swap / flip), external display |
| `install.sh`, `README.md`, `LICENSE` | |

## Settings

Environment variables for `hingeboard` (defaults are the Surface Duo's):

| Variable | Default | Meaning |
|---|---|---|
| `HINGEBOARD_OUTPUT` | `DSI-1` | the keyboard screen |
| `HINGEBOARD_OTHER` | `DSI-2` | the screen that becomes the desktop |
| `HINGEBOARD_OTHER_TOUCH` | `045E:0C01` | that screen's touchscreen (vendor:product) |
| `HINGEBOARD_ROTATE` | `90` | 0 = portrait, 90 = laptop posture |
| `HINGEBOARD_MODE` | `keys` | start in `keys` or `pad` (gamepad) mode |
| `HINGEBOARD_TOP_PAD` | `0.14` | free space above the keys (fraction of the screen) |
| `HINGEBOARD_GAP` | `3.5` | space around each key (logical px) |
| `HINGEBOARD_WINDOWS` | off | show a row of open windows on the keyboard |
| `HINGEBOARD_DISPLAY_TRANSFORM` | `3` | rotation of the desktop screen in keyboard mode (3 = 270) |
| `HINGEBOARD_DEBUG` | off | print every touch and its hit test |

`hingeboard-touchpad.py --help` lists the touchpad's options (device, rotation, gain, zoom style).

The laptop session treats `HINGEBOARD_OUTPUT` / `HINGEBOARD_OTHER` as screens A and B (the keyboard starts on A)
and their touchscreens as `HINGEBOARD_KB_TOUCH` (default `IPTSD Virtual Touchscreen 045E:0C02`) and
`HINGEBOARD_OTHER_TOUCH_NAME` (default `IPTSD Virtual Touchscreen 045E:0C01`); swap and flip work from those.

## License

GPL-2.0-or-later (see [LICENSE](LICENSE) for the GPL version 2 text; each file has an SPDX line).

## How this was made

Written by Claude (Anthropic's AI) working on the phone end to end, with Bryson directing and testing.
