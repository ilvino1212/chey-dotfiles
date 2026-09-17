#!/usr/bin/env python3

import subprocess
import json


def _run(args, timeout=2):
    return subprocess.run(["hyprctl"] + args, capture_output=True, text=True, timeout=timeout)


def hyprctl_json(args, timeout=2):
    """Llamadas de solo lectura (clients, activewindow, monitors, etc).
    Estas NO pasan por el parser de dispatch, siguen funcionando igual
    que antes en Lua config."""
    r = _run(args + ["-j"], timeout=timeout)
    return json.loads(r.stdout) if r.stdout.strip() else None


def dispatch(lua_expr, timeout=2):
    """Ejecuta hyprctl dispatch '<lua_expr>'.
    lua_expr debe ser una llamada completa a hl.dsp.*(...)"""
    return _run(["dispatch", lua_expr], timeout=timeout)


def dispatch_async(lua_expr):
    subprocess.Popen(["hyprctl", "dispatch", lua_expr],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def batch(lua_exprs, timeout=5):
    """lua_exprs: lista de llamadas completas a hl.dsp.*(...)"""
    cmd = " ; ".join(f"dispatch {e}" for e in lua_exprs)
    return subprocess.run(["hyprctl", "--batch", cmd], capture_output=True, timeout=timeout)


_ipc_socket = None

def batch_async(lua_exprs):
    global _ipc_socket

    if not lua_exprs:
        return

    import os
    import socket

    runtime = os.environ.get("XDG_RUNTIME_DIR")
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not runtime or not signature:
        return

    path = os.path.join(runtime, "hypr", signature, ".socket.sock")

    try:
        if _ipc_socket is None:
            _ipc_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            _ipc_socket.settimeout(0.02)
            _ipc_socket.connect(path)

        cmd = "[[BATCH]]" + " ; ".join(
            f"dispatch {e}" for e in lua_exprs
        )

        _ipc_socket.sendall(cmd.encode())

    except Exception:
        try:
            if _ipc_socket:
                _ipc_socket.close()
        except Exception:
            pass
        _ipc_socket = None


# official wiki

def toggle_floating_lua(address=None):
    w = f', window = "address:{address}"' if address else ""
    return f'hl.dsp.window.float({{ action = "toggle"{w} }})'

def toggle_floating(address=None):
    return dispatch(toggle_floating_lua(address))


def focus_window_lua(address):
    return f'hl.dsp.focus({{ window = "address:{address}" }})'

def focus_window(address):
    return dispatch(focus_window_lua(address))


def move_focus_lua(direction_lud):  # 'l' | 'r' | 'u' | 'd'
    return f'hl.dsp.focus({{ direction = "{direction_lud}" }})'

def move_focus(direction_lud):
    return dispatch(move_focus_lua(direction_lud))


def move_window_tiled_lua(direction_lud):
    return f'hl.dsp.window.move({{ direction = "{direction_lud}" }})'

def move_window_tiled(direction_lud):
    return dispatch(move_window_tiled_lua(direction_lud))


def exec_cmd_lua(cmd):
    escaped = cmd.replace('\\', '\\\\').replace('"', '\\"')
    return f'hl.dsp.exec_cmd("{escaped}")'



def move_window_exact_lua(x, y, address):
    return (f'hl.dsp.window.move({{ window = "address:{address}", '
            f'x = {int(x)}, y = {int(y)}, relative = false }})')

def move_window_exact(x, y, address, timeout=2):
    return dispatch(move_window_exact_lua(x, y, address), timeout=timeout)

def move_window_exact_async(x, y, address):
    dispatch_async(move_window_exact_lua(x, y, address))


def resize_window_exact_lua(w, h, address):
    return (f'hl.dsp.window.resize({{ window = "address:{address}", '
            f'x = {int(w)}, y = {int(h)}, relative = false }})')

def resize_window_exact(w, h, address, timeout=2):
    return dispatch(resize_window_exact_lua(w, h, address), timeout=timeout)
