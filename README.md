# Chey Dotfiles

https://github.com/user-attachments/assets/f20f58f9-297b-4484-8c2e-f6a25a0f19cc

My personal dotfiles for **CachyOS + Hyprland**.

I made this repository because I got tired of having to remember and redo every little configuration change whenever I reinstall Linux.

The idea is simple: clone the repo, run the installer, and get most of my setup back.

This is mainly made for my own system, so don't expect everything here to work perfectly on another machine. Some parts are very specific to my hardware and setup.

---

## What's included

This repo currently contains my:

* Hyprland configuration
* Caelestia configuration
* Infinite Desktop scripts
* Fish shell configuration
* Starship configuration
* Fastfetch configuration
* GTK and Qt configuration
* Terminal configuration
* UWSM environment
* Custom scripts and utilities
* Wallpapers/assets used by the setup

There are also some older theme files that came from my previous setup and are still used by a few applications.

---

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/ilvino1212/chey-dotfiles.git
cd chey-dotfiles
```

Then run:

```bash
chmod +x install.sh
./install.sh
```

The installer checks the required dependencies, backs up existing configuration files and then copies everything into the correct locations.

After installing, restart your session.

---

## Installer options

Check if the required dependencies are installed:

```bash
./install.sh --check
```

See what would be installed without actually changing anything:

```bash
./install.sh --dry-run
```

Show the available options:

```bash
./install.sh --help
```

---

## Backups

The installer doesn't just overwrite everything blindly.

If a file already exists, it gets backed up before being replaced.

Backups are stored in:

```text
~/.local/share/chey-dotfiles-backup-YYYYMMDD-HHMMSS/
```

So if something goes wrong, the previous configuration is still there.

---

## 🌌 Infinite Desktop

One of the main custom parts of this setup is my Infinite Desktop configuration.

### New Infinite Desktop

The repository now includes a new version of the Infinite Desktop core.

This is an experimental and personal project designed for Hyprland. It creates an infinite desktop-like environment and allows navigation and window movement beyond the normal workspace layout.

The current implementation includes:

- Infinite desktop-style navigation
- Mouse-based desktop movement
- Keyboard navigation
- Window movement between workspaces
- Floating-window panning
- Automatic mouse and keyboard detection
- Hyprland IPC integration
- Automatic startup with the Hyprland session

The new version is still under development and has several known issues. It is not professional or production-ready software and is mainly intended as an experimental part of this dotfiles setup.

The main script is:

```text
scripts/infinite-desktop/infinite_desktop_core25.py
```

The script can be started with:

```bash
python3 infinite_desktop_core25.py
```

It can also be started automatically when the Hyprland session starts.

The scripts live in:

```text
~/.local/share/chey-dotfiles/scripts/infinite-desktop/
```

They are integrated into Hyprland through:

```text
~/.config/caelestia/hypr-user.lua
```

### Keybinds

| Key / Input | Action |
| ----------- | ------ |
| `SUPER + ALT + Mouse` | Pan the infinite desktop |
| `SUPER + ALT + =` | Zoom in, centered on the cursor |
| `SUPER + ALT + -` | Zoom out, centered on the cursor |
| `SUPER + LMB` | Window dragging handled by Hyprland/Caelestia, not Infinite Desktop |

The `SUPER + ALT` mouse grab is active only while the modifier combination is held. The keyboard is never grabbed by Infinite Desktop, so normal Caelestia/Hyprland binds continue to work.

Other workspace and window-management binds in `hypr-user.lua` belong to the surrounding Hyprland/Caelestia configuration and are not handled by the Infinite Desktop core.

---

## 🧩 My setup

The desktop is basically:

```text
CachyOS
└── Hyprland
    ├── Caelestia
    ├── UWSM
    └── Infinite Desktop
```

Most of the configuration is kept under:

```text
~/.config/
```

while custom scripts and assets are installed under:

```text
~/.local/share/chey-dotfiles/
```

---

## 📁 Repository structure

```text
chey-dotfiles/
├── assets/
│   └── fastfetch/
│
├── home/
│   ├── .config/
│   │   ├── caelestia/
│   │   ├── fish/
│   │   ├── fastfetch/
│   │   ├── hypr/
│   │   ├── uwsm/
│   │   └── ...
│   │
│   └── .local/
│       └── bin/
│
├── scripts/
│   └── infinite-desktop/
│
├── install.sh
├── README.md
└── .gitignore
```

---

## Why I made this

I don't want my Linux setup to depend on me remembering a bunch of commands and configuration files.

If I reinstall CachyOS, the goal is to be able to do:

```bash
git clone https://github.com/ilvino1212/chey-dotfiles.git
cd chey-dotfiles
./install.sh
```

and have my usual environment back with as little manual work as possible.

This repository will probably change over time as I change my setup.

---

## Notes

These dotfiles are made for my own system, so they're not meant to be a universal configuration.

My hardware, monitor setup, installed software and some paths are specific to my machine.

If you want to use these dotfiles yourself, feel free to take whatever parts you like and change the rest.

---
