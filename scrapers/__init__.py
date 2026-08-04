from .komi import KomiScraper
from .linktree import LinktreeScraper
from .punchup import PunchupScraper


SCRAPERS = {
    "komi": KomiScraper,
    "linktree": LinktreeScraper,
    "punchup": PunchupScraper,
}