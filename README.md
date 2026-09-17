# Chey Dotfiles

Personal Linux dotfiles focused on a clean, fast and highly customized Hyprland desktop.

This repository contains my shell configuration, terminal themes, GTK/Qt styling, Fastfetch setup, Caelestia integration and custom Infinite Desktop scripts.

The goal is simple: **clone the repository, run the installer, and get the setup without manually copying dozens of files.**

## Features

* Hyprland configuration through Caelestia user configuration
* Fish shell
* Starship prompt
* eza + zoxide
* Fastfetch with adaptive ASCII/image layout
* Noctalia-inspired GTK, Qt and terminal themes
* Alacritty, Kitty and Foot configurations
* Fuzzel launcher
* btop configuration
* Cava configuration
* Micro editor configuration
* OpenRGB helper script
* Custom Fastfetch assets
* Infinite Desktop window-management scripts
* Automated installation with backup support
* Dependency checking
* Dry-run mode

## Requirements

### Required

The installer expects these components to already be installed:

* `fish`
* `python3`
* `hyprctl`
* `fastfetch`
* `chafa`
* Python `evdev`

### Optional

These are used by parts of the configuration but are not required for the installer:

* `starship`
* `direnv`
* `zoxide`
* `eza`
* `lazygit`
* `kitty`
* `foot`
* `fuzzel`
* `openrgb`

The installer checks for all of them automatically.

> Package names may differ depending on your Linux distribution.

## Installation

Clone the repository:

```bash
git clone <YOUR-REPOSITORY-URL>
cd chey-dotfiles
```

Make sure the installer is executable:

```bash
chmod +x install.sh
```

Run it:

```bash
./install.sh
```

The installer will:

1. Check required dependencies.
2. Show the files that will be installed.
3. Create a timestamped backup of existing configuration files.
4. Install the dotfiles.
5. Install the custom scripts and assets.
6. Set the required executable permissions.
7. Verify the installation.

Restart your shell/session after installation.

## Dependency Check

To check whether the required dependencies are available without changing anything:

```bash
./install.sh --check
```

## Dry Run

To see what the installer would install without modifying anything:

```bash
./install.sh --dry-run
```

## Backups

Before overwriting existing configuration files, the installer creates a backup in:

```text
~/.local/share/chey-dotfiles-backup-YYYYMMDD-HHMMSS/
```

This makes it possible to recover the previous configuration if necessary.

## Infinite Desktop

The repository includes a custom window-management system called **Infinite Desktop**.

It provides custom Hyprland controls for:

* Moving between workspaces
* Moving windows between workspaces
* Navigating between windows
* Moving tiled windows
* Resizing windows
* Switching between floating and tiled behavior

The scripts are located in:

```text
scripts/infinite-desktop/
```

They are installed to:

```text
~/.local/share/chey-dotfiles/scripts/infinite-desktop/
```

The Hyprland integration is provided through:

```text
~/.config/caelestia/hypr-user.lua
```

## Keybinds

| Keybind                 | Action                            |
| ----------------------- | --------------------------------- |
| `SUPER + Z`             | Previous workspace                |
| `SUPER + X`             | Next workspace                    |
| `SUPER + SHIFT + Z`     | Move window to previous workspace |
| `SUPER + SHIFT + X`     | Move window to next workspace     |
| `SUPER + D`             | Toggle floating/tiled behavior    |
| `SUPER + Arrow`         | Navigate windows                  |
| `SUPER + ALT + Arrow`   | Move tiled window                 |
| `SUPER + SHIFT + Arrow` | Move window                       |
| `SUPER + CTRL + Arrow`  | Resize window                     |

## Repository Structure

```text
chey-dotfiles/
├── assets/
│   └── fastfetch/
│       ├── cicada_crop.png
│       └── cicada_transparent_white.png
│
├── home/
│   ├── .config/
│   │   ├── alacritty/
│   │   ├── btop/
│   │   ├── caelestia/
│   │   ├── cava/
│   │   ├── fastfetch/
│   │   ├── fish/
│   │   ├── foot/
│
```
