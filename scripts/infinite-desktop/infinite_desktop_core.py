#!/usr/bin/env python3
#
# infinite_desktop_core.py  --  versione 2.3
#
# Cronologia:
#   2.0  base: socket IPC, camera per workspace, zoom senza deriva
#   2.1  statistiche di debug (durata dei batch)
#   2.2  mouse bloccato solo mentre SUPER+ALT è premuto
#   2.3  animazioni di Hyprland sospese durante pan/drag (via eval, config Lua)
#
# Nessun argomento da riga di comando: la velocità del pan è PAN_SPEED.
# Nessun bind Hyprland: mouse e tastiera vengono letti da /dev/input.
# La tastiera non viene MAI bloccata (SUPER+ALT+frecce e gli altri bind di
# Caelestia arrivano a Hyprland). Il mouse viene bloccato (grab) solo
# finché SUPER+ALT è premuto: il cursore resta fermo e le finestre
# seguono il movimento grezzo del mouse. Al rilascio torna tutto normale.
#
#   SUPER + ALT + mouse        -> sposta tutto il desktop
#   SUPER + ALT + "=" / "-"    -> zoom (centrato sul cursore)
#   SUPER + tasto sinistro     -> trascina la finestra floating
#
# Debug: INFINITE_DESKTOP_DEBUG=1 stampa su stderr comandi rifiutati e refresh.

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import math
import json
from dataclasses import dataclass

from evdev import InputDevice, list_devices, ecodes


# ============================================================
# CONFIG
# ============================================================

TARGET_HZ = 170.0
FRAME_TIME = 1.0 / TARGET_HZ

PAN_SPEED = 1.6
WINDOW_DRAG_SPEED = 1.0

ZOOM_STEP = 1.18
MIN_ZOOM = 0.25
MAX_ZOOM = 3.0
MIN_WINDOW_SIZE = 80

VERSION = "2.3"

STATE_FILE = "/tmp/infinite-desktop-state"

EDGE_MARGIN = 8           # px dal bordo in cui il drag fa scorrere il canvas
CULL_MARGIN = 48          # le finestre oltre schermo+margine non vengono spostate
SOCKET_TIMEOUT = 0.25     # attesa massima della risposta di Hyprland
REFRESH_MIN_INTERVAL = 0.05

# Comando per nascondere il frame di Caelestia mentre SUPER+ALT è premuto.
# Se il tuo vecchio notify_quickshell_hold usava altri argomenti
# (es. "-c caelestia"), copiali qui.
QS_HOLD_COMMAND = ["qs", "ipc", "call", "frame", "setHeldHidden"]

DEBUG = bool(os.environ.get("INFINITE_DESKTOP_DEBUG"))


def debug(*args):
    if DEBUG:
        print("[infinite-desktop]", *args, file=sys.stderr, flush=True)


# ============================================================
# WINDOW STATE
# ============================================================
#
# Modello "camera": ogni finestra ha coordinate MONDO (x, y, width, height,
# a zoom 1.0). La posizione a schermo si calcola sempre da:
#
#     schermo = (mondo - cam) * zoom
#
# Pan e zoom cambiano solo la camera, non le finestre: zoom avanti e
# indietro tornano esattamente allo stato di partenza (niente deriva).
# Ogni workspace ha la sua camera.

@dataclass
class Window:
    address: str
    x: float
    y: float
    width: float
    height: float
    workspace: int
    # ultimo rettangolo (x, y, w, h) che Hyprland ha realmente, in pixel
    applied: tuple = None


windows = {}

state_lock = threading.RLock()   # protegge lo stato
send_lock = threading.Lock()     # serializza le scritture verso Hyprland
zoom_lock = threading.Lock()     # scarta gli zoom in eccesso mentre uno è in corso

cache_dirty = True
cache_refreshing = False
cache_event = threading.Event()

active_workspace = None

monitor = {
    "left": 0,
    "top": 0,
    "right": 1920,
    "bottom": 1080,
}

monitor_rects = []   # (left, top, right, bottom) di tutti i monitor

cameras = {}         # workspace id -> [cam_x, cam_y, zoom]

zoom = 1.0           # specchio dello zoom del workspace attivo


