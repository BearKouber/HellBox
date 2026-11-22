"""MOD 开关页、快捷语音页共用：改 hellbox_options.json 里的设置。

2026-11-14 V0.91（用户要求所有开关热生效）：存完马上写 options.txt，游戏开着的话下一秒就按新开关走，不用关游戏重装。
"""
import build
import hellbox_options


def apply(app, changes):
    def action():
        hellbox_options.save(changes)
        build.write_live_options()
        if build.game_running():
            return "已生效（游戏里下一秒就按新设置）。"
        if build.status() in ("on", "old"):
            return "已保存，下次进游戏生效。"
        return "已保存，打开「核心」开关时一起装。"

    app.run(action)
