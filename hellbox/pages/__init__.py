import build
from pages.about import AboutPage
from pages.character import CharacterPage
from pages.cursor import CursorPage
from pages.data_page import DataPage
from pages.display import DisplayPage
from pages.logs import LogsPage
from pages.mod import ModPage
from pages.multi import MultiPage
from pages.names import NamesPage
from pages.play import PlayPage
from pages.quick import QuickPage
from pages.record import RecordPage
from pages.results import ResultsPage
from pages.split import SplitPage
from pages.voice import VoicePage

PAGES = [ModPage, DisplayPage, VoicePage, QuickPage, PlayPage, MultiPage, DataPage, NamesPage, CharacterPage, CursorPage, ResultsPage, RecordPage, LogsPage]
NAV = [("游戏里", ["mod", "display", "voice", "quick", "play", "multi"]),
       ("改数据", ["data"]),
       ("我的", ["names", "character", "cursor", "results", "record", "logs"])]
NAV_BOTTOM = ["about"]
DEV_ONLY = {"logs", "character"}
DEV_ONLY.add("quick")
DEV_ONLY.add("multi")  # 2026-11-26 HD1-039 用户定：8 人房间先只在开发者模式显示
DEV_ONLY.add("record")  # 2026-11-26 用户定：帮作者录对局（训练潜兵 AI）只在开发者模式显示
KON_PAGES = {"mod", "play", "data", "cursor", "about"}

if build.camera_enabled():
    PAGES.insert(2, SplitPage)
    NAV[0][1].insert(2, "split")
    DEV_ONLY.add("split")

if not build.is_public():
    from pages.arena import ArenaPage
    from pages.overlay import OverlayPage

    PAGES.extend([ArenaPage, OverlayPage])
    NAV.append(("陪玩", ["arena", "overlay"]))

PAGES.append(AboutPage)
