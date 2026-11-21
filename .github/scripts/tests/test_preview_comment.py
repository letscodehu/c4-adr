"""Unit tests for .github/scripts/preview-comment.

Run from the repository root:

    python3 -m unittest discover -s .github/scripts/tests -v

The fixtures in fixtures/preview/ are minimal `render-views` output directories
(PlantUML sources only, no images are needed to build the comment):

    view            base   head
    SystemContext   yes    yes, a relationship description changed  -> changed
    Containers      yes    yes, identical                           -> unchanged
    Legacy          yes    no                                       -> removed
    Deployment      no     yes                                      -> new

HighlightTest copies them into a temporary directory and adds highlighted
`<view-key>.diff.puml` files, as `render-views --compare-to` writes them.
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
FIXTURES = HERE / "fixtures" / "preview"
SCRIPT = HERE.parent / "preview-comment"

loader = importlib.machinery.SourceFileLoader("preview_comment", str(SCRIPT))
spec = importlib.util.spec_from_loader("preview_comment", loader)
preview_comment = importlib.util.module_from_spec(spec)
loader.exec_module(preview_comment)

BASE_URL = "https://raw.githubusercontent.com/letscodehu/c4-adr/diagram-previews/pr-7/abc1234/base"
HEAD_URL = "https://raw.githubusercontent.com/letscodehu/c4-adr/diagram-previews/pr-7/abc1234/head"


def views(side):
    return preview_comment.read_views(FIXTURES / side)


def comment(base="base", head="head", **kwargs):
    return preview_comment.build_comment(views(base), views(head), BASE_URL, HEAD_URL, **kwargs)


def section(text, key):
    """The heading and the table (five lines) of the `### <key> (...)` section."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"### {key} "))
    return lines[start : start + 5]


class CompareTest(unittest.TestCase):
    def test_every_status(self):
        self.assertEqual(
            preview_comment.compare(views("base"), views("head")),
            [
                ("Containers", "unchanged"),
                ("Deployment", "new"),
                ("Legacy", "removed"),
                ("SystemContext", "changed"),
            ],
        )


class CommentTest(unittest.TestCase):
    def test_starts_with_the_marker(self):
        self.assertEqual(comment().splitlines()[0], "<!-- diagram-preview -->")

    def test_summary_counts_the_differences(self):
        self.assertIn("**3 of 4 view(s) differ:** 1 changed, 1 new view, 1 removed.", comment())

    def test_changed_view_shows_before_and_after(self):
        self.assertEqual(
            section(comment(), "SystemContext"),
            [
                "### SystemContext (changed)",
                "",
                "| Before | After |",
                "| --- | --- |",
                f"| ![SystemContext (before)]({BASE_URL}/SystemContext.png)"
                f" | ![SystemContext (after)]({HEAD_URL}/SystemContext.png) |",
            ],
        )

    def test_new_view_says_new_view_before_and_shows_after(self):
        self.assertEqual(
            section(comment(), "Deployment"),
            [
                "### Deployment (new view)",
                "",
                "| Before | After |",
                "| --- | --- |",
                f"| _new view_ | ![Deployment (after)]({HEAD_URL}/Deployment.png) |",
            ],
        )

    def test_removed_view_shows_before_and_says_removed_after(self):
        self.assertEqual(
            section(comment(), "Legacy"),
            [
                "### Legacy (removed)",
                "",
                "| Before | After |",
                "| --- | --- |",
                f"| ![Legacy (before)]({BASE_URL}/Legacy.png) | _removed_ |",
            ],
        )

    def test_unchanged_view_is_collapsed(self):
        text = comment()
        self.assertNotIn("### Containers", text)
        details = text[text.index("<details>") : text.index("</details>")]
        self.assertIn("<summary>Unchanged views (1)</summary>", details)
        self.assertIn(f"![Containers (unchanged)]({HEAD_URL}/Containers.png)", details)

    def test_differing_views_come_before_unchanged_ones(self):
        text = comment()
        self.assertLess(text.index("### SystemContext"), text.index("<details>"))

    def test_footer_links_revisions_and_artifact(self):
        text = comment(base_rev="1111111", head_rev="2222222", run_url="https://example.test/run/1")
        self.assertIn("Before: `1111111` (base), after: `2222222` (this pull request).", text)
        self.assertIn("[workflow run](https://example.test/run/1)", text)
        self.assertIn("never on `main`", text)


