from __future__ import annotations

import json
import re
import tomllib

from ..models import SourceFile


class ResolvedPackage:
    def __init__(self, ecosystem: str, name: str, version: str, path: str) -> None:
        self.ecosystem = ecosystem
        self.name = name
        self.version = version
        self.path = path

    def key(self) -> tuple[str, str, str]:
        return (self.ecosystem, self.name, self.version)


def _norm_pypi(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _requirements(file: SourceFile) -> list[ResolvedPackage]:
    out: list[ResolvedPackage] = []
    for raw in file.text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = re.match(r"^([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-+!]+)", line)
        if match:
            out.append(ResolvedPackage("PyPI", _norm_pypi(match.group(1)), match.group(2), file.path))
    return out


def _toml_packages(file: SourceFile, ecosystem: str, normalize: bool) -> list[ResolvedPackage]:
    try:
        data = tomllib.loads(file.text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []
    out: list[ResolvedPackage] = []
    for pkg in data.get("package", []):
        name, version = pkg.get("name"), pkg.get("version")
        if isinstance(name, str) and isinstance(version, str):
            out.append(ResolvedPackage(ecosystem, _norm_pypi(name) if normalize else name, version, file.path))
    return out


def _pipfile_lock(file: SourceFile) -> list[ResolvedPackage]:
    try:
        data = json.loads(file.text)
    except (json.JSONDecodeError, ValueError):
        return []
    out: list[ResolvedPackage] = []
    for section in ("default", "develop"):
        for name, meta in (data.get(section) or {}).items():
            version = (meta or {}).get("version", "")
            if isinstance(version, str) and version.startswith("=="):
                out.append(ResolvedPackage("PyPI", _norm_pypi(name), version[2:], file.path))
    return out


def _package_lock(file: SourceFile) -> list[ResolvedPackage]:
    try:
        data = json.loads(file.text)
    except (json.JSONDecodeError, ValueError):
        return []
    out: list[ResolvedPackage] = []
    packages = data.get("packages")
    if isinstance(packages, dict):
        for path, meta in packages.items():
            if not path or not isinstance(meta, dict):
                continue
            name = path.split("node_modules/")[-1]
            version = meta.get("version")
            if isinstance(version, str):
                out.append(ResolvedPackage("npm", name, version, file.path))
        return out
    deps = data.get("dependencies")
    if isinstance(deps, dict):
        for name, meta in deps.items():
            version = (meta or {}).get("version")
            if isinstance(version, str):
                out.append(ResolvedPackage("npm", name, version, file.path))
    return out


def _go_sum(file: SourceFile) -> list[ResolvedPackage]:
    seen: set[tuple[str, str]] = set()
    out: list[ResolvedPackage] = []
    for line in file.text.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            module = parts[0]
            version = parts[1].removesuffix("/go.mod")
            if (module, version) not in seen:
                seen.add((module, version))
                out.append(ResolvedPackage("Go", module, version.lstrip("v"), file.path))
    return out


def _gemfile_lock(file: SourceFile) -> list[ResolvedPackage]:
    out: list[ResolvedPackage] = []
    in_specs = False
    for raw in file.text.splitlines():
        if raw.strip() == "specs:":
            in_specs = True
            continue
        if in_specs:
            match = re.match(r"^\s{4}([A-Za-z0-9_.\-]+) \(([^)]+)\)\s*$", raw)
            if match:
                out.append(ResolvedPackage("RubyGems", match.group(1), match.group(2), file.path))
            elif raw and not raw.startswith(" "):
                break
    return out


def _composer_lock(file: SourceFile) -> list[ResolvedPackage]:
    try:
        data = json.loads(file.text)
    except (json.JSONDecodeError, ValueError):
        return []
    out: list[ResolvedPackage] = []
    for section in ("packages", "packages-dev"):
        for pkg in data.get(section) or []:
            name, version = pkg.get("name"), pkg.get("version")
            if isinstance(name, str) and isinstance(version, str):
                out.append(ResolvedPackage("Packagist", name, version.lstrip("v"), file.path))
    return out


def parse_lockfiles(files: list[SourceFile]) -> list[ResolvedPackage]:
    out: list[ResolvedPackage] = []
    for file in files:
        base = file.path.rsplit("/", 1)[-1].lower()
        if base == "requirements.txt":
            out.extend(_requirements(file))
        elif base in ("poetry.lock", "pdm.lock") or base == "uv.lock":
            out.extend(_toml_packages(file, "PyPI", True))
        elif base == "cargo.lock":
            out.extend(_toml_packages(file, "crates.io", False))
        elif base == "pipfile.lock":
            out.extend(_pipfile_lock(file))
        elif base == "package-lock.json":
            out.extend(_package_lock(file))
        elif base == "go.sum":
            out.extend(_go_sum(file))
        elif base == "gemfile.lock":
            out.extend(_gemfile_lock(file))
        elif base == "composer.lock":
            out.extend(_composer_lock(file))
    deduped: dict[tuple[str, str, str], ResolvedPackage] = {}
    for pkg in out:
        deduped.setdefault(pkg.key(), pkg)
    return list(deduped.values())
