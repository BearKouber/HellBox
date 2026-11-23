"""
功能页和快捷语音页共用：修改 hellbox_options.json 里的设置，存完马上写 options.txt，热生效。
"""
import build
import hellbox_options


def apply(app, changes):
    def action():
        hellbox_options.save(changes)
        build.write_live_options()
        if build.game_running():
            return "已生效（游戏内立即按新设置运行）。"
        if build.status() in ("on", "old"):
            return "已保存，下次进游戏生效。"
        return "已保存，打开「核心」开关时一起装。"

    app.run(action)
