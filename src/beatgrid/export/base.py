from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from beatgrid.project.models import Project


class GridExporter(ABC):
    format_name: ClassVar[str]
    file_extension: ClassVar[str]

    @abstractmethod
    def export(self, project: Project, path: Path) -> None: ...
