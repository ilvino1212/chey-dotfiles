#!/usr/bin/env python3
"""
resize_window.py
Redimensiona la ventana flotante activa 90px desde el lado derecho/inferior.

left/right → cambia el ancho
up/down    → cambia el alto

Uso: python3 resize_window.py <left|right|up|down>
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hypr_ipc import hyprctl_json, resize_window_exact

STEP = 90
MIN_SIZE = 100  # tamaño mínimo para no colapsar la ventana


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("left", "right", "up", "down"):
        print("Uso: resize_window.py <left|right|up|down>")
        sys.exit(1)

    direction = sys.argv[1]

    window = hyprctl_json(["activewindow"])
    if not window or not window.get("floating"):
        sys.exit(0)

    addr = window["address"]
    ww, wh = window["size"][0], window["size"][1]

    if direction == "right":
        new_w = ww + STEP
        new_h = wh
    elif direction == "left":
        new_w = max(MIN_SIZE, ww - STEP)
        new_h = wh
    elif direction == "down":
        new_w = ww
        new_h = wh + STEP
    elif direction == "up":
        new_w = ww
        new_h = max(MIN_SIZE, wh - STEP)

    resize_window_exact(new_w, new_h, addr)


if __name__ == "__main__":
    main()
