"""CLI integration tests: every target and Git remote lives in a temporary repo."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class SkillsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skills-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        shutil.copytree(REPO, self.repo, ignore=shutil.ignore_patterns(
            ".git", "vendor", "__pycache__", ".skills-work"))
        self.project = self.root / "axis"
        self.project.mkdir()
        self.user = self.repo / "out"
        self.target = self.project / ".claude/skills"
        self.other = self.project / ".agents/skills"
        self.source = self.repo / "fixture-skills"
        self.skill("demo", self.source)
        self.manifest = {
            "targets": [str(self.user)],
            "sources": {"own": {"type": "local", "path": "fixture-skills"}},
            "install": [],
            "projects": {"axis": {"root": "../axis", "install": [self.entry()]}},
        }
        self.save()
        (self.repo / "skills.lock.json").write_text('{"sources":{}}\n')

    def entry(self, name="demo", source="own", tier="on-demand"):
        return {"skill": name, "source": source, "tier": tier}

    def skill(self, name, root, body="first\n\nsecond\n\nthird\n"):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(f"---\nname: {name}\ndescription: Fixture.\n---\n{body}")
        return path

    def save(self):
        (self.repo / "skills.json").write_text(json.dumps(self.manifest, indent=2))

    def cli(self, *args, success=True, cwd=None):
        result = subprocess.run([sys.executable, str(self.repo / "bin/skills"), *args],
                                cwd=cwd or self.root, capture_output=True, text=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def sync(self, *args, **kwargs):
        return self.cli("sync", "--project", "axis", *args, **kwargs)

    def receipt(self, target=None):
        return json.loads(((target or self.target) / ".skills-receipt.json").read_text())

    def edit(self, root, before, after, name="demo"):
        path = root / name / "SKILL.md"
        path.write_text(path.read_text().replace(before, after))

    def link_targets(self):
        self.target.mkdir(parents=True, exist_ok=True)
        self.other.parent.mkdir(parents=True, exist_ok=True)
        # Fixture reproduces an existing project alias; the installer creates no links.
        self.other.symlink_to("../.claude/skills", target_is_directory=True)

    def git(self, root, *args):
        result = subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture",
                                 "-c", "user.email=fixture@example.test", "-c", "commit.gpgsign=false",
                                 "-c", "core.hooksPath=/dev/null", *args], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def github_source(self, name="upstream"):
        remote = self.root / name
        remote.mkdir()
        self.git(remote, "init", "-b", "main")
        self.skill("demo", remote / "skills")
        self.git(remote, "add", ".")
        self.git(remote, "commit", "-m", "baseline")
        sha = self.git(remote, "rev-parse", "HEAD")
        vendor = self.repo / "vendor" / name
        vendor.parent.mkdir(parents=True, exist_ok=True)
        self.git(self.root, "clone", str(remote), str(vendor))
        self.manifest["sources"][name] = {"type": "github", "repo": f"fixture/{name}", "ref": "main"}
        self.manifest["projects"]["axis"]["install"] = [self.entry(source=name)]
        self.save()
        lock = json.loads((self.repo / "skills.lock.json").read_text())
        lock["sources"][name] = {"sha": sha}
        (self.repo / "skills.lock.json").write_text(json.dumps(lock))
        return remote, sha

    def advance(self, remote):
        self.edit(remote / "skills", "third", "upstream third")
        self.git(remote, "add", ".")
        self.git(remote, "commit", "-m", "upstream change")
        return self.git(remote, "rev-parse", "HEAD")

    def test_scopes_are_independent_and_paths_ignore_cwd(self):
        self.skill("personal", self.source)
        self.manifest["install"] = [self.entry("personal")]
        self.save()
        self.cli("sync")
        self.assertTrue((self.user / "personal/SKILL.md").is_file())
        self.assertFalse(self.target.exists())
        self.sync(cwd=self.project)
        self.assertFalse((self.target / "personal").exists())
        self.assertFalse((self.user / "demo").exists())
        self.manifest["projects"]["axis"]["install"] = []
        self.save()
        self.sync()
        self.assertFalse((self.target / "demo").exists())
        self.assertTrue((self.user / "personal/SKILL.md").is_file())

    def test_all_reconciles_both_scopes(self):
        self.skill("personal", self.source)
        self.manifest["install"] = [self.entry("personal")]
        self.save()
        self.cli("sync", "--all")
        self.assertTrue((self.user / "personal").is_dir())
        self.assertTrue((self.target / "demo").is_dir())

    def test_target_alias_is_preserved_and_written_once(self):
        self.link_targets()
        result = self.sync()
        self.assertTrue(self.other.is_symlink())
        self.assertIn("->", result.stdout)
        self.assertEqual(result.stdout.count("install  demo"), 1)
        self.assertEqual(self.receipt(), self.receipt(self.other))
        self.assertEqual(len(list((self.target.parent / ".skills-baselines").iterdir())), 1)
        self.assertFalse((self.target / ".skills-baselines").exists())

    def test_symlink_chain_and_symlinked_parent(self):
        physical = self.root / "physical"
        physical.mkdir()
        self.target.parent.mkdir(parents=True)
        self.target.symlink_to(physical, target_is_directory=True)
        self.other.parent.mkdir(parents=True)
        self.other.symlink_to(self.target, target_is_directory=True)
        self.sync()
        self.assertTrue((physical / "demo/SKILL.md").is_file())
        self.assertTrue(self.target.is_symlink())
        self.assertTrue(self.other.is_symlink())

    def test_broken_link_and_cycle_fail_without_writes(self):
        self.other.parent.mkdir(parents=True)
        self.other.symlink_to("missing")
        result = self.sync(success=False)
        self.assertIn("broken symlink", result.stderr)
        self.assertFalse(self.target.exists())
        self.other.unlink()
        self.other.symlink_to("skills")
        self.sync(success=False)
        self.assertFalse(self.target.exists())

    def test_cross_scope_target_alias_is_rejected(self):
        self.target.mkdir(parents=True)
        self.manifest["targets"] = [str(self.target)]
        self.save()
        self.assertIn("overlap", self.sync(success=False).stderr)
        self.assertFalse((self.target / "demo").exists())

    def test_dry_run_writes_nothing(self):
        before = (self.repo / "skills.lock.json").read_bytes()
        result = self.sync("--dry-run", "--write-settings")
        self.assertIn("dry-run", result.stdout)
        self.assertFalse(self.target.exists())
        self.assertFalse((self.project / ".claude/settings.local.json").exists())
        self.assertEqual((self.repo / "skills.lock.json").read_bytes(), before)

    def test_missing_source_and_foreign_collision_preflight_entire_scope(self):
        self.manifest["projects"]["axis"]["install"].append(self.entry("missing"))
        self.save()
        self.sync(success=False)
        self.assertFalse(self.target.exists())
        self.manifest["projects"]["axis"]["install"].pop()
        self.save()
        self.skill("demo", self.other, "foreign\n")
        self.assertIn("foreign", self.sync(success=False).stderr)
        self.assertFalse(self.target.exists())
        self.assertIn("foreign", (self.other / "demo/SKILL.md").read_text())

    def test_foreign_unrelated_skills_survive(self):
        self.skill("foreign", self.target)
        self.sync()
        self.assertTrue((self.target / "foreign").is_dir())
        self.assertIn("foreign", self.cli("status", "--project", "axis").stdout)

    def test_customisation_is_preserved_when_source_unchanged(self):
        self.sync()
        self.edit(self.target, "first", "custom first")
        before = self.receipt()["demo"]["hash"]
        self.sync()
        self.assertIn("custom first", (self.target / "demo/SKILL.md").read_text())
        self.assertEqual(self.receipt()["demo"]["hash"], before)
        self.assertIn("customised", self.cli("status", "--project", "axis").stdout)

    def test_reference_customisation_blocks_update_before_any_write(self):
        reference = self.source / "demo/references/tool.md"
        reference.parent.mkdir()
        reference.write_text("upstream reference\n")
        self.sync()
        (self.target / "demo/references/tool.md").write_text("custom reference\n")
        receipt = (self.target / ".skills-receipt.json").read_bytes()
        other = (self.other / "demo/SKILL.md").read_bytes()
        self.edit(self.source, "third", "upstream third")
        result = self.sync(success=False)
        self.assertIn("--merge demo", result.stderr)
        self.assertEqual((self.other / "demo/SKILL.md").read_bytes(), other)
        self.assertEqual((self.target / ".skills-receipt.json").read_bytes(), receipt)

    def test_merge_preserves_local_and_upstream_and_advances_baseline(self):
        self.link_targets()
        self.sync()
        self.edit(self.target, "first", "custom first")
        self.edit(self.source, "third", "upstream third")
        old = self.receipt()["demo"]["hash"]
        self.sync("--merge", "demo")
        content = (self.target / "demo/SKILL.md").read_text()
        self.assertIn("custom first", content)
        self.assertIn("upstream third", content)
        new = self.receipt()["demo"]["hash"]
        self.assertNotEqual(new, old)
        self.assertEqual((self.target.parent / f".skills-baselines/{new}/SKILL.md").read_text(),
                         (self.source / "demo/SKILL.md").read_text())
        self.sync()
        self.assertEqual((self.target / "demo/SKILL.md").read_text(), content)

    def test_keep_leaves_old_baseline_and_replace_discards_customisation(self):
        self.sync()
        old = self.receipt()["demo"]["hash"]
        self.edit(self.target, "first", "custom first")
        self.edit(self.source, "third", "upstream third")
        self.sync("--keep", "demo")
        self.assertEqual(self.receipt()["demo"]["hash"], old)
        self.assertIn("custom first", (self.target / "demo/SKILL.md").read_text())
        self.sync("--replace", "demo")
        self.assertEqual((self.target / "demo/SKILL.md").read_bytes(), (self.source / "demo/SKILL.md").read_bytes())

    def test_merge_conflicts_leave_targets_unchanged_and_save_reviewable_draft(self):
        self.link_targets()
        self.sync()
        self.edit(self.target, "first", "custom first")
        self.edit(self.source, "first", "upstream first")
        before = (self.target / "demo/SKILL.md").read_bytes()
        self.sync("--merge", "demo", success=False)
        self.assertEqual((self.target / "demo/SKILL.md").read_bytes(), before)
        draft = next(p for p in (self.repo / ".skills-work/merges").iterdir() if p.is_dir())
        self.assertIn("<<<<<<< project", (draft / "SKILL.md").read_text())
        (draft / "SKILL.md").write_bytes(before.replace(b"custom first", b"resolved first"))
        self.sync("--resolved", f"demo={draft}")
        self.assertIn("resolved first", (self.target / "demo/SKILL.md").read_text())

    def test_binary_conflict_is_not_silently_overwritten(self):
        (self.source / "demo/image.bin").write_bytes(b"\0baseline")
        self.sync()
        (self.target / "demo/image.bin").write_bytes(b"\0custom")
        (self.source / "demo/image.bin").write_bytes(b"\0upstream")
        self.sync("--merge", "demo", success=False)
        self.assertEqual((self.target / "demo/image.bin").read_bytes(), b"\0custom")

    def test_removal_and_off_protect_customised_copy(self):
        for off in (False, True):
            with self.subTest(off=off):
                self.manifest["projects"]["axis"]["install"] = [self.entry()]
                self.save()
                self.sync()
                self.edit(self.target, "first", "custom first")
                self.manifest["projects"]["axis"]["install"] = [self.entry(tier="off")] if off else []
                self.save()
                self.sync(success=False)
                self.sync("--keep", "demo")
                self.assertTrue((self.target / "demo").is_dir())
                self.assertIn("demo", self.receipt())
                self.sync("--replace", "demo")
                self.assertFalse((self.target / "demo").exists())
                self.assertNotIn("demo", self.receipt())

    def test_user_drift_keeps_existing_overwrite_behaviour_and_legacy_hash(self):
        self.manifest["install"] = [self.entry()]
        self.manifest["projects"] = {}
        self.save()
        self.cli("sync")
        digest = hashlib.sha256((self.source / "demo/SKILL.md").read_bytes()).hexdigest()
        legacy = hashlib.sha256(f"{digest}  ./SKILL.md\n".encode()).hexdigest()
        self.assertEqual(self.receipt(self.user)["demo"]["hash"], legacy)
        self.edit(self.user, "first", "edited first")
        self.cli("sync")
        self.assertNotIn("edited first", (self.user / "demo/SKILL.md").read_text())

    def test_project_settings_are_opt_in_and_preserve_hooks_and_foreign_overrides(self):
        path = self.project / ".claude/settings.local.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"hooks": {"keep": []}, "skillOverrides": {"foreign": "off", "demo": "name-only"}}))
        original = path.read_bytes()
        self.sync()
        self.assertEqual(path.read_bytes(), original)
        self.sync("--write-settings")
        written = json.loads(path.read_text())
        self.assertEqual(written["hooks"], {"keep": []})
        self.assertEqual(written["skillOverrides"], {"foreign": "off", "demo": "user-invocable-only"})
        self.manifest["projects"]["axis"]["install"] = []
        self.save()
        self.sync("--write-settings")
        self.assertEqual(json.loads(path.read_text())["skillOverrides"], {"foreign": "off", "demo": "name-only"})

    def test_duplicate_user_project_names_fail(self):
        self.manifest["install"] = [self.entry()]
        self.save()
        self.assertIn("user scope", self.sync(success=False).stderr)
        self.assertFalse(self.target.exists())

    def test_damaged_baseline_in_later_target_blocks_all_writes(self):
        self.sync()
        baseline = self.receipt()["demo"]["hash"]
        (self.other.parent / f".skills-baselines/{baseline}/SKILL.md").write_text("damaged\n")
        self.edit(self.target, "first", "custom first")
        before = (self.target / "demo/SKILL.md").read_bytes()
        # A legacy user-style restore would overwrite this customised copy;
        # validating every snapshot must happen before any such writes.
        result = self.sync(success=False)
        self.assertIn("damaged baseline", result.stderr)
        self.assertEqual((self.target / "demo/SKILL.md").read_bytes(), before)

    def test_invalid_settings_stop_before_installation(self):
        path = self.project / ".claude/settings.local.json"
        path.parent.mkdir()
        path.write_text("invalid json")
        self.sync("--write-settings", success=False)
        self.assertFalse((self.target / "demo").exists())

    def test_source_switch_protects_customisation(self):
        self.sync()
        self.edit(self.target, "first", "custom first")
        other_source = self.repo / "other-source"
        self.skill("demo", other_source, "different source\n")
        self.manifest["sources"]["other"] = {"type": "local", "path": "other-source"}
        self.manifest["projects"]["axis"]["install"] = [self.entry(source="other")]
        self.save()
        self.sync(success=False)
        self.assertIn("custom first", (self.target / "demo/SKILL.md").read_text())
        self.sync("--replace", "demo")
        self.assertIn("different source", (self.target / "demo/SKILL.md").read_text())

    def test_merge_additions_deletions_and_custom_file(self):
        (self.source / "demo/removed.md").write_text("old reference\n")
        self.sync()
        (self.target / "demo/custom.md").write_text("local addition\n")
        (self.source / "demo/removed.md").unlink()
        (self.source / "demo/added.md").write_text("upstream addition\n")
        self.sync("--merge", "demo")
        self.assertFalse((self.target / "demo/removed.md").exists())
        self.assertEqual((self.target / "demo/custom.md").read_text(), "local addition\n")
        self.assertEqual((self.target / "demo/added.md").read_text(), "upstream addition\n")

    def test_replace_can_discard_customisation_without_upstream_change(self):
        self.sync()
        self.edit(self.target, "first", "custom first")
        self.sync("--replace", "demo")
        self.assertEqual((self.target / "demo/SKILL.md").read_bytes(), (self.source / "demo/SKILL.md").read_bytes())

    def test_stale_merge_draft_is_rejected(self):
        self.link_targets()
        self.sync()
        self.edit(self.target, "first", "custom first")
        self.edit(self.source, "first", "upstream first")
        self.sync("--merge", "demo", success=False)
        draft = next(p for p in (self.repo / ".skills-work/merges").iterdir() if p.is_dir())
        self.edit(self.source, "third", "new upstream third")
        before = (self.target / "demo/SKILL.md").read_bytes()
        result = self.sync("--resolved", f"demo={draft}", success=False)
        self.assertIn("stale merge draft", result.stderr)
        self.assertEqual((self.target / "demo/SKILL.md").read_bytes(), before)

    def test_unknown_project_and_unsafe_names_fail(self):
        self.cli("sync", "--project", "missing", success=False)
        self.manifest["projects"]["axis"]["install"] = [self.entry("../escape")]
        self.save()
        self.sync(success=False)
        self.assertFalse(self.target.exists())

    def test_update_stops_before_pin_changes_and_merge_then_sync_preserves_customisation(self):
        remote, old = self.github_source()
        self.link_targets()
        self.sync()
        self.assertEqual(self.receipt()["demo"]["sourceRevision"], old)
        self.edit(self.target, "first", "custom first")
        new = self.advance(remote)
        before = (self.repo / "skills.lock.json").read_bytes()
        result = self.cli("update", "upstream", success=False)
        self.assertIn("customised", result.stderr)
        self.assertEqual((self.repo / "skills.lock.json").read_bytes(), before)
        self.cli("update", "upstream", "--merge", "demo")
        lock = json.loads((self.repo / "skills.lock.json").read_text())
        self.assertEqual(lock["sources"]["upstream"]["sha"], new)
        self.assertNotIn("upstream third", (self.target / "demo/SKILL.md").read_text())
        self.sync("--merge", "demo")
        content = (self.target / "demo/SKILL.md").read_text()
        self.assertIn("custom first", content)
        self.assertIn("upstream third", content)
        self.assertEqual(self.receipt()["demo"]["sourceRevision"], new)

    def test_update_one_source_preserves_unrelated_pin(self):
        remote, old = self.github_source()
        self.manifest["sources"]["unused"] = {"type": "github", "repo": "fixture/unused", "ref": "main"}
        self.save()
        lock = json.loads((self.repo / "skills.lock.json").read_text())
        lock["sources"]["unused"] = {"sha": "a" * 40}
        (self.repo / "skills.lock.json").write_text(json.dumps(lock))
        new = self.advance(remote)
        self.cli("update", "upstream")
        lock = json.loads((self.repo / "skills.lock.json").read_text())
        self.assertEqual(lock["sources"]["upstream"]["sha"], new)
        self.assertEqual(lock["sources"]["unused"]["sha"], "a" * 40)
        self.assertNotEqual(old, new)

    def test_deleted_upstream_skill_does_not_remove_installed_copy_or_advance_pin(self):
        remote, _ = self.github_source()
        self.sync()
        self.git(remote, "rm", "-r", "skills/demo")
        self.git(remote, "commit", "-m", "remove skill")
        before = (self.repo / "skills.lock.json").read_bytes()
        self.cli("update", "upstream", success=False)
        self.assertEqual((self.repo / "skills.lock.json").read_bytes(), before)
        self.assertTrue((self.target / "demo/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
