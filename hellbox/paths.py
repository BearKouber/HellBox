"""路径：HellBox 和 mod 功能代码放在哪。

开发时：  <工具目录>\\hellbox\\app.py              → ROOT = <工具目录>
发行版：  <解压目录>\\app\\hellbox\\app.pyc        → ROOT = <解压目录>\\app（官方 Python + 编译好的代码，见 make_portable.py）
打包后：  <工具目录>\\bin\\HellBox\\HellBox.exe    → 往上找到带 mod 文件夹的那一层
mod 的功能代码（build.py、cursor_mod.py 等）不打进 exe，运行时从 ROOT\\mod 读，改 mod 不用重新打包。
字体、图标打进 exe（RES）。
"""
import os
import sys

FROZEN = getattr(sys, "frozen", False)


def _has_build(d):
    """mod 里有 build.py（开发 / 源码）或 build.pyc（发行版编译过）。"""
    return any(os.path.isfile(os.path.join(d, "mod", n)) for n in ("build.py", "build.pyc"))


def _find_root(start):
    """从 exe 所在目录往上找带 mod\\build.py 的那一层。"""
    d = start
    for _ in range(4):
        if _has_build(d):
            return d
        d = os.path.dirname(d)
    return start


if FROZEN:
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
    ROOT = _find_root(EXE_DIR)
    RES = getattr(sys, "_MEIPASS", EXE_DIR)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
    ROOT = os.path.dirname(HERE)
    RES = HERE

MOD = os.path.join(ROOT, "mod")
FONTS = os.path.join(RES, "fonts")
ICON_PNG = os.path.join(RES, "icon.png")


def setup():
    """把 mod 目录加进 import 路径。找不到就返回错误说明（界面上显示）。"""
    if not _has_build(ROOT):
        return (f"没找到 mod 文件夹：{MOD}\n"
                "HellBox 要放在 Helldivers 工具目录里（<工具目录>\\bin\\HellBox\\，上两层有 mod 文件夹）。")
    if MOD not in sys.path:
        sys.path.insert(0, MOD)
    return None
