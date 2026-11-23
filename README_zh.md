# HellBox

[English](README.md) | [中文](README_zh.md)

HellBox 作者：**07**。**当前版本：1.09。**

**HELLDIVERS™ 1**（Steam / Windows）的免费开源（MIT）MOD 工具箱：功能修正、额外玩法、怪物与出怪调整等，都在一个窗口里开关。

> **下载：** 成品在 Nexus Mods：https://www.nexusmods.com/helldivers/mods/63  
> 这个仓库是源码。

## 功能

- **功能修正：** 换弹 Bug 修复、把任务箱子搬上车、丢掉支援武器 / 背包，以及其他小功能开关。
- **显示：** 更清楚的名字显示，长名字不会被截得乱七八糟。
- **玩法：** 试炼场玩法联机可用、可叠加的战场事件、随机战略配备掉落、鬼城、房间武装规则、玩法预设。也装了 HellBox 的队友可以选择跟随房主的设置。
- **选图（开发者模式）：** 选任务类型、种族、环境、时间和难度，预览地图、挑地形，并能保存 8 个地图存档。
- **数据：** 自己房间里的怪物属性和出怪规则。
- **指针：** 准星颜色和预览。
- **其他：** 快捷语音、过场加速（兼容 QoL Mod）、刷新星球、队友 HUD 标记（来自 Dive Harder）、「隐藏 HellBox 房间」筛选。
- **其他战线：** 可选普通星区、进攻母星或保卫超级地球，母星 5 关能刷新重抽；这些关只在自己游戏里打，不报给银河战争。

## 安装 / 卸载

1. 解压到能写入的文件夹（不要放 *Program Files*）。
2. 关着游戏打开 `HellBox.exe`，在「关于 → 设置」里打开核心。
3. 想回原版：在同一个地方关掉核心。

HellBox 不替换游戏文件，而是在游戏的 `contents` 文件夹里放补丁文件（`<包名>.patch_N`），关掉核心就拿掉，游戏原文件一直是原版。

**和别的 MOD 一起用：** 可以和 Obsidian（Alomare 的 MOD 管理器）一起装：两边谁也不删谁的补丁，两边都有的功能 HellBox 让出。改同样资源的 MOD 还是可能冲突，HellBox 认得的会提醒。也能和 **QoL Mod**、**Dive Harder** 任意组合：HellBox 装在游戏当前用的启动包上，「恢复原版」不碰它们的文件；HellBox 里来自 Dive Harder 的几项在装了 Dive Harder 时交给它。

**联机：** HellBox 只改你自己的游戏，没装 HellBox 的人也能进你的房间。你当房主时，改的怪物 / 出怪和玩法在你的房间里生效，房间名会带 `[HellBox]` 标记，大家一看就知道是改过的房间（装了 HellBox 的人还能用「隐藏 HellBox 房间」筛掉）。你进别人的房间时，你改的数据不生效（按原版），功能开关大多照常（带箱子上车、丢支援装备、补给背包自己用、自动定位任务位置、分屏只在房主也装了 HellBox 或开着 CameraCTRL 分屏的房间生效）；队友也装了 HellBox 的，可以自己选跟不跟随房主的玩法。

<sub>隐藏的开发者模式：「关于」页的版本号连点 10 次。数据能按单只怪 / 单个出怪来源细改，左边多出「选图」「分屏」「潜兵」「日志」，风险自负。</sub>

希望大家玩得开心，也请不要影响别的玩家。

## 从源码构建

HellBox 是 Python 3.12+ / PySide6 程序，在 Windows 上开发。

```bat
pip install -r requirements.txt
python hellbox/app.py
```

