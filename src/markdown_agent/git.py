from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


# Files that almost never warrant documentation updates
_NOISE_PATTERNS = re.compile(
    r"(\.lock$|\.sum$|__pycache__|\.pyc$|\.DS_Store|\.git/|node_modules/)"
)

_NOISE_FILENAMES = frozenset([
    "package-lock.json", "package-sources.json", "yarn.lock", "poetry.lock",
    "Pipfile.lock", "requirements.txt.lock",
])

# Change-type classifiers: (regex on file path) -> section tag
_PATH_CLASSIFIERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(requirements.*\.txt|pyproject\.toml|package\.json|Pipfile|go\.mod|Cargo\.toml)"), "dependencies"),
    (re.compile(r"(Makefile|scripts/|bin/|\.github/workflows/)"), "commands"),
    (re.compile(r"(\.env|config\.(yml|yaml|toml|json)|settings\.(py|ts|js))"), "environment"),
    (re.compile(r"(Dockerfile|docker-compose|\.dockerignore)"), "environment"),
    (re.compile(r"(README|CONTRIBUTING|CHANGELOG|docs/)"), "skip"),
]


@dataclass
class FileDiff:
    path: str
    insertions: int
    deletions: int
    is_new: bool = False
    is_deleted: bool = False
    is_renamed: bool = False


@dataclass
class DiffSummary:
    file_diffs: list[FileDiff] = field(default_factory=list)
    raw_diff: str = ""
    total_insertions: int = 0
    total_deletions: int = 0
    change_types: set[str] = field(default_factory=set)
    is_comment_only: bool = False
    is_whitespace_only: bool = False

    @property
    def significant_files(self) -> list[FileDiff]:
        return [
            f for f in self.file_diffs
            if not _NOISE_PATTERNS.search(f.path)
            and Path(f.path).name not in _NOISE_FILENAMES
        ]

    @property
    def total_meaningful_lines(self) -> int:
        return sum(f.insertions + f.deletions for f in self.significant_files)


def _run(cmd: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return ""


def _classify_path(path: str) -> str | None:
    for pattern, tag in _PATH_CLASSIFIERS:
        if pattern.search(path):
            return tag
    return "structure"


def _is_comment_or_whitespace_only(diff_text: str) -> tuple[bool, bool]:
    added = [l[1:] for l in diff_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in diff_text.splitlines() if l.startswith("-") and not l.startswith("---")]
    changed = added + removed
    if not changed:
        return False, False

    whitespace_only = all(not l.strip() for l in changed)
    comment_only = all(
        l.strip().startswith(("#", "//", "*", "/*", "*/", '"""', "'''", "--"))
        for l in changed if l.strip()
    )
    return comment_only, whitespace_only


def get_diff(repo_root: Path, staged_only: bool = False) -> DiffSummary:
    """Return a DiffSummary for the most recent change (staged or HEAD~1)."""
    if staged_only:
        raw = _run(["git", "diff", "--cached"], repo_root)
        stat = _run(["git", "diff", "--cached", "--numstat"], repo_root)
        name_status = _run(["git", "diff", "--cached", "--name-status"], repo_root)
    else:
        raw = _run(["git", "diff", "HEAD~1", "HEAD"], repo_root)
        stat = _run(["git", "diff", "HEAD~1", "HEAD", "--numstat"], repo_root)
        name_status = _run(["git", "diff", "HEAD~1", "HEAD", "--name-status"], repo_root)

    file_diffs: list[FileDiff] = []
    change_types: set[str] = set()
    total_ins = total_del = 0

    status_map: dict[str, str] = {}
    for line in name_status.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            status_map[parts[-1]] = parts[0]

    for line in stat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        ins_str, del_str, path = parts
        try:
            ins = int(ins_str) if ins_str != "-" else 0
            dels = int(del_str) if del_str != "-" else 0
        except ValueError:
            continue

        status = status_map.get(path, "M")
        fd = FileDiff(
            path=path,
            insertions=ins,
            deletions=dels,
            is_new=status.startswith("A"),
            is_deleted=status.startswith("D"),
            is_renamed=status.startswith("R"),
        )
        file_diffs.append(fd)
        total_ins += ins
        total_del += dels

        if not _NOISE_PATTERNS.search(path):
            ct = _classify_path(path)
            if ct and ct != "skip":
                change_types.add(ct)

    comment_only, whitespace_only = _is_comment_or_whitespace_only(raw)

    # Truncate raw diff to 300 lines to avoid blowing token budgets
    raw_lines = raw.splitlines()
    truncated = "\n".join(raw_lines[:300])
    if len(raw_lines) > 300:
        truncated += f"\n... (truncated {len(raw_lines) - 300} more lines)"

    return DiffSummary(
        file_diffs=file_diffs,
        raw_diff=truncated,
        total_insertions=total_ins,
        total_deletions=total_del,
        change_types=change_types,
        is_comment_only=comment_only,
        is_whitespace_only=whitespace_only,
    )
