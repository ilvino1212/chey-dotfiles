#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/share/chey-dotfiles"
BACKUP_DIR="$HOME/.local/share/chey-dotfiles-backup-$(date +%Y%m%d-%H%M%S)"

DRY_RUN=0
CHECK_ONLY=0

case "${1:-}" in
    --check)
        CHECK_ONLY=1
        ;;
    --dry-run)
        DRY_RUN=1
        ;;
    --help|-h)
        echo "Usage: ./install.sh [--check|--dry-run]"
        echo
        echo "  --check      Check dependencies without changing anything"
        echo "  --dry-run    Show what would be installed"
        echo "  no argument  Install the dotfiles"
        exit 0
        ;;
    "")
        ;;
    *)
        echo "Unknown option: $1"
        echo "Use ./install.sh --help"
        exit 1
        ;;
esac

echo
echo "╭──────────────────────────────────────╮"
echo "│        Chey Dotfiles Installer       │"
echo "╰──────────────────────────────────────╯"
echo

missing_required=()

check_command() {
    local cmd="$1"

    if command -v "$cmd" >/dev/null 2>&1; then
        printf "  ✓ %s\n" "$cmd"
    else
        printf "  ✗ %s\n" "$cmd"
        missing_required+=("$cmd")
    fi
}

echo "==> Required dependencies"

check_command fish
check_command python3
check_command hyprctl
check_command fastfetch
check_command chafa

if python3 -c "import evdev" >/dev/null 2>&1; then
    echo "  ✓ python evdev"
else
    echo "  ✗ python evdev"
    missing_required+=("python-evdev")
fi

echo
echo "==> Optional dependencies"

optional_commands=(
    starship
    direnv
    zoxide
    eza
    lazygit
    kitty
    foot
    fuzzel
    openrgb
)

for cmd in "${optional_commands[@]}"; do
    if command -v "$cmd" >/dev/null 2>&1; then
        printf "  ✓ %s\n" "$cmd"
    else
        printf "  - %s (optional)\n" "$cmd"
    fi
done

if ((${#missing_required[@]} > 0)); then
    echo
    echo "Missing required dependencies:"
    printf "  - %s\n" "${missing_required[@]}"
    echo
    echo "Install the missing dependencies with your distribution's"
    echo "package manager, then run ./install.sh again."
    exit 1
fi

if ((CHECK_ONLY)); then
    echo
    echo "✓ Dependency check passed."
    exit 0
fi

echo
echo "==> Files that will be installed"

while IFS= read -r -d "" file; do
    rel="${file#"$REPO_DIR/home/"}"
    printf "  ~/%s\n" "$rel"
done < <(find "$REPO_DIR/home" -type f -print0 | sort -z)

echo
echo "==> Data that will be installed"
echo "  $INSTALL_DIR/scripts/"
echo "  $INSTALL_DIR/assets/"

if ((DRY_RUN)); then
    echo
    echo "✓ Dry run complete. Nothing was changed."
    exit 0
fi

echo
echo "==> Creating backup"

backup_created=0

backup_file() {
    local rel="$1"
    local target="$HOME/$rel"

    if [[ -e "$target" || -L "$target" ]]; then
        mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
        cp -a "$target" "$BACKUP_DIR/$rel"
        printf "  backup: ~/%s\n" "$rel"
        backup_created=1
    fi
}

while IFS= read -r -d "" file; do
    rel="${file#"$REPO_DIR/home/"}"
    backup_file "$rel"
done < <(find "$REPO_DIR/home" -type f -print0)

echo
echo "==> Installing dotfiles"

mkdir -p "$HOME/.local"
cp -a "$REPO_DIR/home/." "$HOME/"

echo
echo "==> Installing Chey Dotfiles data"

mkdir -p "$INSTALL_DIR/scripts" "$INSTALL_DIR/assets"

cp -a "$REPO_DIR/scripts/." "$INSTALL_DIR/scripts/"
cp -a "$REPO_DIR/assets/." "$INSTALL_DIR/assets/"

echo
echo "==> Setting permissions"

find "$INSTALL_DIR/scripts" -type f -name "*.py" -exec chmod +x {} +

chmod +x \
    "$HOME/.local/bin/fastfetch-adaptive" \
    "$HOME/.local/bin/wraith-white"

echo
echo "==> Verifying installed files"

failed=0

verify_file() {
    local file="$1"

    if [[ -f "$file" ]]; then
        printf "  ✓ %s\n" "$file"
    else
        printf "  ✗ %s\n" "$file"
        failed=1
    fi
}

verify_file "$HOME/.config/fish/config.fish"
verify_file "$HOME/.config/fish/functions/fish_greeting.fish"
verify_file "$HOME/.config/caelestia/hypr-user.lua"
verify_file "$HOME/.local/bin/fastfetch-adaptive"
verify_file "$HOME/.local/bin/wraith-white"
verify_file "$INSTALL_DIR/scripts/infinite-desktop/infinite_desktop_core.py"
verify_file "$INSTALL_DIR/assets/fastfetch/cicada_crop.png"
verify_file "$INSTALL_DIR/assets/fastfetch/cicada_transparent_white.png"

if ((failed)); then
    echo
    echo "✗ Installation verification failed."
    exit 1
fi

echo
echo "╭──────────────────────────────────────╮"
echo "│       Installation completed!        │"
echo "╰──────────────────────────────────────╯"
echo
echo "Dotfiles:     $HOME"
echo "Data:         $INSTALL_DIR"

if ((backup_created)); then
    echo "Backup:       $BACKUP_DIR"
else
    echo "Backup:       none needed"
fi

echo
echo "Restart your shell/session to apply everything."
echo
