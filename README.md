# HellBox

[English](README.md) | [中文](README_zh.md)

HellBox is created by **07**. **Current version: 1.09.**

A free, open-source (MIT) toolbox for **HELLDIVERS™ 1** on Steam / Windows: quality-of-life fixes, extra play modes, enemy and spawn tuning, and more — all switched on and off from one window.

> **Download:** the ready-to-use build is on Nexus Mods: https://www.nexusmods.com/helldivers/mods/63  
> This repository contains the source code.

## Features

- **Fixes:** reload bug fix, carry objective boxes into vehicles, drop your support weapon or backpack, and other small quality-of-life switches.
- **Display:** readable name plates and clean handling of long names.
- **Play modes:** Proving Grounds modes online, stackable field events, random stratagem drops, Ghost Town, room loadout rules, and saved presets. Players who also use HellBox can follow the host's settings.
- **Map Select (developer mode):** choose mission type, race, environment, time and difficulty, preview the map, pick a terrain, and keep up to eight map presets.
- **Data:** enemy stats and spawn rules for your own room.
- **Cursor:** aim cursor colour and preview.
- **Extras:** quick voice lines, faster cutscenes (QoL Mod compatible), planet refresh, teammate ping on the HUD (from Dive Harder), and a "Hide HellBox games" room filter.
- **Other fronts:** unlock normal sectors, a homeworld assault or the Super Earth defence locally, with homeworld missions that can be rerolled. These missions are not reported to the Galactic War.

## Install and remove

1. Unzip the release into a folder you can write to (not *Program Files*).
2. Close the game, run `HellBox.exe`, and turn the core on under **About → Settings**.
3. To return to vanilla, turn the core off in the same place.

HellBox does not replace game files. It adds patch files next to them (`<package>.patch_N` in the game's `contents` folder) and removes them when the core is turned off. The original files stay vanilla.

**Other mods:** HellBox can be installed together with Obsidian (Alomare's mod manager): neither removes the other's patches, and HellBox steps back where both offer the same feature. Mods that change the same resources can still conflict; HellBox warns about the ones it knows. HellBox also works together with **QoL Mod** and **Dive Harder**: it installs on whichever boot package the game uses, "Restore vanilla" never touches their files, and the Dive Harder features included in HellBox step aside when Dive Harder is installed.

**Multiplayer:** HellBox only changes your own game. Players without HellBox can still join you. As host, your enemy / spawn edits and play modes apply to your room, and the room name is tagged `[HellBox]`, so everyone can see it is modded (HellBox users can hide such rooms with the "Hide HellBox games" filter). When you join someone else's room, your data changes are not applied there (vanilla rules); most feature switches still work for you (carrying boxes into vehicles, dropping support gear, self-resupply, auto-locating objectives and split screen only work in rooms whose host also runs HellBox or has CameraCTRL split screen on), and teammates who also use HellBox can choose to follow the host's play modes.

<sub>Hidden developer mode: click the version number on the About page 10 times. It adds per-enemy / per-spawn-source data editing and the Map Select, Split screen, Helldiver and Log pages. Use at your own risk.</sub>

Have fun, and don't spoil other players' games.

## Build from source

HellBox is a Python 3.12+ / PySide6 application (developed on Windows).

```bat
pip install -r requirements.txt
python hellbox/app.py
```

LuaJIT 2.0 is needed to compile the Lua scripts when the core is installed. Put it in `tools/luajit-2.0/` with `src/luajit.exe`, `src/lua51.dll`, `src/jit/` and `COPYRIGHT` (build from [LuaJIT/LuaJIT](https://github.com/LuaJIT/LuaJIT), branch `v2.0`).

**Local build** (the normal build):

```bat
python hellbox/make_exe.py
```

This creates `bin\HellBox\HellBox.exe` (PyInstaller, one folder). It also points a `HellBox.lnk` shortcut in the repository root at it.

**Release-style build:**

```bat
python hellbox/make_exe.py --public
```

The result is in `.work\hellbox-public\HellBox`: `HellBox.exe` + `_internal`, with `mod`, `ai` and `tools` next to it as plain files. `--public --portable` is an alternative that ships the official Python embeddable package plus HellBox compiled to `.pyc` (`hellbox/make_portable.py`) instead of PyInstaller.

### If HellBox cannot save settings: `fix-save.bat`

On Windows a copied, extracted or freshly built folder can inherit a **Low** integrity label. HellBox then starts, but may fail to save settings with an error such as:

```
Permission denied: ...\play.txt.tmp
```

`fix-save.bat` restores the **Medium** integrity label on the built app folder and starts HellBox. Run it **as administrator** (right-click → *Run as administrator*). It expects the build next to it, at `bin\HellBox` in the repository root.

If your build is somewhere else, edit the `set "B=..."` line at the top of the file first. It only changes the folder's integrity label, not the file contents, and then launches `HellBox.exe`; close HellBox before running it. You normally need it only when saving fails after a build or copy.

### Optional components

- Split screen: `mod/camera/runtime.luac` is HalfSugar's CameraCTRL module, built from `camera-src/` (CameraCTRL with HellBox's camera changes and `BridgeCore`). Rebuild it with `python camera-src/CameraCTRL/bridge/compile.py <path to luajit.exe>`. When the core is installed, `mod/camera_stack.py` adds it to the game's boot script.
- `mod/src/hellbox_hop.lua` is generated from `mod/hop/` with `python tools/make_hop.py`.

No original game files are in this repository. When the core is installed, HellBox reads the two original scripts it extends (`character_state_machine`, `character_state_carry`) from your own game files and runs them unchanged, with HellBox's code added after them.

## Project layout

- `hellbox/` — the PySide6 window.
- `mod/` — core installation and in-game Lua scripts (`mod/src`, `mod/hop`); `mod/camera/` is split screen.
- `ai/` — data tables.
- `camera-src/` — CameraCTRL sources for split screen.
- `tools/` — build helpers (including LuaJIT).

## Credits and license

HellBox was created by **07**; its own code is under the [MIT license](LICENSE). Third-party parts keep their own licenses or terms, listed at the end of [LICENSE](LICENSE).

- **Split screen:** CameraCTRL by **HalfSugar**.
- **Input-method crash fix:** **HalfSugar**.
- **HelldiversOptimization fixes** (`mod/hop/`) by **HalfSugar**, included and published with the author's permission.
- **Dive Harder:** HUD ping, hidden objectives, friends-list refresh and two QoL Mod fixes by **Oct0pu5** (MIT, included with permission; `mod/src/hellbox_dh.lua`).
- **QoL Mod:** **SomeDoggo**.
- Self-resupply and hide sample outlines: **Lhgrzr**.
- Outer UI design: **91** · high-difficulty data guidance: **吃大份** · testing: **91, HalfSugar, 吃大份, K-ON!, Kent, QiQi** · overall planning and code: **Claude**.
- **Text:** **Oct0pu5**.
- Features borrowed from other mods name their source under the feature in HellBox.

Font: Silkscreen (SIL Open Font License, `hellbox/fonts/OFL.txt`). LuaJIT © Mike Pall (MIT). Release builds also contain Python (PSF license), PySide6 / Qt (LGPL-3.0) and pymem (MIT).

Unofficial fan mod, not affiliated with Arrowhead Game Studios or Sony Interactive Entertainment. HELLDIVERS is a trademark of Sony Interactive Entertainment.