def camera(ws):
    # da chiamare con state_lock preso
    cam = cameras.get(ws)

    if cam is None:
        cam = [0.0, 0.0, 1.0]
        cameras[ws] = cam

    return cam


# ============================================================
# INPUT STATE
# ============================================================

super_down = False
alt_down = False
ctrl_down = False
left_down = False

mouse_dx = 0.0
mouse_dy = 0.0

drag_address = None

frame_held_hidden = False
hold_lock = threading.Lock()

mouse_devices = []
mouse_grabbed = False

anim_suspended = False
anim_restore_failures = 0
anim_lock = threading.Lock()

running = True


META_KEYS = {
    ecodes.KEY_LEFTMETA,
    ecodes.KEY_RIGHTMETA,
}

ALT_KEYS = {
    ecodes.KEY_LEFTALT,
    ecodes.KEY_RIGHTALT,
}

CTRL_KEYS = {
    ecodes.KEY_LEFTCTRL,
    ecodes.KEY_RIGHTCTRL,
}

ZOOM_IN_KEYS = {
    ecodes.KEY_EQUAL,
    ecodes.KEY_KPPLUS,
}

ZOOM_OUT_KEYS = {
    ecodes.KEY_MINUS,
    ecodes.KEY_KPMINUS,
}


# ============================================================
# HYPRLAND SOCKET (nessun processo hyprctl)
# ============================================================

def _socket_path(name):

    runtime = os.environ.get("XDG_RUNTIME_DIR")
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")

    if not runtime or not signature:
        return None

    return os.path.join(runtime, "hypr", signature, name)


def hypr_request(payload, timeout=SOCKET_TIMEOUT):
    """Invia una richiesta e aspetta la risposta completa.

    Aspettare la risposta è quello che tiene il ritmo: il chiamante
    non può inviare più in fretta di quanto Hyprland riesca a eseguire,
    quindi non si forma nessuna coda. Ritorna None in caso di errore.
    """

    path = _socket_path(".socket.sock")

    if path is None:
        return None

    try:

        with socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        ) as sock:

            sock.settimeout(timeout)
            sock.connect(path)
            sock.sendall(payload.encode())

            chunks = []

            while True:

                chunk = sock.recv(65536)

                if not chunk:
                    break

                chunks.append(chunk)

        return b"".join(chunks).decode(errors="ignore")

    except Exception:
        return None


def hypr_json(args, timeout=SOCKET_TIMEOUT):

    reply = hypr_request(
        "j/" + " ".join(args),
        timeout,
    )

    if not reply or not reply.strip():
        return None

    try:
        return json.loads(reply)
    except ValueError:
        return None


_batch_stats = {
    "n": 0, "cmds": 0, "total": 0.0, "max": 0.0,
    "since": 0.0, "last": 0.0, "gap": 0.0,
}


def _record_batch(count, elapsed, started):
    """Solo in debug: una riga al secondo con quanto impiega Hyprland."""

    if not DEBUG:
        return

    st = _batch_stats
    now = time.monotonic()

    if st["since"] == 0.0:
        st["since"] = now

    # intervallo tra due batch consecutivi (ignora le pause a mouse fermo)
    if st["last"]:

        gap = started - st["last"]

        if gap < 0.25:
            st["gap"] = max(st["gap"], gap)

    st["last"] = started

    st["n"] += 1
    st["cmds"] += count
    st["total"] += elapsed
    st["max"] = max(st["max"], elapsed)

    if now - st["since"] >= 1.0:

        debug(
            f"stat: {st['n']} batch/s, "
            f"{st['total'] / st['n'] * 1000:.1f} ms medi, "
            f"{st['max'] * 1000:.1f} ms max, "
            f"{st['cmds'] / st['n']:.1f} comandi/batch, "
            f"intervallo max {st['gap'] * 1000:.1f} ms"
        )

        st.update(n=0, cmds=0, total=0.0, max=0.0, since=now, gap=0.0)


