from .komi import KomiScraper
from .linktree import LinktreeScraper


SCRAPERS = {
    "komi": KomiScraper,
    "linktree": LinktreeScraper,
}