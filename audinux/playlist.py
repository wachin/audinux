# -*- coding: utf-8 -*-
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class PlaylistItem:
    path: str

class Playlist:
    def __init__(self):
        self.items: List[PlaylistItem] = []
        self.index: int = -1

    def add(self, path: str):
        self.items.append(PlaylistItem(path))
        if self.index < 0:
            self.index = 0

    def current(self) -> Optional[PlaylistItem]:
        if 0 <= self.index < len(self.items):
            return self.items[self.index]
        return None

    def next(self) -> Optional[PlaylistItem]:
        if self.index + 1 < len(self.items):
            self.index += 1
            return self.current()
        return None

    def prev(self) -> Optional[PlaylistItem]:
        if self.index - 1 >= 0:
            self.index -= 1
            return self.current()
        return None
