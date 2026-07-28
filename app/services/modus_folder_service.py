from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List, Optional

from app.providers.adapters.modus_official.parser import ModusSavedPageParser
from app.providers.adapters.modus_official.real_match_parser import ModusRealMatchPageParser


MATCH_FILE = re.compile(r"^match_(\d+)\.html$", re.IGNORECASE)


@dataclass(frozen=True)
class ModusFolderIssue:
    severity: str
    code: str
    message: str
    filename: Optional[str] = None
    match_id: Optional[int] = None


@dataclass(frozen=True)
class ModusFolderManifest:
    folder: Path
    results_file: Optional[Path]
    series_id: Optional[int]
    series_label: Optional[str]
    week_id: Optional[int]
    week_label: Optional[str]
    group: Optional[str]
    expected_match_ids: List[int] = field(default_factory=list)
    found_match_ids: List[int] = field(default_factory=list)
    validated_match_ids: List[int] = field(default_factory=list)
    missing_match_ids: List[int] = field(default_factory=list)
    unexpected_match_ids: List[int] = field(default_factory=list)
    invalid_files: List[str] = field(default_factory=list)
    ignored_files: List[str] = field(default_factory=list)
    issues: List[ModusFolderIssue] = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return (
            self.results_file is not None
            and self.expected_match_ids == self.validated_match_ids
            and not self.missing_match_ids
            and not self.unexpected_match_ids
            and not self.invalid_files
            and not any(i.severity == "error" for i in self.issues)
        )

    def to_dict(self) -> dict:
        return {
            "folder": str(self.folder),
            "results_file": self.results_file.name if self.results_file else None,
            "series_id": self.series_id,
            "series_label": self.series_label,
            "week_id": self.week_id,
            "week_label": self.week_label,
            "group": self.group,
            "expected_count": len(self.expected_match_ids),
            "found_count": len(self.found_match_ids),
            "validated_count": len(self.validated_match_ids),
            "missing_match_ids": self.missing_match_ids,
            "unexpected_match_ids": self.unexpected_match_ids,
            "invalid_files": self.invalid_files,
            "ignored_files": self.ignored_files,
            "ready": self.ready,
            "issues": [i.__dict__ for i in self.issues],
        }


class ModusFolderImportService:
    """Inspect and cross-validate saved MODUS pages without database writes."""

    def __init__(self):
        self.results_parser = ModusSavedPageParser()
        self.match_parser = ModusRealMatchPageParser()

    def inspect(self, folder: str | Path) -> ModusFolderManifest:
        folder = Path(folder).expanduser().resolve()
        if not folder.exists():
            raise ValueError(f"MODUS import folder does not exist: {folder}")
        if not folder.is_dir():
            raise ValueError(f"MODUS import path is not a folder: {folder}")

        files = sorted(p for p in folder.iterdir() if p.is_file())
        results_files = self._find_results_files(files)
        issues: List[ModusFolderIssue] = []

        if not results_files:
            return ModusFolderManifest(
                folder=folder,
                results_file=None,
                series_id=None,
                series_label=None,
                week_id=None,
                week_label=None,
                group=None,
                ignored_files=sorted(
                    p.name for p in files if p.suffix.lower() != ".html"
                ),
                issues=[ModusFolderIssue(
                    "error", "missing_results_file",
                    "No saved MODUS results page was found."
                )],
            )

        if len(results_files) > 1:
            issues.append(ModusFolderIssue(
                "error", "multiple_results_files",
                "More than one saved MODUS results page was found."
            ))

        results_file = results_files[0]
        page = self.results_parser.parse_results_document(
            results_file.read_text(encoding="utf-8")
        )
        expected = {m.match_id: m for m in page.matches}

        found = {}
        invalid_files = []
        ignored_files = []
        for path in files:
            if path in results_files:
                continue
            match = MATCH_FILE.fullmatch(path.name)
            if match:
                found[int(match.group(1))] = path
            elif path.suffix.lower() == ".html":
                invalid_files.append(path.name)
                issues.append(ModusFolderIssue(
                    "error", "invalid_html_filename",
                    "HTML match pages must use match_<id>.html.",
                    filename=path.name,
                ))
            else:
                ignored_files.append(path.name)

        expected_ids = sorted(expected)
        found_ids = sorted(found)
        missing_ids = sorted(set(expected_ids) - set(found_ids))
        unexpected_ids = sorted(set(found_ids) - set(expected_ids))

        for match_id in missing_ids:
            issues.append(ModusFolderIssue(
                "error", "missing_match_page",
                f"Missing match_{match_id}.html.", match_id=match_id
            ))
        for match_id in unexpected_ids:
            issues.append(ModusFolderIssue(
                "error", "unexpected_match_page",
                f"match_{match_id}.html is not listed on the results page.",
                match_id=match_id,
            ))

        validated = []
        for match_id in expected_ids:
            path = found.get(match_id)
            if path is None:
                continue
            try:
                detail = self.match_parser.parse(
                    path.read_text(encoding="utf-8"),
                    match_id=match_id,
                )
                listed = expected[match_id]
                self._validate_match(path.name, listed, detail)
                validated.append(match_id)
            except Exception as exc:
                issues.append(ModusFolderIssue(
                    "error", "match_validation_failed", str(exc),
                    filename=path.name, match_id=match_id
                ))

        return ModusFolderManifest(
            folder=folder,
            results_file=results_file,
            series_id=page.series_id,
            series_label=page.series_label,
            week_id=page.week_id,
            week_label=page.week_label,
            group=page.group,
            expected_match_ids=expected_ids,
            found_match_ids=found_ids,
            validated_match_ids=validated,
            missing_match_ids=missing_ids,
            unexpected_match_ids=unexpected_ids,
            invalid_files=sorted(invalid_files),
            ignored_files=sorted(ignored_files),
            issues=issues,
        )

    @staticmethod
    def _find_results_files(files: List[Path]) -> List[Path]:
        named = [p for p in files if p.name.lower() == "results.html"]
        if named:
            return named
        found = []
        for path in files:
            if path.suffix.lower() != ".html":
                continue
            text = path.read_text(encoding="utf-8")
            if 'id="seriesSelect"' in text and "fixture-card" in text:
                found.append(path)
        return found

    @staticmethod
    def _validate_match(filename, listed, detail):
        if detail.player_a_name.casefold() != listed.player_a_name.casefold():
            raise ValueError(f"{filename}: Player A does not match results page.")
        if detail.player_b_name.casefold() != listed.player_b_name.casefold():
            raise ValueError(f"{filename}: Player B does not match results page.")
        if listed.player_a_legs is not None and detail.player_a_legs != listed.player_a_legs:
            raise ValueError(f"{filename}: Player A score does not match results page.")
        if listed.player_b_legs is not None and detail.player_b_legs != listed.player_b_legs:
            raise ValueError(f"{filename}: Player B score does not match results page.")