def hypr_batch(commands):
    """Esegue i comandi in un solo batch. True se Hyprland ha risposto."""

    if not commands:
        return True

    started = time.monotonic()

    reply = hypr_request(
        "[[BATCH]]" + " ; ".join(commands),
        SOCKET_TIMEOUT,
    )

    _record_batch(len(commands), time.monotonic() - started, started)

    if reply is None:
        debug("batch non riuscito (timeout o socket)")
        return False

    if DEBUG:

        bad = [
            line.strip()
            for line in reply.splitlines()
            if line.strip() and line.strip() != "ok"
        ]

        if bad:
            debug("risposta Hyprland:", bad[:3])

    return True


# ============================================================
# HYPRLAND COMMANDS
# ============================================================

def move_command(
    window,
    x,
    y,
):

    return (
        'dispatch hl.dsp.window.move({'
        f'window = "address:{window.address}", '
        f'x = {int(round(x))}, '
        f'y = {int(round(y))}, '
        'relative = false'
        '})'
    )


def resize_command(
    window,
    width,
    height,
):

    return (
        'dispatch hl.dsp.window.resize({'
        f'window = "address:{window.address}", '
        f'x = {int(round(width))}, '
        f'y = {int(round(height))}, '
        'relative = false'
        '})'
    )


# ============================================================
# GEOMETRY: mondo -> schermo
# ============================================================

def screen_rect(window, cam):
    """Rettangolo a schermo (x, y, w, h) interi per una finestra."""

    z = cam[2]

    # la dimensione minima non ingrandisce mai una finestra già più piccola
    sw = max(min(MIN_WINDOW_SIZE, window.width), window.width * z)
    sh = max(min(MIN_WINDOW_SIZE, window.height), window.height * z)

    # si scala attorno al centro, come faceva la versione originale
    cx = window.x + window.width / 2
    cy = window.y + window.height / 2

    sx = (cx - cam[0]) * z - sw / 2
    sy = (cy - cam[1]) * z - sh / 2

    return (
        int(round(sx)),
        int(round(sy)),
        int(round(sw)),
        int(round(sh)),
    )


def _visible(rect):

    if not monitor_rects:
        return True

    x, y, w, h = rect

    for left, top, right, bottom in monitor_rects:

        if (
            x < right + CULL_MARGIN
            and x + w > left - CULL_MARGIN
            and y < bottom + CULL_MARGIN
            and y + h > top - CULL_MARGIN
        ):
            return True

    return False


def _build_sync():
    """Comandi necessari per allineare Hyprland al modello.

    Da chiamare con state_lock preso. Salta:
    - le finestre già nella posizione giusta;
    - quelle fuori schermo sia prima sia dopo (verranno aggiornate
      quando rientrano in vista, Hyprland non le vede comunque).
    """

    commands = []
    pending = []

    if active_workspace is None:
        return commands, pending

    cam = camera(active_workspace)

    for window in windows.values():

        if window.workspace != active_workspace:
            continue

        rect = screen_rect(window, cam)
        applied = window.applied

        if rect == applied:
            continue

        if (
            applied is not None
            and not _visible(applied)
            and not _visible(rect)
        ):
            continue

        if applied is None or rect[2:] != applied[2:]:
            commands.append(
                resize_command(window, rect[2], rect[3])
            )

        if applied is None or rect[:2] != applied[:2]:
            commands.append(
                move_command(window, rect[0], rect[1])
            )

        pending.append((window, rect))

    return commands, pending


def sync_windows():
    """Invia a Hyprland ciò che è cambiato. NON chiamare con state_lock preso."""

    with send_lock:

        with state_lock:
            commands, pending = _build_sync()

        if not commands:
            return True

        ok = hypr_batch(commands)

        if ok:

            with state_lock:

                for window, rect in pending:
                    window.applied = rect

        else:
            # lo stato reale potrebbe essere diverso: rileggilo
            invalidate_cache()

        return ok


# ============================================================
# WINDOW CACHE
# ============================================================

