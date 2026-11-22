"""把 mod/hop/ 里半糖 HelldiversOptimization 的模块拼成一个游戏脚本 mod/src/hellbox_hop.lua。
（2026-11-20 用户删了增强 HUD；2026-11-22 状态提示也删了，betterhud 整个不要了。）

2026-11-20 HD1-035。用法：.venv\\Scripts\\python tools\\make_hop.py
改了 mod/hop/ 下任何文件都要重跑一次（生成的文件也提交）。
装 MOD 时 build.py 把 "@HELLBOX_HOP@" 换成 hellbox_hop.py 里的初始设置（Lua 表）。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOP = ROOT / "mod" / "hop"
OUT = ROOT / "mod" / "src" / "hellbox_hop.lua"

# 2026-11-21 HD1-038（用户定）：来自 QoL Mod 的模块全部删掉，只留半糖自己的功能用到的
# 2026-11-22 用户：「资料和状态」两项（军械库显示真实数值、显示身上的状态）也是 QoL 的，删掉 reference_display、indicators
#   （画字用的 betterhud/canvas.lua 跟着不要了）
MODULES = ["context", "constitution", "readability"]


def read(path):
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")


def main():
    out = [
        "-- [hellbox hop] 自动生成，不要手改：改 mod/hop/ 下的文件后跑 tools/make_hop.py。",
        "-- 来源：HalfSugar（半糖）的 HelldiversOptimization（作者同意收进 HellBox，2026-11-19）；",
        "do",
        'local hop_defaults = "@HELLBOX_HOP@"',
    ]
    for name in MODULES:
        out.append(f"local {name}_factory = (function()\n{read(HOP / (name + '.lua'))}\nend)()")
    out.append(read(HOP / "hellbox_bootstrap.lua"))
    out.append("end\n")
    OUT.write_text("\n".join(out), encoding="utf-8", newline="\n")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
