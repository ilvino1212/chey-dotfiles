-- Chey Dotfiles: Infinite Desktop

local scripts = os.getenv("HOME") .. "/.local/share/chey-dotfiles/scripts/infinite-desktop"

hl.on("hyprland.start", function()
    hl.exec_cmd(
        "python3 " .. scripts .. "/infinite_desktop_core25.py > /tmp/infinite-desktop.log 2>&1 &"
    )
end)

-- Infinite Desktop keybinds

hl.bind("SUPER" .. " + Z", hl.dsp.focus({ workspace = "-1" }))
hl.bind("SUPER" .. " + X", hl.dsp.focus({ workspace = "+1" }))
hl.bind("SUPER" .. " + SHIFT + Z", hl.dsp.window.move({ workspace = "-1" }))
hl.bind("SUPER" .. " + SHIFT + X", hl.dsp.window.move({ workspace = "+1" }))

hl.bind("SUPER" .. " + D",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/floating_tile_toggle.py"))

hl.bind("SUPER" .. " + left",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/navigate_windows.py left"))

hl.bind("SUPER" .. " + ALT + left",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window_tiled.py left"))

hl.bind("SUPER" .. " + SHIFT + left",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window.py left"),
    { repeating = true })

hl.bind("SUPER" .. " + CTRL + left",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/resize_window.py left"),
    { repeating = true })

hl.bind("SUPER" .. " + right",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/navigate_windows.py right"))

hl.bind("SUPER" .. " + ALT + right",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window_tiled.py right"))

hl.bind("SUPER" .. " + SHIFT + right",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window.py right"),
    { repeating = true })

hl.bind("SUPER" .. " + CTRL + right",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/resize_window.py right"),
    { repeating = true })

hl.bind("SUPER" .. " + up",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/navigate_windows.py up"))

hl.bind("SUPER" .. " + ALT + up",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window_tiled.py up"))

hl.bind("SUPER" .. " + SHIFT + up",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window.py up"),
    { repeating = true })

hl.bind("SUPER" .. " + CTRL + up",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/resize_window.py up"),
    { repeating = true })

hl.bind("SUPER" .. " + down",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/navigate_windows.py down"))

hl.bind("SUPER" .. " + ALT + down",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window_tiled.py down"))

hl.bind("SUPER" .. " + SHIFT + down",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/move_window.py down"),
    { repeating = true })

hl.bind("SUPER" .. " + CTRL + down",
    hl.dsp.exec_cmd("python3 " .. scripts .. "/resize_window.py down"),
    { repeating = true })
