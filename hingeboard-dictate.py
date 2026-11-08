#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Duo dictation (request 2026-11-06: "keyboard needs a voice to text button"): OFFLINE speech-to-text with Vosk
(Alpine community: py3-vosk-api + vosk-model-small-en-us; nothing leaves the phone). Records the session's default
microphone through PipeWire (parecord, 16 kHz mono) and prints one line per event on stdout:
  READY            model loaded, listening
  PART <words>     partial hypothesis (for display)
  TEXT <words>     a finished phrase (the keyboard app types it)
SIGTERM/SIGINT: flush the last phrase as TEXT, then exit. The keyboard app's mic key starts/stops this.
usage: hingeboard-dictate.py [--model /usr/share/vosk-models/small-en-us]"""
import argparse, json, signal, subprocess, sys
import vosk

ap = argparse.ArgumentParser(); ap.add_argument("--model", default="/usr/share/vosk-models/small-en-us")
a = ap.parse_args()
vosk.SetLogLevel(-1)
rec = vosk.KaldiRecognizer(vosk.Model(a.model), 16000)
rec_proc = subprocess.Popen(["parecord", "--raw", "--format=s16le", "--rate=16000", "--channels=1"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
done = False
def stop(*_):
    global done
    done = True
    rec_proc.terminate()
signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
print("READY", flush=True)
while True:
    data = rec_proc.stdout.read(4000)          # 125 ms of audio
    if not data:
        break
    if rec.AcceptWaveform(data):
        t = json.loads(rec.Result()).get("text", "")
        if t: print("TEXT " + t, flush=True)
    else:
        p = json.loads(rec.PartialResult()).get("partial", "")
        if p: print("PART " + p, flush=True)
t = json.loads(rec.FinalResult()).get("text", "")
if t: print("TEXT " + t, flush=True)