def refresh_windows():

    global cache_dirty
    global cache_refreshing
    global active_workspace
    global monitor
    global monitor_rects
    global zoom

    with state_lock:

        if cache_refreshing:
            return

        cache_refreshing = True

        # azzerato PRIMA delle query: un evento che arriva durante il
        # refresh lo riaccende invece di andare perso
        cache_dirty = False

    ok = False

    try:

        debug("refresh cache")

        workspace_data = hypr_json(["activeworkspace"])
        monitors = hypr_json(["monitors"])
        clients = hypr_json(["clients"], timeout=0.6)

        if not isinstance(clients, list):
            return

        # -------------------------
        # Monitor (coordinate logiche: pixel / scale)
        # -------------------------

        new_rects = []
        focused = None

        if isinstance(monitors, list):

            for mon in monitors:

                scale = float(mon.get("scale") or 1.0)

                left = int(mon.get("x", 0))
                top = int(mon.get("y", 0))

                width = float(mon.get("width", 1920))
                height = float(mon.get("height", 1080))

                if int(mon.get("transform", 0)) % 2 == 1:
                    width, height = height, width

                rect = (
                    left,
                    top,
                    left + int(round(width / scale)),
                    top + int(round(height / scale)),
                )

                new_rects.append(rect)

                if mon.get("focused"):
                    focused = rect

            if focused is None and new_rects:
                focused = new_rects[0]

        # -------------------------
        # Stato
        # -------------------------

        with state_lock:

            if (
                isinstance(workspace_data, dict)
                and workspace_data.get("id") is not None
            ):
                active_workspace = int(workspace_data["id"])

            if focused:

                monitor = {
                    "left": focused[0],
                    "top": focused[1],
                    "right": focused[2],
                    "bottom": focused[3],
                }

            if new_rects:
                monitor_rects = new_rects

            new_windows = {}

            for client in clients:

                if not client.get("floating"):
                    continue

                if not client.get("mapped", True):
                    continue

                address = client.get("address")
                position = client.get("at")
                size = client.get("size")

                if not address:
                    continue

                if not position or len(position) < 2:
                    continue

                if not size or len(size) < 2:
                    continue

                ws = int(
                    (client.get("workspace") or {}).get("id", -1)
                )

                real = (
                    int(position[0]),
                    int(position[1]),
                    int(size[0]),
                    int(size[1]),
                )

                old = windows.get(address)

                # se coincide con quanto abbiamo inviato noi, il modello
                # resta com'è (niente deriva da arrotondamenti)
                if (
                    old is not None
                    and old.applied is not None
                    and old.workspace == ws
                    and all(
                        abs(a - b) <= 2
                        for a, b in zip(real, old.applied)
                    )
                ):
                    new_windows[address] = old
                    continue

                # nuova finestra, o spostata/ridimensionata da qualcun altro:
                # si importa la geometria reale nel mondo
                cam = camera(ws)
                z = cam[2]

                new_windows[address] = Window(
                    address=address,
                    x=cam[0] + real[0] / z,
                    y=cam[1] + real[1] / z,
                    width=real[2] / z,
                    height=real[3] / z,
                    workspace=ws,
                    applied=real,
                )

            windows.clear()
            windows.update(new_windows)

            if active_workspace is not None:
                zoom = camera(active_workspace)[2]

        ok = True

    finally:

        with state_lock:

            cache_refreshing = False

            if not ok:
                # query fallita: riprova al prossimo giro
                cache_dirty = True


def invalidate_cache():

    global cache_dirty

    with state_lock:
        cache_dirty = True

    cache_event.set()


def cache_thread():

    last = 0.0

    while running:

        with state_lock:
            dirty = cache_dirty

        if not dirty:

            cache_event.wait(0.25)
            cache_event.clear()
            continue

        wait = REFRESH_MIN_INTERVAL - (time.monotonic() - last)

        if wait > 0:
            time.sleep(wait)

        refresh_windows()

        last = time.monotonic()


# ============================================================
# CURSOR / ACTIVE WINDOW
# ============================================================

def get_cursor_position():

    data = hypr_json(
        ["cursorpos"],
        timeout=0.12
    )

    if isinstance(data, dict):

        if (
            "x" in data
            and "y" in data
        ):
            return (
                float(data["x"]),
                float(data["y"]),
            )

    reply = hypr_request("cursorpos", 0.12)

    if reply:

        match = re.search(
            r"(-?\d+)\s*,\s*(-?\d+)",
            reply,
        )

        if match:

            return (
                float(match.group(1)),
                float(match.group(2)),
            )

    return None


