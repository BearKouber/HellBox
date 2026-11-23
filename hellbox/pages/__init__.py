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
DEV_ONLY = {"logs", "character"}
DEV_ONLY.add("quick")
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
