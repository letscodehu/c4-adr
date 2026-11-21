"""Unit tests for .github/scripts/highlight-diff.

Run from the repository root:

    python3 -m unittest discover -s .github/scripts/tests -v

Uses the Structurizr JSON fixtures of test_model_diff.py: the diff is computed
with model-diff, then highlighted on the base or head workspace.
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def load_script(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(HERE.parent / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


model_diff = load_script("model-diff")
highlight_diff = load_script("highlight-diff")


def load(name):
    with open(FIXTURES / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def all_items(workspace):
    """Return {id: element or relationship} of the whole model."""
    result = {}
    for collection in ("people", "softwareSystems", "customElements", "deploymentNodes"):
        for top in workspace["model"].get(collection, []):
            for element, relationships in highlight_diff.walk(top):
                result[element["id"]] = element
                for relationship in relationships:
                    result[relationship["id"]] = relationship
    return result


def tags(raw):
    return raw.get("tags", "").split(",")


def highlighted(base, head, side):
    """Highlight the diff of two fixtures on one side; return that workspace."""
    diff = model_diff.diff_ids(load(base), load(head))
    workspace = load(head if side == "--after" else base)
    highlight_diff.highlight(workspace, diff, side)
    return workspace, diff


def diff_tagged(workspace):
    """Return {id: Diff tag} of everything tagged."""
    return {
        item_id: tag
        for item_id, raw in all_items(workspace).items()
        for tag in tags(raw)
        if tag.startswith("Diff: ")
    }


class AfterTest(unittest.TestCase):
    def test_new_element_is_tagged_added_and_styled_green(self):
        workspace, diff = highlighted("base", "new-element", "--after")
        self.assertEqual(diff_tagged(workspace), {diff["added"][0]["id"]: "Diff: Added"})
        styles = workspace["views"]["configuration"]["styles"]
        self.assertIn({"tag": "Diff: Added", **highlight_diff.ELEMENT_STYLES["Diff: Added"]}, styles["elements"])
        self.assertNotIn("relationships", styles)

    def test_new_relationship_and_its_implied_ones_are_added(self):
        workspace, diff = highlighted("base", "implied-relationship", "--after")
        (item,) = diff["added"]
        expected = {i: "Diff: Added" for i in [item["id"], *item["related"]]}
        self.assertEqual(len(expected), 3)
        self.assertEqual(diff_tagged(workspace), expected)
        styles = workspace["views"]["configuration"]["styles"]
        self.assertIn(
            {"tag": "Diff: Added", **highlight_diff.RELATIONSHIP_STYLES["Diff: Added"]}, styles["relationships"]
        )

    def test_changed_element_and_its_instances_are_changed(self):
        workspace, diff = highlighted("base", "description-change", "--after")
        (item,) = diff["changed"]
        self.assertEqual(diff_tagged(workspace), {item["id"]: "Diff: Changed", item["related"][0]: "Diff: Changed"})
        instance = all_items(workspace)[item["related"][0]]
        self.assertEqual(instance["containerId"], item["id"])

    def test_changed_relationship_is_changed(self):
        workspace, diff = highlighted("base", "relationship-description-change", "--after")
        (item,) = diff["changed"]
        self.assertEqual(
            diff_tagged(workspace), {i: "Diff: Changed" for i in [item["id"], *item["related"]]}
        )

    def test_deployment_node_is_tagged(self):
        workspace, diff = highlighted("base", "deployment-node", "--after")
        node = all_items(workspace)[diff["added"][0]["id"]]
        self.assertEqual(node["name"], "RDS")
        self.assertIn("Diff: Added", tags(node))

    def test_removed_items_are_not_marked_on_the_after_side(self):
        workspace, _ = highlighted("new-element", "base", "--after")
        self.assertEqual(diff_tagged(workspace), {})


class BeforeTest(unittest.TestCase):
    def test_removed_relationship_is_red_and_dashed(self):
        workspace, diff = highlighted("new-relationship", "base", "--before")
        self.assertEqual(diff_tagged(workspace), {diff["removed"][0]["id"]: "Diff: Removed"})
        (style,) = workspace["views"]["configuration"]["styles"]["relationships"]
        self.assertEqual(style["tag"], "Diff: Removed")
        self.assertEqual(style["style"], "Dashed")

    def test_removed_element_has_a_dashed_border(self):
        workspace, _ = highlighted("new-element", "base", "--before")
        styles = workspace["views"]["configuration"]["styles"]["elements"]
        self.assertIn({"tag": "Diff: Removed", **highlight_diff.ELEMENT_STYLES["Diff: Removed"]}, styles)
        self.assertEqual(highlight_diff.ELEMENT_STYLES["Diff: Removed"]["border"], "Dashed")

    def test_added_and_changed_items_are_not_marked_on_the_before_side(self):
        workspace, _ = highlighted("base", "description-change", "--before")
        self.assertEqual(diff_tagged(workspace), {})


class KeepsExistingTest(unittest.TestCase):
    def test_existing_tags_are_kept_and_the_diff_tag_comes_last(self):
        workspace, diff = highlighted("base", "tag-change", "--after")
        before = all_items(load("tag-change"))[diff["changed"][0]["id"]]
        after = all_items(workspace)[diff["changed"][0]["id"]]
        self.assertEqual(tags(after), tags(before) + ["Diff: Changed"])

    def test_existing_styles_are_kept(self):
        original = load("base")["views"]["configuration"]["styles"]["elements"]
        workspace, _ = highlighted("base", "new-element", "--after")
        styles = workspace["views"]["configuration"]["styles"]["elements"]
        self.assertEqual(styles[: len(original)], original)
        self.assertEqual(len(styles), len(original) + 1)

    def test_styles_do_not_touch_fill_or_shape(self):
        # Only the border of elements and the line of relationships.
        for style in highlight_diff.ELEMENT_STYLES.values():
            self.assertLessEqual(set(style), {"stroke", "strokeWidth", "border"})
        for style in highlight_diff.RELATIONSHIP_STYLES.values():
            self.assertLessEqual(set(style), {"color", "thickness", "style"})

    def test_no_differences_change_nothing(self):
        diff = model_diff.diff_ids(load("base"), load("views-only"))
        workspace = load("views-only")
        self.assertEqual(highlight_diff.highlight(workspace, diff, "--after"), {})
        self.assertEqual(workspace, load("views-only"))


class CommandLineTest(unittest.TestCase):
    def test_writes_the_highlighted_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            diff_path = pathlib.Path(tmp) / "diff.json"
            output = pathlib.Path(tmp) / "out.json"
            diff_path.write_text(json.dumps(model_diff.diff_ids(load("base"), load("new-element"))))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = highlight_diff.main(
                    ["highlight-diff", "--after", str(FIXTURES / "new-element.json"), str(diff_path), str(output)]
                )
            self.assertEqual(code, 0)
            self.assertIn("1 Diff: Added", err.getvalue())
            self.assertEqual(len(diff_tagged(json.loads(output.read_text()))), 1)

    def test_bad_usage_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(highlight_diff.main(["highlight-diff", "--sideways", "a", "b", "c"]), 2)
            self.assertEqual(highlight_diff.main(["highlight-diff", "--after", "nope.json", "nope.json", "x"]), 2)


if __name__ == "__main__":
    unittest.main()
