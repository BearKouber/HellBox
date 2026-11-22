# HellBox

A free, open-source (MIT) mod toolbox for **HELLDIVERS™ 1** (Steam, Windows): quality-of-life fixes, extra play modes, enemy / spawn tweaks and more, all switched on and off from one window.

[中文说明在下面](#中文)

> **Download:** the ready-to-use build is on Nexus Mods: https://www.nexusmods.com/helldivers/mods/63
> This repository is the source code.

## What it does

- **Features:** small quality-of-life switches, e.g. drop your support weapon or backpack, reload bug fix, carry objective boxes into vehicles, refresh planets, quick voice lines, teammate ping on the HUD (from Dive Harder), a "Hide HellBox games" room filter.
- **Display:** readable names (name plates, long names cut cleanly).
- **Play modes:** Proving Grounds modes online, stackable field events, random stratagem drops, Ghost Town, room loadout rules, saved presets; players who also run HellBox can follow the host's settings.
- **Data:** enemy stats and spawn rules for your own room.
- **Cursor:** aim cursor colour.

## Install / remove

1. Unzip the release anywhere you can write to (not *Program Files*).
2. Close the game, run `HellBox.exe`, and turn the core on under **About → Settings**.
3. To go back to vanilla: turn the core off in the same place.

HellBox does not replace game files. It adds patch files next to them (`<package>.patch_N` in the game's `contents` folder) and removes them again when the core is turned off; the original files stay vanilla.

**Other mods:** HellBox can be installed together with Obsidian (Alomare's mod manager): neither removes the other's patches, and HellBox steps back where both offer the same feature. Mods that change the same resources can still conflict; HellBox warns about the ones it knows. HellBox also works together with **QoL Mod** and **Dive Harder** in any combination: it installs on whichever boot package the game uses, "Restore vanilla" never touches their files, and the Dive Harder features included in HellBox step aside when Dive Harder is installed.

**Multiplayer:** players without HellBox can still join you. When you join someone else's room, your data changes are not applied there (vanilla rules); feature switches still work for you.

<sub>Hidden developer mode: click the version number on the About page 10 times. It adds detailed per-enemy / per-weapon editing, logs, split screen and Map Select. Use at your own risk.</sub>

Have fun, and don't spoil other players' games.

<!-- ☕ If you enjoy HellBox you can buy me a coffee: (link) -->

## Build from source

- Windows, Python 3.12+ (developed on 3.14), `pip install -r requirements.txt`
- LuaJIT 2.0 (built from [LuaJIT/LuaJIT](https://github.com/LuaJIT/LuaJIT), branch `v2.0`) in `tools/luajit-2.0/` (`src/luajit.exe`, `src/lua51.dll`, `src/jit/`, `COPYRIGHT`). HellBox uses it to compile its Lua scripts when installing the core.
- Run from source: `python hellbox/app.py`
- Package like the release: `python hellbox/make_exe.py --public` (PyInstaller, output in `.work/hellbox-public/HellBox`: `HellBox.exe` + `_internal`, with `mod`, `ai` and `tools` next to it as plain files). `--public --portable` is an alternative that ships the official, signed Python embeddable package plus HellBox compiled to `.pyc` (`hellbox/make_portable.py`) instead of PyInstaller.
- Split screen: `mod/camera/runtime.luac` is HalfSugar's CameraCTRL module, compiled from `camera-src/` (CameraCTRL with HellBox's camera changes: original single-player follow and camera shake, plus `BridgeCore`) with `python camera-src/CameraCTRL/bridge/compile.py <path to luajit.exe>`. When the core is installed, `mod/camera_stack.py` (a Python port of BridgeCore's install step) adds it to the game's boot script.
- `mod/src/hellbox_hop.lua` is generated from `mod/hop/` by `python tools/make_hop.py`.

No original game files are in this repository. When the core is installed, HellBox reads the two original scripts it extends (`character_state_machine`, `character_state_carry`) from your own game files and runs them unchanged, with HellBox's code added after them.

Layout: `hellbox/` the window (PySide6), `mod/` installing the core and the in-game Lua scripts (`mod/src`, `mod/hop`), `ai/` data tables, `mod/camera/` split screen (built from `camera-src/`).

## License and credits

HellBox's own code is under the [MIT license](LICENSE). Third-party parts keep their own licenses or terms, listed at the end of [LICENSE](LICENSE).

- Split screen: **CameraCTRL** by **HalfSugar**, and the **HelldiversOptimization** fixes (`mod/hop/`) by **HalfSugar**, both included and published with the author's permission. Chat IME crash fix: HalfSugar. Self-resupply and hide sample outlines: Lhgrzr. HUD ping, hidden objectives, friends list refresh and two QoL Mod fixes come from **Dive Harder** by **Oct0pu5** (MIT, included with permission; `mod/src/hellbox_dh.lua`). Thanks to **SomeDoggo** (QoL Mod).
- Outer UI design: 91 · High-difficulty data guidance: 吃大份 · Testing: 91, HalfSugar, 吃大份, K-ON!, Kent, QiQi · Overall UI planning and code design: Claude
- Features borrowed from other mods name their source under the feature in HellBox.
- Font: Silkscreen (SIL Open Font License, `hellbox/fonts/OFL.txt`). LuaJIT © Mike Pall (MIT). Release builds also contain Python (PSF license), PySide6 / Qt (LGPL-3.0) and pymem (MIT).

Unofficial fan mod, not affiliated with Arrowhead Game Studios or Sony Interactive Entertainment. HELLDIVERS is a trademark of Sony Interactive Entertainment.

---

## 中文

HELLDIVERS™ 1（Steam / Windows）的免费开源（MIT）MOD 工具箱：小功能修正、额外玩法、怪物 / 出怪调整等，都在一个窗口里开关。

> **下载：** 成品在 Nexus Mods：https://www.nexusmods.com/helldivers/mods/63。这个仓库是源码。

**安装 / 卸载**
1. 解压到能写入的文件夹（不要放 Program Files）。
2. 关着游戏打开 `HellBox.exe`，在「关于 → 设置」里打开核心。
3. 想回原版：同一个地方关掉核心。

HellBox 不替换游戏文件，而是在游戏的 contents 文件夹里放补丁文件（`<包名>.patch_N`），关掉核心就拿掉，游戏原文件一直是原版。

**和别的 MOD：** 能和 Obsidian（Alomare 的 MOD 管理器）一起装：两边谁也不删谁的补丁，两边都有的功能 HellBox 让出。改同样资源的 MOD 还是可能冲突，HellBox 认得的会提醒。也能和 **QoL Mod**、**Dive Harder** 任意组合一起装：HellBox 装在游戏当前用的启动包上，「恢复原版」不碰它们的文件；HellBox 里来自 Dive Harder 的几项在装了 Dive Harder 时交给它。

**联机：** 没装 HellBox 的人也能进你的房间。你进别人的房间时，你改的数据不生效（按原版），功能开关照常。

<sub>隐藏的开发者模式：「关于」页的版本号连点 10 次。多出按单只怪 / 单把枪细改、日志、分屏、选图，风险自负。</sub>

希望大家玩得开心，也请不要影响别的玩家。

<!-- ☕ 喜欢的话可以请我喝杯咖啡：（链接） -->

**从源码构建：** 见上面英文的 *Build from source*。发行版用 PyInstaller 打（`python hellbox/make_exe.py --public`）。

**授权：** HellBox 自己的代码按 [MIT](LICENSE) 授权，可以自由修改、再发布，请保留作者 07 的署名和授权说明，并注明原发布页。收录的别人的作品（分屏、半糖的优化功能、Dive Harder 的几项等）归原作者，各自的说明在 [LICENSE](LICENSE) 末尾。花钱买到的请找卖家退款。非官方 MOD，和游戏官方无关。
