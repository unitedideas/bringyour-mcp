"""Check the skill's discovery command with disposable synthetic data only."""
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "skills/bringyour-migration-auditor/SKILL.md"


class AuditorDiscoveryTest(unittest.TestCase):
    def setUp(self):
        command = next(line for line in SKILL.read_text().splitlines() if line.startswith("grep "))
        self.argv = shlex.split(command)
        self.assertEqual(self.argv[3:], ["~/.codex", ".", "2>/dev/null"])
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()

    def run_search(self, flags=None):
        return subprocess.run(
            [self.argv[0], flags or self.argv[1], self.argv[2], str(self.source)],
            capture_output=True, text=True, check=False,
        )

    def test_old_search_leaks_but_documented_search_only_lists_files(self):
        marker = "SYNTHETIC_PRIVATE_VALUE_NOT_A_CREDENTIAL"
        config = self.source / "config.toml"
        config.write_text(f'api_key = "{marker}"\n')
        old = self.run_search("-RInE")
        self.assertEqual(old.returncode, 0)
        self.assertIn(marker, old.stdout)
        new = self.run_search()
        self.assertEqual(new.returncode, 0)
        self.assertEqual(new.stdout.splitlines(), [str(config)])
        self.assertNotIn(marker, new.stdout + new.stderr)

    def test_migration_residue_is_still_found(self):
        notes = self.source / "notes.md"
        notes.write_text("hook not equivalent; manual review of AGENTS.md\n")
        result = self.run_search()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), [str(notes)])
        self.assertNotIn("manual review", result.stdout)

    def test_no_matches_returns_one_without_output(self):
        (self.source / "notes.md").write_text("Ordinary text.\n")
        result = self.run_search()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout + result.stderr, "")

    def test_recursive_symlink_and_binary_are_not_read(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "config.toml").write_text("hook SYNTHETIC_OUTSIDE_RESIDUE\n")
        (self.source / "linked-dir").symlink_to(outside, target_is_directory=True)
        (self.source / "linked-file").symlink_to(outside / "config.toml")
        (self.source / "binary").write_bytes(b"\0hook SYNTHETIC_BINARY_RESIDUE\n")
        result = self.run_search()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout + result.stderr, "")


if __name__ == "__main__":
    unittest.main()
