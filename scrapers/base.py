from __future__ import annotations

from abc import ABC, abstractmethod

from models import Event


class BaseScraper(ABC):
    def __init__(
        self,
        url: str,
        performer: str | None = None,
    ) -> None:
        self.url = url
        self.performer = performer

    @abstractmethod
    def scrape(self) -> list[Event]:
        """Return standardized Event objects."""
        raise NotImplementedError