安装核心时需要 LuaJIT 2.0 来编译 Lua 脚本。把 LuaJIT 放在 `tools/luajit-2.0/`，包含 `src/luajit.exe`、`src/lua51.dll`、`src/jit/` 和 `COPYRIGHT`（可从 [LuaJIT/LuaJIT](https://github.com/LuaJIT/LuaJIT) 的 `v2.0` 分支构建）。

**本地打包（普通构建）：**

```bat
python hellbox/make_exe.py
```

生成 `bin\HellBox\HellBox.exe`（PyInstaller 文件夹版）。同时会在仓库根目录生成指向它的快捷方式 `HellBox.lnk`。

**发行版打包：**

```bat
python hellbox/make_exe.py --public
```

结果在 `.work\hellbox-public\HellBox`：`HellBox.exe` + `_internal`，旁边还有以普通文件形式放着的 `mod`、`ai` 和 `tools`。`--public --portable` 是另一种打法：使用官方 Python 便携版，HellBox 编译成 `.pyc`（`hellbox/make_portable.py`），不用 PyInstaller。

### 存档 / 设置写不进去：`fix-save.bat`

Windows 有时会把复制、解压或刚构建出来的程序目录标成 **低完整性（Low）**。这时 HellBox 能启动，但保存设置可能报：

```
Permission denied: ...\play.txt.tmp
```

`fix-save.bat` 会把构建目录改回 **Medium** 完整性，然后启动 HellBox。用法：

- **右键 → 以管理员身份运行**。
- 默认找它旁边的 `bin\HellBox`（仓库根目录下的构建）。如果你的构建在别处，先改文件顶部的 `set "B=..."`。
- 它只改文件夹的完整性标签，不改文件内容；运行前先关掉 HellBox。
- 一般只在构建 / 复制后保存失败时用，不需要每次都跑。

### 可选组件

- 分屏：`mod/camera/runtime.luac` 是 HalfSugar 的 CameraCTRL 模块，从 `camera-src/` 构建（CameraCTRL 加 HellBox 的镜头改动和 `BridgeCore`）。重新编译：`python camera-src/CameraCTRL/bridge/compile.py <LuaJIT 的路径>`。安装核心时，`mod/camera_stack.py` 把它加进游戏的启动脚本。
- `mod/src/hellbox_hop.lua` 由 `python tools/make_hop.py` 从 `mod/hop/` 生成。

仓库里没有游戏原文件。安装核心时，HellBox 会从你自己的游戏文件里读取它扩展的两个原脚本（`character_state_machine`、`character_state_carry`），原样运行，再在它们后面加上 HellBox 的代码。

## 目录

- `hellbox/`：PySide6 界面。
- `mod/`：核心安装和游戏内 Lua 脚本（`mod/src`、`mod/hop`）；`mod/camera/` 是分屏。
- `ai/`：数据表。
- `camera-src/`：分屏 CameraCTRL 源码。
- `tools/`：构建工具（包括 LuaJIT）。

## 鸣谢与授权

HellBox 由 **07** 制作；自己的代码按 [MIT](LICENSE) 授权。收录的第三方部分保留各自的授权或条款，列在 [LICENSE](LICENSE) 末尾。

- **分屏：** CameraCTRL，**HalfSugar**。
- **输入法防闪退：** **HalfSugar**。
- **HelldiversOptimization 修复**（`mod/hop/`）：**HalfSugar**，经作者同意收录并发布。
- **Dive Harder：** 队友 HUD 标记、隐藏目标、好友列表刷新和两个 QoL Mod 修复，**Oct0pu5**（MIT，经同意收录；`mod/src/hellbox_dh.lua`）。
- **QoL Mod：** **SomeDoggo**。
- 自己补给、隐藏样本轮廓：**Lhgrzr**。
- 界面设计：**91** · 高难度数据指导：**吃大份** · 测试：**91、HalfSugar、吃大份、K-ON!、Kent、QiQi** · 总体规划与代码：**Claude**。
- **文本：** **Oct0pu5**。
- 从别的 MOD 借来的功能，会在 HellBox 对应功能下面写明来源。

字体：Silkscreen（SIL Open Font License，`hellbox/fonts/OFL.txt`）。LuaJIT © Mike Pall（MIT）。发行版还包含 Python（PSF 授权）、PySide6 / Qt（LGPL-3.0）和 pymem（MIT）。

非官方粉丝 MOD，与 Arrowhead Game Studios 或 Sony Interactive Entertainment 无关。HELLDIVERS 是 Sony Interactive Entertainment 的商标。
