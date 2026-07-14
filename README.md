# ATK Tray Charge Notification

> **Notice:** Development has moved to a new project: https://github.com/Fan4Metal/mouse_tray

## Introduction
![Screenshot](images/screenshot.png)<br>
This is a script for **Windows** written in Python 3.10+ with `wxPython` and `hidapi` that gets the battery level of a **ATK/VXE/VGN** Wireless mouse and shows it in system tray.

## Setup
1. Clone this repository.
2. Install dependencies: `pip install -r requirements.txt`.
3. Change extension of script file from `atk_tray.py` to `atk_tray.pyw` if you don't want to see console output.

## Settings
You can modify these settings variables:
1. `poll_rate` in seconds - how often battery charge is read. 60 sec by default.
2. `foreground_color` - color of indicator text. Tuple with RGB data.
3. `background_color` - color of indicator background. Transparent by default (0, 0, 0, 0).
4. `font` - font of digital indicator. Default: `consola.ttf`.

## Supported models
 - ATK F1 Ultimate
 - ATK A9 Ultimate
 - VXE MAD R
 - VXE MAD R Major Plus
 - VXE R1 Pro Max
 - VXE R1 SE+
 - VGN F1 Pro