def get_active_window():

    return hypr_json(
        ["activewindow"],
        timeout=0.18
    )


# ============================================================
# PAN WHOLE DESKTOP
# ============================================================

def pan_desktop(
    dx,
    dy,
):

    with state_lock:

        if active_workspace is None:
            return

        cam = camera(active_workspace)

        # le finestre seguono il mouse: la camera va nel verso opposto
        cam[0] -= dx / cam[2]
        cam[1] -= dy / cam[2]

    sync_windows()


# ============================================================
# WINDOW DRAG
# ============================================================

def begin_window_drag():

    global drag_address

    address = None

    # finestra floating sotto il cursore (la più recentemente usata);
    # non ci si affida solo alla finestra attiva perché Hyprland potrebbe
    # non aver ancora elaborato il click che l'ha messa a fuoco
    clients = hypr_json(["clients"], timeout=0.3)
    cursor = get_cursor_position()

    if isinstance(clients, list) and cursor is not None:

        cx, cy = cursor
        best = None

        for client in clients:

            if not client.get("floating"):
                continue

            if not client.get("mapped", True):
                continue

            workspace = (client.get("workspace") or {}).get("id")

            if workspace != active_workspace:
                continue

            at = client.get("at")
            size = client.get("size")

            if not at or not size or len(at) < 2 or len(size) < 2:
                continue

            if not (
                at[0] <= cx < at[0] + size[0]
                and at[1] <= cy < at[1] + size[1]
            ):
                continue

            rank = client.get("focusHistoryID", 10**6)

            if best is None or rank < best[0]:
                best = (rank, client.get("address"))

        if best is not None:
            address = best[1]

    if address is None:

        active = get_active_window()

        if active and active.get("floating"):
            address = active.get("address")

    if not address:
        return

    with state_lock:

        if address in windows:

            drag_address = address


def end_window_drag():

    global drag_address

    drag_address = None


def _axis_push(pos, size, delta, low, high):
    """Di quanto (px schermo) deve scorrere il canvas su un asse.

    La finestra si muove liberamente finché non entra nella fascia di
    EDGE_MARGIN px dal bordo; oltre, resta lì e scorre il canvas.
    """

    new = pos + delta

    if delta < 0:

        limit = low + EDGE_MARGIN

        if new < limit:
            return max(new - limit, delta)

    elif delta > 0:

        limit = high - EDGE_MARGIN

        if new + size > limit:
            return min(new + size - limit, delta)

    return 0.0


def drag_window(
    dx,
    dy,
):

    with state_lock:

        if not drag_address:
            return

        window = windows.get(
            drag_address
        )

        if not window:
            return

        if window.workspace != active_workspace:
            return

        cam = camera(window.workspace)
        z = cam[2]

        move_x = dx * WINDOW_DRAG_SPEED
        move_y = dy * WINDOW_DRAG_SPEED

        sx, sy, sw, sh = screen_rect(window, cam)

        scroll_x = _axis_push(
            sx, sw, move_x,
            monitor["left"], monitor["right"],
        )

        scroll_y = _axis_push(
            sy, sh, move_y,
            monitor["top"], monitor["bottom"],
        )

        # la finestra si sposta di tutto il delta nel mondo; se la camera
        # scorre della stessa quota, a schermo resta ferma al bordo
        # e tutte le altre vengono spinte nel verso opposto
        window.x += move_x / z
        window.y += move_y / z

        cam[0] += scroll_x / z
        cam[1] += scroll_y / z

    sync_windows()


# ============================================================
# ZOOM CENTERED ON MOUSE
# ============================================================

