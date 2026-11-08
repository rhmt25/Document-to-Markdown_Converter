"""Background queue worker and conflict request models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from .engine import ConversionOptions, convert_document


class ConflictChoice(str, Enum):
    OVERWRITE = "overwrite"
    NUMBERED_COPY = "numbered_copy"
    SKIP = "skip"
    CANCEL = "cancel"


@dataclass
class ConflictRequest:
    source: Path
    destination: Path
    allow_apply_to_all: bool
    response_ready: Event
    choice: ConflictChoice | None = None
    apply_to_all: bool = False


@dataclass
class FileOutcome:
    source: Path
    destination: Path | None
    status: str
    message: str


class ConversionWorker(QObject):
    """Sequentially convert a set of files without blocking the GUI thread."""

    progress = Signal(int, int, str)
    conflict_requested = Signal(object)
    file_finished = Signal(object)
    finished = Signal(object)

    def __init__(
        self,
        sources: list[Path],
        output_directory: Path,
        options: ConversionOptions,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self.sources = sources
        self.output_directory = output_directory
        self.options = options
        self.cancel_event = cancel_event
        self._apply_to_all_choice: ConflictChoice | None = None

    @Slot()
    def run(self) -> None:
        outcomes: list[FileOutcome] = []
        total = len(self.sources)
        for index, source in enumerate(self.sources, start=1):
            if self.cancel_event.is_set():
                break
            self.progress.emit(index, total, source.name)
            destination = self.output_directory / f"{source.stem}.md"
            if destination.exists():
                choice = self._get_conflict_choice(source, destination, total > 1)
                if choice == ConflictChoice.CANCEL:
                    break
                if choice == ConflictChoice.SKIP:
                    outcome = FileOutcome(source, None, "skipped", "Skipped due to a name conflict.")
                    outcomes.append(outcome)
                    self.file_finished.emit(outcome)
                    continue
                if choice == ConflictChoice.NUMBERED_COPY:
                    destination = self._numbered_destination(destination)

            try:
                convert_document(source, destination, self.options)
                outcome = FileOutcome(source, destination, "success", f"Saved {destination.name}")
            except Exception as error:
                outcome = FileOutcome(source, None, "failed", str(error))
            outcomes.append(outcome)
            self.file_finished.emit(outcome)

        self.finished.emit(outcomes)

    def _get_conflict_choice(
        self, source: Path, destination: Path, allow_apply_to_all: bool
    ) -> ConflictChoice:
        if self._apply_to_all_choice is not None:
            return self._apply_to_all_choice

        request = ConflictRequest(
            source=source,
            destination=destination,
            allow_apply_to_all=allow_apply_to_all,
            response_ready=Event(),
        )
        self.conflict_requested.emit(request)
        while not request.response_ready.wait(0.1):
            if self.cancel_event.is_set():
                return ConflictChoice.CANCEL

        choice = request.choice or ConflictChoice.CANCEL
        if request.apply_to_all:
            self._apply_to_all_choice = choice
        return choice

    @staticmethod
    def _numbered_destination(destination: Path) -> Path:
        sequence = 1
        while True:
            candidate = destination.with_name(f"{destination.stem} ({sequence}){destination.suffix}")
            if not candidate.exists():
                return candidate
            sequence += 1
