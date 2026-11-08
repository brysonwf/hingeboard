#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Install Hingeboard into a root filesystem: the running system (default) or a mounted one (ROOT=/mnt/root). Run as
# root; idempotent. The small config files (udev rule, launchers, doas rule, labwc and LXQt settings) are written here.
# usage: [ROOT=/] [HB_USER=user] sh install.sh [--no-desktop]
#   --no-desktop  only the keyboard, touchpad, dictation and dock watcher (no labwc + LXQt laptop session)
set -e
R=${ROOT:-}; U=${HB_USER:-user}; S=$(dirname "$(readlink -f "$0")")
DESKTOP=1; [ "$1" = --no-desktop ] && DESKTOP=0
put() { mkdir -p "$(dirname "$R$1")"; cat > "$R$1"; chmod "${2:-644}" "$R$1"; }

for f in hingeboard hingeboard-touchpad.py hingeboard-display-mode hingeboard-dictate.py hingeboard-dock-watch hingeboard-session; do
	tr -d '\r' < "$S/$f" | put /usr/local/bin/$f 755
done
# the keyboard and touchpad create virtual input devices: /dev/uinput for the input group (the session user is in it)
echo 'KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"' |
	put /etc/udev/rules.d/70-hingeboard-uinput.rules
put /etc/xdg/autostart/hingeboard-dock-watch.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Hingeboard dock watcher
Comment=USB-C dock plugged in -> keyboard mode, unplugged -> phone mode
Exec=/usr/local/bin/hingeboard-dock-watch
NoDisplay=true
X-GNOME-Autostart-enabled=true
OnlyShowIn=Phosh;GNOME;
EOF
echo "installed: keyboard, touchpad, display modes, dictation, dock watcher"
[ $DESKTOP = 1 ] || exit 0

# the laptop session: the app launcher switches to it, Exit on the keyboard switches back
put /usr/local/share/applications/hingeboard.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Hingeboard
Comment=Laptop mode: landscape desktop + touchpad on one screen, the keyboard on the other; Exit comes back
Exec=doas /usr/local/bin/hingeboard-session desktop
Icon=input-keyboard
Categories=Utility;Accessibility;
X-Purism-FormFactor=Workstation;Mobile;
EOF
put /usr/share/wayland-sessions/hingeboard-desktop.desktop <<EOF
[Desktop Entry]
Name=Hingeboard Desktop
Comment=Laptop mode: landscape desktop + permanent keyboard (labwc + LXQt)
Exec=/usr/local/bin/hingeboard-session run
Type=Application
EOF
# the session user may switch sessions as root without a password - only these two commands
put /etc/doas.d/hingeboard-session.conf <<EOF
permit nopass $U as root cmd /usr/local/bin/hingeboard-session args desktop
permit nopass $U as root cmd /usr/local/bin/hingeboard-session args phone
EOF
# labwc: a TEMPLATE - hingeboard-session fills in the keyboard screen and its touchscreen for the current layout
# and runs labwc with that config dir. A full-screen magnifier that follows the pointer (pinch on the touchpad =
# Super+= / Super+-); the keyboard screen's touch as a touchscreen (no mouse emulation: taps on the keyboard must not
# move the pointer there)
put /usr/local/share/hingeboard/labwc/rc.xml <<EOF
<?xml version="1.0"?>
<labwc_config>
  <core><gap>0</gap></core>
  <theme>
    <cornerRadius>6</cornerRadius>
    <font place="ActiveWindow" name="sans" size="11" />
    <font place="MenuItem" name="sans" size="11" />
  </theme>
  <placement><policy>cascade</policy></placement>
  <magnifier>
    <width>-1</width><height>-1</height><initScale>1.5</initScale><increment>0.25</increment><useFilter>true</useFilter>
  </magnifier>
  <keyboard>
    <default />
    <keybind key="W-equal"><action name="ZoomIn" /></keybind>
    <keybind key="W-minus"><action name="ZoomOut" /></keybind>
    <keybind key="W-0"><action name="ToggleMagnify" /></keybind>
  </keyboard>
  <touch deviceName="@KB_TOUCH@" mapToOutput="@KB_OUT@" mouseEmulation="no" />
  <windowRules>
    <!-- the TV mirror (hingeboard-session screens) is not a window to switch to -->
    <windowRule identifier="at.yrlf.wl_mirror" skipTaskbar="yes" skipWindowSwitcher="yes" />
  </windowRules>
</labwc_config>
EOF

# per-user desktop: Downloads on the desktop, dark LXQt with real icons, a taskbar on the desktop screen, a battery
# icon without power actions (a suspend would end the session)
H=$R/home/$U
IDS=$(awk -F: -v u="$U" '$1 == u { print $3 ":" $4 }' "$R/etc/passwd")
[ -n "$IDS" ] || { echo "no user $U in $R/etc/passwd (set HB_USER)"; exit 1; }
mkdir -p $H/Desktop $H/Downloads $H/.config/pcmanfm-qt/lxqt $H/.config/lxqt
ln -sfn /home/$U/Downloads $H/Desktop/Downloads
C=$H/.config/pcmanfm-qt/lxqt/settings.conf
grep -q '^DesktopShortcuts' $C 2>/dev/null ||
	printf '[Desktop]\nDesktopShortcuts=Home, Trash, Computer, Network\nWallpaperMode=stretch\nBgColor=#1f4f3a\n' >> $C
IT=breeze-dark; [ -f $R/usr/share/icons/linuxduobench/index.theme ] && IT=linuxduobench
cat > $H/.config/lxqt/lxqt.conf <<EOF
[General]
__userfile__=true
icon_theme=$IT
theme=dark

[Qt]
style=Fusion

[Palette]
window_color=#202226
base_color=#17191c
alt_base_color=#202226
button_color=#2a2d32
window_text_color=#e8e8e8
text_color=#e8e8e8
button_text_color=#e8e8e8
highlight_color=#3d7ad6
highlighted_text_color=#ffffff
link_color=#6aa6ff
link_visited_color=#b08cff
EOF
printf '[General]\n__userfile__=true\nenableBatteryWatcher=true\npowerLowAction=0\nenableIdlenessWatcher=false\nenableLidWatcher=false\nshowIcon=true\nuseThemeIcons=true\n' > $H/.config/lxqt/lxqt-powermanagement.conf
cat > $H/.config/lxqt/panel.conf <<EOF
[General]
__userfile__=true

[panel1]
alignment=-1
animation-duration=0
desktop=0
hidable=false
iconSize=24
lineCount=1
lockPanel=true
panelSize=40
plugins=fancymenu,quicklaunch,taskbar,statusnotifier,mount,volume,worldclock,showdesktop
position=Bottom
reserve-space=true
screen-name=${HINGEBOARD_OTHER:-DSI-2}
width=100
width-percent=true

[fancymenu]
type=fancymenu

[quicklaunch]
type=quicklaunch
alignment=Left
apps\\1\\desktop=/usr/share/applications/pcmanfm-qt.desktop
apps\\2\\desktop=/usr/share/applications/foot.desktop
apps\\3\\desktop=/usr/share/applications/org.gnome.Epiphany.desktop
apps\\size=3

[taskbar]
type=taskbar
buttonStyle=IconText
buttonWidth=200
groupingEnabled=false

[statusnotifier]
type=statusnotifier

[mount]
type=mount

[volume]
type=volume

[worldclock]
type=worldclock

[showdesktop]
type=showdesktop
EOF
chown -R "$IDS" $H/Desktop $H/Downloads $H/.config/pcmanfm-qt $H/.config/lxqt
echo "installed: laptop session for $U"