def zoom_at_mouse(
    direction,
):

    global zoom

    # se uno zoom è ancora in corso, questo evento (tasto in repeat)
    # viene scartato: così non si accumula una coda di zoom
    if not zoom_lock.acquire(blocking=False):
        return

    try:

        cursor = get_cursor_position()

        if cursor is None:
            return

        mouse_x, mouse_y = cursor

        with state_lock:

            if active_workspace is None:
                return

            cam = camera(active_workspace)

            old_zoom = cam[2]

            if direction > 0:
                new_zoom = old_zoom * ZOOM_STEP
            else:
                new_zoom = old_zoom / ZOOM_STEP

            new_zoom = max(
                MIN_ZOOM,
                min(MAX_ZOOM, new_zoom),
            )

            if math.isclose(old_zoom, new_zoom):
                return

            # punto del mondo sotto il cursore: deve restare sotto il cursore
            world_x = cam[0] + mouse_x / old_zoom
            world_y = cam[1] + mouse_y / old_zoom

            cam[0] = world_x - mouse_x / new_zoom
            cam[1] = world_y - mouse_y / new_zoom
            cam[2] = new_zoom

            zoom = new_zoom

        sync_windows()

    finally:
        zoom_lock.release()


# ============================================================
# HYPRLAND EVENT SOCKET
# ============================================================

def event_listener():

    socket_path = _socket_path(".socket2.sock")

    if socket_path is None:
        return

    watched_events = {
        "workspace",
        "workspacev2",
        "focusedmon",
        "openwindow",
        "closewindow",
        "movewindowv2",
        "changefloatingmode",
        "configreloaded",
        "monitoradded",
        "monitorremoved",
    }

    while running:

        try:

            with socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM,
            ) as sock:

                sock.connect(
                    socket_path
                )

                buffer = b""

                while running:

                    data = sock.recv(
                        4096
                    )

                    if not data:
                        break

                    buffer += data

                    while b"\n" in buffer:

                        line, buffer = (
                            buffer.split(
                                b"\n",
                                1,
                            )
                        )

                        line = line.decode(
                            errors="ignore"
                        )

                        if ">>" not in line:
                            continue

                        event = line.split(
                            ">>",
                            1,
                        )[0]

                        if event in watched_events:

                            invalidate_cache()

            time.sleep(0.25)

        except Exception:

            time.sleep(
                0.25
            )


# ============================================================
# INPUT DEVICE DETECTION
# ============================================================

def classify_device(
    path,
):

    try:

        device = InputDevice(
            path
        )

        capabilities = (
            device.capabilities()
        )

        device.close()

    except Exception:

        return None

    keys = set(
        capabilities.get(
            ecodes.EV_KEY,
            [],
        )
    )

    relative = set(
        capabilities.get(
            ecodes.EV_REL,
            [],
        )
    )

    if (
        ecodes.REL_X in relative
        and ecodes.REL_Y in relative
        and ecodes.BTN_LEFT in keys
    ):
        return "mouse"

    if (
        ecodes.KEY_A in keys
        and ecodes.KEY_Z in keys
        and ecodes.KEY_LEFTSHIFT in keys
        and (
            ecodes.KEY_LEFTMETA in keys
            or ecodes.KEY_RIGHTMETA in keys
        )
    ):
        return "keyboard"

    return None


# ============================================================
# ANIMAZIONI DI HYPRLAND: sospese durante pan e drag
# ============================================================
#
# Con le animazioni attive ogni spostamento fa partire un'animazione
# verso il nuovo punto; con ~170 spostamenti al secondo le finestre
# inseguono il bersaglio invece di seguire il mouse. Si sospendono solo
# mentre serve, poi si ripristinano il valore originale.

def _animations_enabled():

    data = hypr_json(["getoption", "animations:enabled"])

    if isinstance(data, dict):

        if "int" in data:
            return bool(data["int"])

        if "bool" in data:
            return bool(data["bool"])

    return None


def _apply_animations(enabled):
    """Cambia animations:enabled e verifica che sia cambiato davvero.

    Con la config Lua di Hyprland `keyword` non funziona ("Use eval"),
    quindi si prova prima `eval` e poi, per le config legacy, `keyword`.
    """

    flag = "true" if enabled else "false"

    attempts = (
        f"eval hl.config({{ animations = {{ enabled = {flag} }} }})",
        f"keyword animations:enabled {flag}",
    )

    for payload in attempts:

        reply = hypr_request(payload)

        debug("animazioni:", payload, "->", repr(reply))

        if _animations_enabled() == enabled:
            return True

    return False


