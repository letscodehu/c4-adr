"""Unit tests for .github/scripts/log4brains-prepare.

Run from the repository root:

    python3 -m unittest discover -s .github/scripts/tests -v
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import pathlib
import shutil
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE.parent / "log4brains-prepare"
DECISIONS = HERE.parents[2] / "docs" / "architecture" / "decisions"

loader = importlib.machinery.SourceFileLoader("log4brains_prepare", str(SCRIPT))
spec = importlib.util.spec_from_loader("log4brains_prepare", loader)
prepare = importlib.util.module_from_spec(spec)
loader.exec_module(prepare)

SUPERSEDED = """\
---
status: superseded by ADR-0006
date: 2026-11-20
---

# Synchronous REST between Order and Inventory

* Status: Superseded by [ADR-0006: Introduce an event bus (RabbitMQ)](0006-introduce-an-event-bus-rabbitmq.md)
* Date: 2026-11-20

## Context and Problem Statement

See [ADR-0006: Introduce an event bus (RabbitMQ)](0006-introduce-an-event-bus-rabbitmq.md).
"""


class PrepareTest(unittest.TestCase):
    def test_strips_front_matter_and_slugs_the_superseded_by_link(self):
        self.assertEqual(
            prepare.prepare(SUPERSEDED),
            """\
# Synchronous REST between Order and Inventory

* Status: Superseded by [0006-introduce-an-event-bus-rabbitmq](0006-introduce-an-event-bus-rabbitmq.md)
* Date: 2026-11-20

## Context and Problem Statement

See [ADR-0006: Introduce an event bus (RabbitMQ)](0006-introduce-an-event-bus-rabbitmq.md).
""",
        )

    def test_leaves_an_adr_without_front_matter_unchanged(self):
        text = "# Use PostgreSQL\n\n* Status: Accepted\n* Date: 2026-11-20\n\n## Context\n\n---\n\nText.\n"
        self.assertEqual(prepare.prepare(text), text)

    def test_leaves_an_unclosed_front_matter_block_unchanged(self):
        text = "---\nstatus: accepted\n\n# Title\n"
        self.assertEqual(prepare.prepare(text), text)

    def test_moves_metadata_items_in_front_of_the_other_header_items(self):
        text = (
            "---\nstatus: accepted\n---\n\n# T\n\n"
            "* Status: Accepted\n"
            "* Supersedes: [ADR-0005: X](0005-x.md)\n"
            "* Date: 2026-11-20\n"
            "\n## Context\n\n* Supersedes is not metadata here\n* Date: neither is this\n"
        )
        self.assertEqual(
            prepare.prepare(text),
            "# T\n\n"
            "* Status: Accepted\n"
            "* Date: 2026-11-20\n"
            "* Supersedes: [ADR-0005: X](0005-x.md)\n"
            "\n## Context\n\n* Supersedes is not metadata here\n* Date: neither is this\n",
        )

    def test_leaves_a_document_without_a_title_or_header_list_unchanged(self):
        for text in ("No title\n* Date: x\n* Other\n", "# T\n\nText.\n* Other\n* Date: x\n"):
            with self.subTest(text=text):
                self.assertEqual(prepare.prepare(text), text)

    def test_handles_dash_bullets_and_a_colon_after_superseded_by(self):
        self.assertEqual(
            prepare.prepare("# T\n\n- status: superseded by: [later](./0009-later.md)\n"),
            "# T\n\n- status: superseded by: [0009-later](./0009-later.md)\n",
        )

    def test_is_idempotent(self):
        once = prepare.prepare(SUPERSEDED)
        self.assertEqual(prepare.prepare(once), once)


class MainTest(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = prepare.main(["log4brains-prepare", *args])
        return status, out.getvalue(), err.getvalue()

    def test_prepares_a_copy_of_the_repository_adrs_in_place(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp) / "decisions"
            shutil.copytree(DECISIONS, target)
            status, out, _ = self.run_main(str(target))
            self.assertEqual(status, 0)
            for path in sorted(target.glob("*.md")):
                text = path.read_text(encoding="utf-8")
                with self.subTest(adr=path.name):
                    self.assertTrue(text.startswith("# "), "title is the first line")
                    self.assertRegex(text, r"\n\* Status: ")
                    self.assertRegex(text, r"\n\* Date: \d{4}-\d{2}-\d{2}\n")
                    header = text.split("\n## ", 1)[0].strip().split("\n")[2:]
                    self.assertRegex(header[-1], r"^\* (?!Status|Date)|^\* (Status|Date): ",
                                     "a header item log4brains keeps, or only metadata")
                    kinds = ["meta" if prepare.METADATA_ITEM.match(l) else "other" for l in header]
                    self.assertEqual(kinds, sorted(kinds), "metadata items come first")
            superseded = (target / "0005-synchronous-rest-between-order-and-inventory.md").read_text(encoding="utf-8")
            self.assertIn(
                "* Status: Superseded by [0006-introduce-an-event-bus-rabbitmq](0006-introduce-an-event-bus-rabbitmq.md)",
                superseded,
            )
            self.assertIn("0005-synchronous-rest-between-order-and-inventory.md", out)

    def test_rejects_a_missing_directory(self):
        status, _, err = self.run_main("does-not-exist")
        self.assertEqual(status, 2)
        self.assertIn("not a directory", err)

    def test_rejects_a_wrong_number_of_arguments(self):
        status, _, err = self.run_main()
        self.assertEqual(status, 2)
        self.assertIn("Usage", err)


if __name__ == "__main__":
    unittest.main()
