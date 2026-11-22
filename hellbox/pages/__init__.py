"""页面登记。2026-11-15 新界面：左侧导航分组（游戏里 / 改数据 / 我的），「关于」贴在最下面；
「日志」「潜兵」「分屏」「训练」只在开发者模式里出现（DEV_ONLY）；「K-ON!增强UI定制版」开着时只留 KON_PAGES 这几页（盖过开发者模式）。加新页面：pages/ 下新建一个继承 Page 的类，在下面 import、加进 PAGES 和 NAV。"""
import build
from pages.about import AboutPage
from pages.character import CharacterPage
from pages.cursor import CursorPage
from pages.data_page import DataPage
from pages.display import DisplayPage
from pages.logs import LogsPage
from pages.mod import ModPage
from pages.names import NamesPage
from pages.play import PlayPage
from pages.quick import QuickPage
from pages.results import ResultsPage
from pages.split import SplitPage
from pages.voice import VoicePage

PAGES = [ModPage, DisplayPage, VoicePage, QuickPage, PlayPage, DataPage, NamesPage, CharacterPage, CursorPage, ResultsPage, LogsPage]
NAV = [("游戏里", ["mod", "display", "voice", "quick", "play"]),
       ("改数据", ["data"]),
       ("我的", ["names", "character", "cursor", "results", "logs"])]
NAV_BOTTOM = ["about"]
DEV_ONLY = {"logs", "character"}  # 2026-11-19 用户定：「潜兵」页（等级、武器解锁、披风）只在开发者模式里出现
DEV_ONLY.add("quick")  # 2026-11-19 用户定：「训练」（同日改名「选图」）也挪进开发者模式
# 2026-11-19 用户定：「关于」里的「K-ON!增强UI定制版」开着时，左边只有这几页（不管开没开开发者模式）
KON_PAGES = {"mod", "play", "data", "cursor", "about"}

if build.camera_enabled():  # 分屏（HalfSugar 的 CameraCTRL）：发行版才有
    PAGES.insert(2, SplitPage)
    NAV[0][1].insert(2, "split")
    # 2026-11-19 用户定：分屏还要调整，先挪进开发者模式，普通模式看不到；游戏里普通模式也不开分屏（camera_link.lua 看 dev.txt）
    DEV_ONLY.add("split")

if not build.is_public():  # 自用版：AI 陪玩的两页
    from pages.arena import ArenaPage
    from pages.overlay import OverlayPage

    PAGES.extend([ArenaPage, OverlayPage])
    NAV.append(("陪玩", ["arena", "overlay"]))

PAGES.append(AboutPage)