def set_animations(suspend):

    global anim_suspended
    global anim_restore_failures

    with anim_lock:

        if suspend:

            if anim_suspended:
                return

            current = _animations_enabled()

            if not current:
                # già spente (o valore illeggibile): niente da ripristinare
                debug("animazioni: stato attuale", current, "- non tocco")
                return

            if _apply_animations(False):

                anim_suspended = True
                anim_restore_failures = 0

                debug("animazioni sospese")

            else:
                debug("animazioni: impossibile sospenderle")

        else:

            if not anim_suspended:
                return

            if _apply_animations(True):

                anim_suspended = False
                debug("animazioni ripristinate")

            else:

                anim_restore_failures += 1

                # dopo 3 tentativi si smette di riprovare, ma lo si dice
                if anim_restore_failures >= 3:

                    anim_suspended = False

                    print(
                        "infinite-desktop: ATTENZIONE, non riesco a "
                        "riattivare le animazioni. Esegui: hyprctl eval "
                        "'hl.config({ animations = { enabled = true } })'",
                        file=sys.stderr,
                        flush=True,
                    )


def refresh_animation_state():
    """Animazioni spente solo durante pan (Super+Alt) o drag (Super+click)."""

    with state_lock:
        want_off = (super_down and alt_down) or bool(drag_address)

    set_animations(want_off)


# ============================================================
# GRAB DEL MOUSE SOLO DURANTE SUPER+ALT
# ============================================================

def set_mouse_grab(active):
    """Blocca/sblocca il mouse per Hyprland (evdev grab).

    Durante il pan il cursore resta fermo: lo script continua a ricevere
    i movimenti grezzi. Se il processo muore, il kernel rilascia il grab.
    """

    global mouse_grabbed

    with state_lock:

        if active == mouse_grabbed:
            return

        mouse_grabbed = active
        devices = list(mouse_devices)

    for device in devices:

        try:

            if active:
                device.grab()
            else:
                device.ungrab()

        except Exception as exc:
            debug("grab/ungrab del mouse non riuscito:", exc)


# ============================================================
# MOUSE READER
# ============================================================

def mouse_reader(
    path,
):

    global mouse_dx
    global mouse_dy
    global left_down

    try:

        device = InputDevice(
            path
        )

    except Exception:

        return

    with state_lock:
        mouse_devices.append(device)

    try:

        for event in device.read_loop():

            start_drag = False
            stop_drag = False

            with state_lock:

                if (
                    event.type
                    == ecodes.EV_KEY
                    and event.code
                    == ecodes.BTN_LEFT
                ):

                    left_down = (
                        event.value == 1
                    )

                    if (
                        left_down
                        and super_down
                        and not alt_down
                        and not ctrl_down
                    ):

                        start_drag = True

                    elif not left_down:

                        stop_drag = True

                elif (
                    event.type
                    == ecodes.EV_REL
                ):

                    if event.code == ecodes.REL_X:

                        mouse_dx += (
                            event.value
                        )

                    elif event.code == ecodes.REL_Y:

                        mouse_dy += (
                            event.value
                        )

            # l'I/O verso Hyprland avviene FUORI dal lock: prima
            # bloccava tutti i thread per la durata della richiesta
            if start_drag:
                begin_window_drag()
                refresh_animation_state()

            elif stop_drag:
                end_window_drag()
                refresh_animation_state()

    except Exception:

        pass

    finally:

        with state_lock:

            if device in mouse_devices:
                mouse_devices.remove(device)

        try:
            device.close()
        except Exception:
            pass


# ============================================================
# QUICKSHELL: nasconde il frame di Caelestia durante SUPER+ALT
# ============================================================

