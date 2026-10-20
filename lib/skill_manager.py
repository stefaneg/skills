"""Resolve scopes into a complete plan before changing installed skills."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

RECEIPT = ".skills-receipt.json"
BASELINES = ".skills-baselines"
TIERS = {"auto", "on-demand", "off"}


class SkillError(Exception):
    pass


def read_json(path, default=None):
    if not path.exists() and default is not None:
        return default
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SkillError(f"cannot read {path}: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        json.dump(value, f, indent=2)
        f.write("\n")
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def valid_name(name):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
        raise SkillError(f"invalid name: {name!r}")


def baseline_dir(target):
    # Keep snapshots outside the discovery root: a baseline contains SKILL.md
    # too, and must not become another discoverable copy of the skill.
    return target.parent / f".{target.name}-baselines"


def resolve_path(path):
    try:
        result = path.resolve()
        for part in (path, *path.parents):
            if part.is_symlink() and not part.exists():
                raise SkillError(f"broken symlink: {part}")
        return result
    except (OSError, RuntimeError) as exc:
        raise SkillError(f"cannot resolve target {path}: {exc}") from exc


def tree_files(root):
    files = {}
    if not root.is_dir() or root.is_symlink():
        raise SkillError(f"not a physical skill directory: {root}")
    for parent, dirs, names in os.walk(root, followlinks=False):
        for name in dirs + names:
            path = Path(parent) / name
            if path.is_symlink():
                raise SkillError(f"symlinks inside skills are unsupported: {path}")
        for name in names:
            if name == ".DS_Store":
                continue
            path = Path(parent) / name
            if not path.is_file():
                raise SkillError(f"unsupported file in skill: {path}")
            files[path.relative_to(root).as_posix()] = path
    return files


def skill_hash(root):
    # Keep compatibility with the original find/sort/shasum listing. Baseline
    # hashes cover relative filenames and every regular file's content.
    listing = bytearray()
    for name, path in sorted(tree_files(root).items(), key=lambda item: os.fsencode(item[0])):
        label = "./" + name
        escaped = "\\" in label or "\n" in label
        if escaped:
            label = label.replace("\\", "\\\\").replace("\n", "\\n")
        line = ("\\" if escaped else "") + hashlib.sha256(path.read_bytes()).hexdigest()
        listing.extend(os.fsencode(line + "  " + label + "\n"))
    return hashlib.sha256(listing).hexdigest()


def copy_tree(source, dest):
    tree_files(source)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(".DS_Store"))


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if result.returncode:
        raise SkillError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def find_skill(root, name):
    hits = []
    for parent, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", BASELINES}]
        if Path(parent).name == name and "SKILL.md" in files:
            hits.append(Path(parent))
    if len(hits) != 1:
        reason = "not found" if not hits else "ambiguous: " + ", ".join(map(str, hits))
        raise SkillError(f"skill {name!r} {reason} in {root}")
    return hits[0]


@dataclass
class Scope:
    name: str
    project: bool
    targets: list[Path]
    install: list[dict]
    settings: Path


@dataclass
class Operation:
    scope: Scope
    target: Path
    skill: str
    action: str
    local_hash: str | None
    entry: dict | None
    incoming: Path | None = None
    staged: Path | None = None


class Manager:
    def __init__(self, repo, args):
        self.repo, self.args = repo, args
        self.manifest = read_json(repo / "skills.json")
        self.lock = read_json(repo / "skills.lock.json", {"sources": {}})
        self.original_lock = json.loads(json.dumps(self.lock))
        self.scratch = tempfile.TemporaryDirectory(prefix="skills-")
        self.temp = Path(self.scratch.name)
        self.roots = {}
        self.scopes = self.load_scopes()
        self.decisions = {}
        for choice in ("keep", "merge", "replace", "resolved"):
            for raw in getattr(args, choice, []) or []:
                name, sep, path = raw.partition("=") if choice == "resolved" else (raw, "", "")
                valid_name(name)
                if name in self.decisions:
                    raise SkillError(f"multiple customisation choices for {name}")
                if choice == "resolved" and not sep:
                    raise SkillError("--resolved expects SKILL=DIR")
                self.decisions[name] = (choice, Path(path).absolute() if sep else None)

    def close(self):
        self.scratch.cleanup()

    def path(self, value):
        expanded = Path(value).expanduser()
        return expanded if expanded.is_absolute() else self.repo / expanded

    def load_scopes(self):
        sources = self.manifest.get("sources", {})
        for name, source in sources.items():
            valid_name(name)
            if source.get("type") not in {"local", "github"}:
                raise SkillError(f"unknown source type for {name}")
            if source["type"] == "local" and not isinstance(source.get("path"), str):
                raise SkillError(f"local source {name} needs a path")
            if source["type"] == "github" and not re.fullmatch(r"[\w.-]+/[\w.-]+", source.get("repo", "")):
                raise SkillError(f"invalid GitHub repo for {name}")
        scopes = [Scope("user", False, [self.path(t) for t in self.manifest["targets"]],
                        self.manifest["install"], Path.home() / ".claude/settings.json")]
        for name, project in self.manifest.get("projects", {}).items():
            valid_name(name)
            if name == "user":
                raise SkillError("project name 'user' is reserved")
            root = self.path(project["root"])
            scopes.append(Scope(name, True, [root / ".claude/skills", root / ".agents/skills"],
                                project["install"], root / ".claude/settings.local.json"))
        for scope in scopes:
            seen = set()
            for entry in scope.install:
                valid_name(entry.get("skill"))
                if entry["skill"] in seen:
                    raise SkillError(f"duplicate {entry['skill']} in {scope.name}")
                seen.add(entry["skill"])
                if entry.get("source") not in sources or entry.get("tier") not in TIERS:
                    raise SkillError(f"invalid install entry in {scope.name}: {entry}")
            if not scope.targets:
                raise SkillError(f"scope {scope.name} needs at least one target")
        return scopes

    def selected(self):
        if self.args.all:
            return self.scopes
        name = self.args.project or "user"
        matches = [s for s in self.scopes if s.name == name]
        if not matches:
            raise SkillError(f"unknown project: {name}")
        return matches

    def targets(self, scope, display=False):
        result = []
        for alias in scope.targets:
            physical = resolve_path(alias)
            if display and alias.absolute() != physical:
                print(f"  target {alias} -> {physical}")
            if physical not in result:
                result.append(physical)
        return result

    def validate_targets(self):
        owners = {}
        for scope in self.scopes:
            for target in self.targets(scope):
                for previous, owner in owners.items():
                    if owner != scope.name and (target == previous or target in previous.parents or previous in target.parents):
                        raise SkillError(f"target overlap between {owner} and {scope.name}: {previous}, {target}")
                owners[target] = scope.name
                if target.exists() and not target.is_dir():
                    raise SkillError(f"target is not a directory: {target}")
                for metadata in (target / RECEIPT, baseline_dir(target)):
                    if metadata.is_symlink():
                        raise SkillError(f"metadata must not be a symlink: {metadata}")
                if baseline_dir(target).exists() and not baseline_dir(target).is_dir():
                    raise SkillError(f"baseline store is not a directory: {baseline_dir(target)}")

    def receipt(self, target):
        receipt = read_json(target / RECEIPT, {})
        if not isinstance(receipt, dict):
            raise SkillError(f"invalid receipt: {target / RECEIPT}")
        for name, entry in receipt.items():
            valid_name(name)
            if not isinstance(entry, dict) or not re.fullmatch(r"[0-9a-f]{64}", entry.get("hash", "")):
                raise SkillError(f"invalid receipt entry for {name} in {target}")
        return receipt

    def ensure_repo(self, name, update=False):
        source = self.manifest["sources"][name]
        directory = self.repo / "vendor" / name
        pin = self.lock.get("sources", {}).get(name, {}).get("sha")
        if not (directory / ".git").exists():
            directory.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(["git", "clone", "--quiet", "--filter=blob:none",
                                     f"https://github.com/{source['repo']}.git", str(directory)],
                                    capture_output=True, text=True)
            if result.returncode:
                raise SkillError(f"cannot clone {name}: {result.stderr.strip()}")
        exists = bool(pin) and subprocess.run(
            ["git", "-C", str(directory), "cat-file", "-e", f"{pin}^{{commit}}"],
            capture_output=True).returncode == 0
        if update or not exists:
            git(directory, "fetch", "--quiet", "origin", source.get("ref", "main"))
        sha = git(directory, "rev-parse", "FETCH_HEAD") if update or not pin else pin
        git(directory, "cat-file", "-e", f"{sha}^{{commit}}")
        return sha

    def root(self, name):
        source = self.manifest["sources"][name]
        if source["type"] == "local":
            return resolve_path(self.path(source["path"]))
        sha = self.lock.get("sources", {}).get(name, {}).get("sha")
        directory = self.repo / "vendor" / name
        if not sha:
            sha = git(directory, "rev-parse", "HEAD")
        key = (name, sha)
        if key not in self.roots:
            dest = self.temp / f"source-{len(self.roots)}"
            dest.mkdir()
            archive = self.temp / f"source-{len(self.roots)}.tar"
            git(directory, "archive", "--format=tar", f"--output={archive}", sha)
            with tarfile.open(archive) as tar:
                tar.extractall(dest, filter="data")
            self.roots[key] = dest
        return self.roots[key]

    def prepare_sources(self, scopes):
        names = {e["source"] for s in scopes for e in s.install if e["tier"] != "off"}
        for name in sorted(names):
            if self.manifest["sources"][name]["type"] == "github":
                if self.args.dry_run:
                    if not self.lock.get("sources", {}).get(name, {}).get("sha"):
                        raise SkillError(f"no cached pin for {name}; run sync before a dry-run")
                else:
                    sha = self.ensure_repo(name)
                    self.lock.setdefault("sources", {})[name] = {"sha": sha}

    def duplicates(self, scope):
        if not scope.project:
            return []
        user = {e["skill"] for e in self.scopes[0].install if e["tier"] != "off"}
        for target in self.targets(self.scopes[0]):
            if target.is_dir():
                user.update(p.name for p in target.iterdir() if (p / "SKILL.md").is_file())
        return sorted(user & {e["skill"] for e in scope.install if e["tier"] != "off"})

    def baseline(self, target, name, old):
        snapshot = baseline_dir(target) / old["hash"]
        if snapshot.is_dir() and not snapshot.is_symlink() and skill_hash(snapshot) == old["hash"]:
            return snapshot
        source = old.get("source")
        if source in self.manifest["sources"]:
            saved = self.lock.get("sources", {}).get(source)
            try:
                if old.get("sourceRevision"):
                    self.lock.setdefault("sources", {})[source] = {"sha": old["sourceRevision"]}
                path = find_skill(self.root(source), name)
                if skill_hash(path) == old["hash"]:
                    return path
            except SkillError:
                pass
            finally:
                if saved is None:
                    self.lock.get("sources", {}).pop(source, None)
                else:
                    self.lock["sources"][source] = saved
        raise SkillError(f"baseline unavailable for {name} at {target}; choose --keep {name} or --replace {name}")

    def merged(self, base, local, incoming, name):
        output = self.temp / f"merge-{uuid.uuid4().hex}"
        output.mkdir()
        versions = [tree_files(p) for p in (base, local, incoming)]
        conflicts = []
        for rel in sorted(set().union(*versions)):
            paths = [v.get(rel) for v in versions]
            values = [p.read_bytes() if p else None for p in paths]
            b, l, n = values
            if l == n or n == b:
                data, chosen = l, paths[1]
            elif l == b:
                data, chosen = n, paths[2]
            elif all(v is not None and b"\0" not in v for v in values):
                result = subprocess.run(["git", "merge-file", "-p", "-L", "project", "-L", "baseline",
                                         "-L", "upstream", str(paths[1]), str(paths[0]), str(paths[2])], capture_output=True)
                if result.returncode < 0 or result.returncode > 127:
                    raise SkillError(f"cannot merge {name}/{rel}: {result.stderr.decode(errors='replace')}")
                data, chosen = result.stdout, paths[1]
                if result.returncode:
                    conflicts.append(rel)
            else:
                data, chosen = l, paths[1]
                conflicts.append(rel)
            if data is not None:
                dest = output / rel
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(data)
                    if chosen:
                        dest.chmod(stat.S_IMODE(chosen.stat().st_mode))
                except OSError as exc:
                    raise SkillError(f"merge file/directory conflict in {name}/{rel}: {exc}") from exc
        if conflicts:
            if self.args.dry_run:
                raise SkillError(f"merge conflicts in {name}: {', '.join(conflicts)} (dry-run; no draft saved)")
            draft = self.repo / ".skills-work/merges" / f"{name}-{uuid.uuid4().hex[:8]}"
            draft.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(output, draft)
            write_json(Path(str(draft) + ".json"), {"skill": name, "baselineHash": skill_hash(base),
                       "localHash": skill_hash(local), "incomingHash": skill_hash(incoming),
                       "conflicts": conflicts})
            raise SkillError(f"merge conflicts in {name}: {', '.join(conflicts)}\nDraft: {draft}\n"
                             f"Resolve the draft, then run sync with --resolved '{name}={draft}'. "
                             "Binary and add/delete conflicts retain the project version in the draft.")
        return output

    def plan(self, scopes, source_filter=None):
        self.validate_targets()
        operations, issues = [], []
        self.planned_targets = {s.name: self.targets(s) for s in scopes}
        self.planned_receipts = {}
        for scope in scopes:
            duplicates = self.duplicates(scope)
            if duplicates:
                issues.append(f"{scope.name}: skills also installed at user scope: {', '.join(duplicates)}; "
                              "choose one scope or use distinct skill names")
                continue
            entries = {e["skill"]: e for e in scope.install if e["tier"] != "off"}
            receipts = {target: self.receipt(target) for target in self.targets(scope)}
            self.planned_receipts.update(receipts)
            relevant = set(entries) | set().union(*(set(r) for r in receipts.values()))
            if source_filter is not None:
                relevant = {name for name in relevant if
                            (name in entries and entries[name]["source"] in source_filter) or
                            any(r.get(name, {}).get("source") in source_filter for r in receipts.values())}
            incoming = {}
            for name in sorted(relevant & entries.keys()):
                entry = entries[name]
                path = find_skill(self.root(entry["source"]), name)
                staged = self.temp / f"incoming-{uuid.uuid4().hex}"
                copy_tree(path, staged)
                incoming[name] = staged
            for target, receipt in receipts.items():
                for name in sorted(relevant):
                    desired, old = entries.get(name), receipt.get(name)
                    if desired is None and old is None:
                        continue
                    local = target / name
                    if local.is_symlink():
                        issues.append(f"{local}: skill is a symlink; only target-directory symlinks are supported")
                        continue
                    exists = local.exists()
                    if exists and not local.is_dir():
                        issues.append(f"{local}: not a skill directory")
                        continue
                    if exists and old is None:
                        issues.append(f"{local}: foreign skill (no receipt); left untouched")
                        continue
                    current = skill_hash(local) if exists else None
                    customised = scope.project and old is not None and current is not None and current != old["hash"]
                    new_path = incoming.get(name)
                    new_hash = skill_hash(new_path) if new_path else None
                    changed = desired is None or old is None or old.get("source") != desired["source"] or old["hash"] != new_hash
                    choice, resolved = self.decisions.get(name, (None, None))
                    if customised and changed and choice is None:
                        issues.append(f"{scope.name}: {local} is customised and its source is changing or being removed.\n"
                                      f"  Preserve and merge: --merge {name}\n  Keep local and skip: --keep {name}\n"
                                      f"  Discard customisation: --replace {name}")
                        continue
                    if choice == "keep" and customised and changed:
                        operations.append(Operation(scope, target, name, "keep", current, old))
                        continue
                    if desired is None:
                        if customised and choice in {"merge", "resolved"}:
                            issues.append(f"cannot merge removal of {name}; choose --keep {name} or --replace {name}")
                        else:
                            operations.append(Operation(scope, target, name, "remove", current, None))
                        continue
                    entry = {"source": desired["source"], "tier": desired["tier"], "hash": new_hash,
                             "sourceRevision": self.lock.get("sources", {}).get(desired["source"], {}).get("sha")}
                    if old and not changed and current is not None and (scope.project or current == old["hash"]) and choice not in {"replace", "resolved"}:
                        operations.append(Operation(scope, target, name, "preserve", current, entry, new_path))
                        continue
                    payload, action = new_path, "install"
                    if customised and choice == "merge":
                        try:
                            payload = self.merged(self.baseline(target, name, old), local, new_path, name)
                            action = "merge"
                        except SkillError as exc:
                            issues.append(str(exc))
                            continue
                    elif choice == "resolved":
                        if resolved is None or not (resolved / "SKILL.md").is_file():
                            issues.append(f"resolved draft for {name} must contain SKILL.md")
                            continue
                        metadata = read_json(Path(str(resolved) + ".json"), {})
                        if metadata and (metadata.get("skill") != name or metadata.get("incomingHash") != new_hash
                                         or metadata.get("localHash") != current
                                         or metadata.get("baselineHash") != (old or {}).get("hash")):
                            issues.append(f"stale merge draft for {name}: baseline, project, or upstream changed; merge again")
                            continue
                        payload, action = resolved, "resolved"
                    staged = self.temp / f"install-{uuid.uuid4().hex}"
                    copy_tree(payload, staged)
                    if not (staged / "SKILL.md").is_file():
                        issues.append(f"merged skill {name} has no SKILL.md")
                        continue
                    operations.append(Operation(scope, target, name, action, current, entry, new_path, staged))
        # An invalid baseline in a later target must not fail after earlier
        # targets have already been installed.
        for op in operations:
            if op.scope.project and op.incoming is not None:
                snapshot = baseline_dir(op.target) / op.entry["hash"]
                if snapshot.exists() or snapshot.is_symlink():
                    if snapshot.is_symlink() or skill_hash(snapshot) != op.entry["hash"]:
                        issues.append(f"damaged baseline: {snapshot}")
        if issues:
            raise SkillError("preflight stopped; no installed skills or pins changed:\n" + "\n".join(issues))
        return operations

    def save_baseline(self, op):
        if not op.scope.project or op.incoming is None:
            return
        path = baseline_dir(op.target) / op.entry["hash"]
        if path.exists():
            if path.is_symlink() or skill_hash(path) != op.entry["hash"]:
                raise SkillError(f"damaged baseline: {path}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        copy_tree(op.incoming, path)

    def apply(self, operations, scopes):
        self.validate_targets()
        for scope in scopes:
            if self.targets(scope) != self.planned_targets[scope.name]:
                raise SkillError(f"targets for {scope.name} changed during preflight; run sync again")
        for target, receipt in self.planned_receipts.items():
            if self.receipt(target) != receipt:
                raise SkillError(f"receipt at {target} changed during preflight; run sync again")
        for op in operations:
            local = op.target / op.skill
            current = skill_hash(local) if local.exists() else None
            if local.is_symlink() or current != op.local_hash:
                raise SkillError(f"{local} changed during preflight; run sync again")
        receipts = {t: self.receipt(t) for s in scopes for t in self.targets(s)}
        for op in operations:
            local = op.target / op.skill
            self.save_baseline(op)
            if op.action in {"install", "merge", "resolved"}:
                op.target.mkdir(parents=True, exist_ok=True)
                candidate = Path(tempfile.mkdtemp(prefix=".skills-stage-", dir=op.target))
                shutil.rmtree(candidate)
                copy_tree(op.staged, candidate)
                if local.exists():
                    shutil.rmtree(local)
                os.replace(candidate, local)
            elif op.action == "remove":
                if local.exists():
                    shutil.rmtree(local)
                receipts[op.target].pop(op.skill, None)
                continue
            receipts[op.target][op.skill] = op.entry
        for target, receipt in receipts.items():
            write_json(target / RECEIPT, receipt)

    def overrides(self, scope):
        return {e["skill"]: "user-invocable-only" for e in sorted(scope.install, key=lambda e: e["skill"])
                if e["tier"] == "on-demand"}

    def settings_plan(self, scope):
        path = resolve_path(scope.settings)
        settings = read_json(path, {})
        if not isinstance(settings, dict) or not isinstance(settings.get("skillOverrides", {}), dict):
            raise SkillError(f"invalid settings object: {path}")
        state_path = self.repo / ".skills-work/settings" / (hashlib.sha256(os.fsencode(path)).hexdigest() + ".json")
        state = read_json(state_path, {})
        current = settings.setdefault("skillOverrides", {})
        desired, new_state = self.overrides(scope), {}
        for name, owned in state.items():
            if name not in desired and current.get(name) == owned["written"]:
                if owned["hadPrevious"]:
                    current[name] = owned["previous"]
                else:
                    current.pop(name, None)
        for name, value in desired.items():
            previous = state.get(name, {"hadPrevious": name in current, "previous": current.get(name)})
            new_state[name] = {**previous, "written": value}
            current[name] = value
        return path, settings, state_path, new_state

    def sync(self):
        scopes = self.selected()
        self.prepare_sources(scopes)
        plans = self.plan(scopes)
        settings = [self.settings_plan(s) for s in scopes] if self.args.write_settings else []
        for scope in scopes:
            print(f"== {scope.name}")
            self.targets(scope, display=True)
        for op in plans:
            print(f"  {op.action:8} {op.skill} -> {op.target}")
        if self.args.dry_run:
            print("dry-run: no targets, settings, or pins written")
            return
        self.apply(plans, scopes)
        if self.lock != self.original_lock:
            write_json(self.repo / "skills.lock.json", self.lock)
        for path, value, state_path, state in settings:
            if path.exists():
                shutil.copy2(path, Path(str(path) + ".bak"))
            write_json(path, value)
            write_json(state_path, state)
            print(f"wrote skillOverrides to {path}")
        if not self.args.write_settings:
            print("skillOverrides not written. Review with 'bin/skills overrides' (use --project for project settings).")

    def update(self):
        names = {n for n, s in self.manifest["sources"].items() if s["type"] == "github"}
        if self.args.source:
            if self.args.source not in names:
                raise SkillError(f"not a GitHub source: {self.args.source}")
            names = {self.args.source}
        if self.args.project or self.args.all:
            raise SkillError("update changes shared pins; select a source, not a scope")
        if self.args.dry_run:
            raise SkillError("update --dry-run is unsupported; sync --dry-run previews cached pins")
        for name in sorted(names):
            print(f"updating {name}...")
            sha = self.ensure_repo(name, update=True)
            self.lock.setdefault("sources", {})[name] = {"sha": sha}
        affected = []
        for scope in self.scopes:
            consumers = {e["source"] for e in scope.install}
            for target in self.targets(scope):
                consumers.update(e["source"] for e in self.receipt(target).values())
            if consumers & names:
                affected.append(scope)
        self.plan(affected, source_filter=names)
        write_json(self.repo / "skills.lock.json", self.lock)
        print("relocked; affected scopes: " + (", ".join(s.name for s in affected) or "none"))
        print("No installed copies changed. Run sync for the desired scope, repeating any customisation choices.")

    def listing(self):
        for scope in self.selected():
            print(f"== {scope.name}")
            print(f"{'SKILL':32} {'SOURCE':14} {'TIER':12} PATH")
            for entry in scope.install:
                try:
                    root = self.root(entry["source"])
                    path = str(find_skill(root, entry["skill"]).relative_to(root))
                except SkillError:
                    path = "(unresolved)"
                print(f"{entry['skill']:32} {entry['source']:14} {entry['tier']:12} {path}")

    def status(self):
        self.validate_targets()
        for scope in self.selected():
            print(f"== {scope.name}")
            for target in self.targets(scope, display=True):
                print(f"== {target}")
                if not target.is_dir():
                    print("   (missing)")
                    continue
                receipt = self.receipt(target)
                for name, entry in sorted(receipt.items()):
                    path = target / name
                    if not path.is_dir():
                        label = "gone"
                    elif skill_hash(path) != entry["hash"]:
                        label = "customised" if scope.project else "edited"
                    else:
                        label = "ok"
                    print(f"   {label:12} {name}")
                for path in sorted(target.iterdir()):
                    if (path / "SKILL.md").is_file() and path.name not in receipt:
                        print(f"   foreign      {path.name} (left alone)")

    def doctor(self):
        self.validate_targets()
        problems = []
        for scope in self.selected():
            print(f"== {scope.name}")
            self.targets(scope, display=True)
            for entry in scope.install:
                if entry["tier"] == "off":
                    continue
                try:
                    path = find_skill(self.root(entry["source"]), entry["skill"])
                    skill_hash(path)
                    if entry["tier"] == "auto" and re.search(r"(?m)^disable-model-invocation: *true", (path / "SKILL.md").read_text()):
                        problems.append(f"{entry['skill']}: auto but upstream disables model invocation")
                except SkillError as exc:
                    problems.append(str(exc))
            duplicates = self.duplicates(scope)
            if duplicates:
                problems.append(f"{scope.name}: user/project duplicate names: {', '.join(duplicates)}")
            for tier in sorted(TIERS):
                print(f"   {tier}: {sum(e['tier'] == tier for e in scope.install)}")
        if problems:
            raise SkillError("\n".join(problems))


def parser():
    result = argparse.ArgumentParser(description="Manage user and project skills from skills.json.")
    result.add_argument("command", nargs="?", default="sync", choices=["sync", "update", "list", "status", "doctor", "overrides"])
    result.add_argument("source", nargs="?", help="GitHub source to update")
    scope = result.add_mutually_exclusive_group()
    scope.add_argument("--project", metavar="NAME", help="select a registered project (default: user)")
    scope.add_argument("--all", action="store_true", help="select user and all registered projects")
    result.add_argument("--dry-run", action="store_true", help="preflight sync using cached pins without writing")
    result.add_argument("--write-settings", action="store_true", help="write scoped Claude overrides, preserving unrelated settings")
    result.add_argument("--merge", action="append", metavar="SKILL", help="preserve customisation with a three-way merge")
    result.add_argument("--keep", action="append", metavar="SKILL", help="keep a customised skill at its previous baseline")
    result.add_argument("--replace", action="append", metavar="SKILL", help="discard customisation, including on removal")
    result.add_argument("--resolved", action="append", metavar="SKILL=DIR", help="install an explicitly reviewed merge draft")
    return result


def main(repo, argv=None):
    args = parser().parse_args(argv)
    if args.source and args.command != "update":
        print("error: a source argument is only valid for update", file=sys.stderr)
        return 1
    if args.command not in {"sync", "update"} and (args.dry_run or args.write_settings or args.merge or args.keep or args.replace or args.resolved):
        print("error: write and customisation options require sync or update", file=sys.stderr)
        return 1
    if args.command == "update" and args.write_settings:
        print("error: --write-settings requires sync", file=sys.stderr)
        return 1
    manager = None
    try:
        manager = Manager(repo, args)
        if args.command == "overrides":
            scopes = manager.selected()
            value = manager.overrides(scopes[0]) if len(scopes) == 1 else {s.name: manager.overrides(s) for s in scopes}
            print(json.dumps(value, indent=2))
        else:
            getattr(manager, {"list": "listing"}.get(args.command, args.command))()
        return 0
    except (SkillError, OSError, ValueError, KeyError, TypeError, tarfile.TarError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if manager:
            manager.close()