class NoChangesTest(unittest.TestCase):
    def test_identical_views_say_no_diagram_changes(self):
        text = comment(base="head", head="head")
        self.assertIn("**No diagram changes.** None of the 3 view(s) changed.", text)
        self.assertNotIn("| Before | After |", text)
        self.assertIn("<summary>Unchanged views (3)</summary>", text)

    def test_no_views_at_all(self):
        text = preview_comment.build_comment({}, {}, BASE_URL, HEAD_URL)
        self.assertIn("**No diagram changes.**", text)
        self.assertNotIn("<details>", text)


class HighlightTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dirs = {}
        for side in ("base", "head"):
            self.dirs[side] = pathlib.Path(tmp.name) / side
            shutil.copytree(FIXTURES / side, self.dirs[side])

    def highlight(self, side, *keys):
        for key in keys:
            source = (self.dirs[side] / f"{key}.puml").read_text(encoding="utf-8")
            highlighted = source.replace("@enduml", "' // Element,Diff: Removed\n@enduml")
            (self.dirs[side] / f"{key}.diff.puml").write_text(highlighted, encoding="utf-8")

    def comment(self):
        return preview_comment.build_comment(
            preview_comment.read_views(self.dirs["base"]),
            preview_comment.read_views(self.dirs["head"]),
            BASE_URL,
            HEAD_URL,
            highlighted=preview_comment.read_highlighted(self.dirs["head"]),
        )

    def test_highlighted_sources_do_not_change_the_classification(self):
        self.highlight("base", "SystemContext", "Containers", "Legacy")
        self.highlight("head", "SystemContext", "Containers", "Deployment")
        self.assertEqual(
            preview_comment.compare(
                preview_comment.read_views(self.dirs["base"]), preview_comment.read_views(self.dirs["head"])
            ),
            preview_comment.compare(views("base"), views("head")),
        )

    def test_after_is_highlighted_before_stays_plain_and_legend_is_shown(self):
        self.highlight("head", "SystemContext", "Deployment")
        text = self.comment()
        self.assertIn(preview_comment.LEGEND, text)
        self.assertLess(text.index(preview_comment.LEGEND), text.index("| Before | After |"))
        self.assertEqual(
            section(text, "SystemContext")[-1],
            f"| ![SystemContext (before)]({BASE_URL}/SystemContext.png)"
            f" | ![SystemContext (after)]({HEAD_URL}/SystemContext.diff.png) |",
        )
        self.assertEqual(
            section(text, "Deployment")[-1], f"| _new view_ | ![Deployment (after)]({HEAD_URL}/Deployment.diff.png) |"
        )
        self.assertEqual(section(text, "Legacy")[-1], f"| ![Legacy (before)]({BASE_URL}/Legacy.png) | _removed_ |")

    def test_base_side_is_never_highlighted(self):
        self.highlight("base", "SystemContext", "Legacy")
        text = self.comment()
        self.assertNotIn(".diff.png", text)
        self.assertNotIn(preview_comment.LEGEND, text)

    def test_unchanged_views_show_the_plain_image_and_no_legend(self):
        # E.g. only a url changed: highlighted, but nothing visible changed.
        self.highlight("head", "Containers")
        text = self.comment()
        self.assertNotIn(preview_comment.LEGEND, text)
        self.assertNotIn(".diff.png", text)

    def test_without_highlighting_the_comment_is_as_before(self):
        self.assertEqual(self.comment(), comment())
        self.assertNotIn(preview_comment.LEGEND, comment())

    def test_command_line_reads_the_highlighted_images(self):
        self.highlight("head", "SystemContext")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = preview_comment.main(
                ["preview-comment", str(self.dirs["base"]), str(self.dirs["head"]), BASE_URL, HEAD_URL]
            )
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), self.comment())
        self.assertIn(f"{HEAD_URL}/SystemContext.diff.png", out.getvalue())


class CommandLineTest(unittest.TestCase):
    def run_main(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = preview_comment.main(["preview-comment", *args])
        return code, out.getvalue()

    def test_prints_the_comment(self):
        code, out = self.run_main(str(FIXTURES / "base"), str(FIXTURES / "head"), BASE_URL, HEAD_URL)
        self.assertEqual(code, 0)
        self.assertEqual(out, comment())

    def test_missing_directory_exits_2(self):
        code, _ = self.run_main(str(FIXTURES / "nope"), str(FIXTURES / "head"), BASE_URL, HEAD_URL)
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