def notify_quickshell_hold(_state=None):
    """Invia lo stato più recente a Quickshell.

    Gira in un thread separato e fuori da state_lock. Ogni thread invia lo
    stato corrente al momento del suo turno, quindi anche con pressioni
    molto rapide l'ultimo comando inviato è sempre quello giusto.
    """

    with hold_lock:

        with state_lock:
            hidden = frame_held_hidden

        try:

            subprocess.run(
                QS_HOLD_COMMAND + ["true" if hidden else "false"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )

        except Exception:
            pass


# ============================================================
# KEYBOARD READER (sola lettura, nessun grab)
# ============================================================

def keyboard_reader(
    path,
):

    global super_down
    global alt_down
    global ctrl_down
    global frame_held_hidden

    try:

        device = InputDevice(
            path
        )

    except Exception:

        return

    try:

        for event in device.read_loop():

            if event.type != ecodes.EV_KEY:
                continue

            code = event.code
            value = event.value

            zoom_direction = 0
            notify = False
            hold_state = False

            with state_lock:

                if code in META_KEYS:
                    super_down = value != 0

                elif code in ALT_KEYS:
                    alt_down = value != 0

                elif code in CTRL_KEYS:
                    ctrl_down = value != 0

                elif (
                    value in (1, 2)
                    and super_down
                    and alt_down
                ):

                    if code in ZOOM_IN_KEYS:
                        zoom_direction = 1

                    elif code in ZOOM_OUT_KEYS:
                        zoom_direction = -1

                combo = super_down and alt_down

                if combo != frame_held_hidden:

                    frame_held_hidden = combo
                    hold_state = combo
                    notify = True

            # fuori dal lock
            if notify:

                set_mouse_grab(hold_state)
                refresh_animation_state()

                threading.Thread(
                    target=notify_quickshell_hold,
                    daemon=True,
                ).start()

            if zoom_direction:

                # un repeat già vecchio di 50 ms è arretrato: lo scarto
                if (
                    value == 2
                    and time.time() - event.timestamp() > 0.05
                ):
                    continue

                zoom_at_mouse(
                    zoom_direction
                )

    except Exception:

        pass

    finally:

        try:
            device.close()
        except Exception:
            pass


# ============================================================
# MAIN
# ============================================================

def _stop(*_):

    global running

    running = False


def main():

    global running
    global mouse_dx
    global mouse_dy
    global frame_held_hidden

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    refresh_windows()

    threading.Thread(target=cache_thread, daemon=True).start()
    threading.Thread(target=event_listener, daemon=True).start()

    mice = 0
    keyboards = 0

    for path in list_devices():

        kind = classify_device(path)

        if kind == "mouse":

            threading.Thread(
                target=mouse_reader,
                args=(path,),
                daemon=True,
            ).start()

            mice += 1

        elif kind == "keyboard":

            threading.Thread(
                target=keyboard_reader,
                args=(path,),
                daemon=True,
            ).start()

            keyboards += 1

    print(
        f"infinite-desktop v{VERSION}: {mice} mouse, {keyboards} tastiere",
        flush=True,
    )

    if not mice or not keyboards:
        print(
            "infinite-desktop: dispositivi mancanti "
            "(controlla i permessi su /dev/input, gruppo 'input')",
            file=sys.stderr,
            flush=True,
        )

    next_frame = time.monotonic()

    while running:

        with state_lock:

            dx = mouse_dx
            dy = mouse_dy

            # sempre azzerati: i movimenti fatti senza combinazione
            # non devono causare salti quando la combinazione parte
            mouse_dx = 0.0
            mouse_dy = 0.0

            panning = super_down and alt_down
            dragging = bool(drag_address) and left_down

        # rete di sicurezza: se per qualsiasi motivo il mouse è rimasto
        # bloccato ma SUPER+ALT non è più premuto, lo si libera
        if mouse_grabbed and not panning:
            set_mouse_grab(False)

        if anim_suspended and not panning and not dragging:
            set_animations(False)

        if not panning and not dragging:

            time.sleep(0.02)
            next_frame = time.monotonic()
            continue

        if dx or dy:

            if panning:

                pan_desktop(
                    dx * PAN_SPEED,
                    dy * PAN_SPEED,
                )

            else:

                drag_window(
                    dx,
                    dy,
                )

        next_frame += FRAME_TIME
        delay = next_frame - time.monotonic()

        if delay > 0:
            time.sleep(delay)
        else:
            next_frame = time.monotonic()

    # uscita pulita: libera il mouse, riattiva le animazioni e rimetti
    # il frame di Caelestia
    set_mouse_grab(False)
    set_animations(False)

    with state_lock:
        hidden = frame_held_hidden

    if hidden:

        with state_lock:
            frame_held_hidden = False

        notify_quickshell_hold()


if __name__ == "__main__":
    main()
