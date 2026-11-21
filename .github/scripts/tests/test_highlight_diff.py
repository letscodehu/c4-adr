"""Unit tests for .github/scripts/highlight-diff.

Run from the repository root:

    python3 -m unittest discover -s .github/scripts/tests -v

Uses the Structurizr JSON fixtures of test_model_diff.py: the diff of two
fixtures is computed with model-diff, then highlighted on the head workspace.
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


def tags(raw):
    return raw.get("tags", "").split(",")


def highlighted(base, head):
    """Highlight the diff of two fixtures on the head; return (workspace, diff)."""
    diff = model_diff.diff_ids(load(base), load(head))
    workspace = load(head)
    highlight_diff.highlight(load(base), workspace, diff)
    return workspace, diff


def diff_tagged(workspace):
    """Return {id: Diff tag} of every element and relationship tagged."""
    elements, relationships = highlight_diff.index(workspace)
    return {
        item_id: tag
        for items in (elements, relationships)
        for item_id, (raw, *_) in items.items()
        for tag in tags(raw)
        if tag.startswith("Diff: ")
    }


def view(workspace, key="SystemContext"):
    return highlight_diff.views_by_key(workspace)[key]


class AddedAndChangedTest(unittest.TestCase):
    def test_new_element_is_tagged_added_and_styled_green(self):
        workspace, diff = highlighted("base", "new-element")
        self.assertEqual(diff_tagged(workspace), {diff["added"][0]["id"]: "Diff: Added"})
        styles = workspace["views"]["configuration"]["styles"]
        self.assertIn({"tag": "Diff: Added", **highlight_diff.ELEMENT_STYLES["Diff: Added"]}, styles["elements"])
        self.assertNotIn("relationships", styles)

    def test_new_relationship_and_its_implied_ones_are_added(self):
        workspace, diff = highlighted("base", "implied-relationship")
        (item,) = diff["added"]
        expected = {i: "Diff: Added" for i in [item["id"], *item["related"]]}
        self.assertEqual(len(expected), 3)
        self.assertEqual(diff_tagged(workspace), expected)
        styles = workspace["views"]["configuration"]["styles"]
        self.assertIn(
            {"tag": "Diff: Added", **highlight_diff.RELATIONSHIP_STYLES["Diff: Added"]}, styles["relationships"]
        )

    def test_changed_element_and_its_instances_are_changed(self):
        workspace, diff = highlighted("base", "description-change")
        (item,) = diff["changed"]
        self.assertEqual(diff_tagged(workspace), {item["id"]: "Diff: Changed", item["related"][0]: "Diff: Changed"})
        elements, _ = highlight_diff.index(workspace)
        self.assertEqual(elements[item["related"][0]][0]["containerId"], item["id"])

    def test_changed_relationship_is_changed_not_removed(self):
        workspace, diff = highlighted("base", "relationship-description-change")
        (item,) = diff["changed"]
        self.assertEqual(diff_tagged(workspace), {i: "Diff: Changed" for i in [item["id"], *item["related"]]})

    def test_deployment_node_is_tagged(self):
        workspace, diff = highlighted("base", "deployment-node")
        elements, _ = highlight_diff.index(workspace)
        node = elements[diff["added"][0]["id"]][0]
        self.assertEqual(node["name"], "RDS")
        self.assertIn("Diff: Added", tags(node))


class RemovedTest(unittest.TestCase):
    """Removed items are copied back into the head, so the After image shows them."""

    def test_removed_relationship_is_restored_red_dashed_and_shown(self):
        workspace, diff = highlighted("new-relationship", "base")
        tagged = diff_tagged(workspace)
        (new_id,) = tagged
        self.assertEqual(tagged[new_id], "Diff: Removed")
        _, relationships = highlight_diff.index(workspace)
        restored, owner = relationships[new_id]
        self.assertEqual(restored["description"], "Delivers emails to")
        self.assertEqual(owner["name"], "Email Service")
        customer = next(p for p in workspace["model"]["people"] if p["name"] == "Customer")
        self.assertEqual(restored["destinationId"], customer["id"])
        self.assertIn({"id": new_id}, view(workspace)["relationships"])
        (style,) = workspace["views"]["configuration"]["styles"]["relationships"]
        self.assertEqual(style, {"tag": "Diff: Removed", **highlight_diff.RELATIONSHIP_STYLES["Diff: Removed"]})
        self.assertEqual(style["style"], "Dashed")

    def test_removed_ids_do_not_clash(self):
        workspace, _ = highlighted("new-relationship", "base")
        elements, relationships = highlight_diff.index(workspace)
        original_elements, original_relationships = highlight_diff.index(load("base"))
        self.assertEqual(len(elements) + len(relationships), len(original_elements) + len(original_relationships) + 1)

    def test_removed_element_is_restored_under_its_parent(self):
        workspace, diff = highlighted("new-element", "base")
        self.assertEqual(list(diff_tagged(workspace).values()), ["Diff: Removed"])
        webshop = next(s for s in workspace["model"]["softwareSystems"] if s["name"] == "Webshop")
        database = next(c for c in webshop["containers"] if c["name"] == "Database")
        self.assertIn("Diff: Removed", tags(database))
        styles = workspace["views"]["configuration"]["styles"]["elements"]
        self.assertIn({"tag": "Diff: Removed", **highlight_diff.ELEMENT_STYLES["Diff: Removed"]}, styles)

    def test_removed_deployment_node_is_restored(self):
        workspace, _ = highlighted("deployment-node", "base")
        aws = workspace["model"]["deploymentNodes"][0]
        rds = next(n for n in aws["children"] if n["name"] == "RDS")
        self.assertIn("Diff: Removed", tags(rds))

    def test_removed_instance_is_restored_with_its_replicated_relationship(self):
        base = load("base")
        head = load("base")
        ec2 = head["model"]["deploymentNodes"][0]["children"][0]
        web_instance, api_instance = ec2["containerInstances"]
        ec2["containerInstances"] = [web_instance]
        web_instance["relationships"] = []  # the replicated Web App -> API ("Calls")
        highlight_diff.highlight(base, head, model_diff.diff_ids(base, head))

        restored_instance = next(i for i in ec2["containerInstances"] if "Diff: Removed" in tags(i))
        self.assertEqual(restored_instance["containerId"], api_instance["containerId"])
        (replicated,) = web_instance["relationships"]
        self.assertIn("Diff: Removed", tags(replicated))
        self.assertEqual(replicated["destinationId"], restored_instance["id"])
        # Still linked to the (kept) Web App -> API relationship of the head.
        _, relationships = highlight_diff.index(head)
        self.assertIn(replicated["linkedRelationshipId"], relationships)

    def test_removed_implied_relationship_is_restored_and_linked(self):
        workspace, diff = highlighted("implied-relationship", "base")
        (item,) = diff["removed"]
        _, relationships = highlight_diff.index(workspace)
        restored = {i: raw for i, (raw, _) in relationships.items() if "Diff: Removed" in tags(raw)}
        self.assertEqual(len(restored), 3)  # explicit + 2 implied
        explicit = [i for i, raw in restored.items() if "linkedRelationshipId" not in raw]
        self.assertEqual(len(explicit), 1)
        for raw in restored.values():
            if "linkedRelationshipId" in raw:
                self.assertEqual(raw["linkedRelationshipId"], explicit[0])
        # The System Context view showed Webshop -> Customer "Notifies": it still does.
        shown = {r["id"] for r in view(workspace)["relationships"]}
        self.assertEqual(len(shown & set(restored)), 1)

    def test_removed_items_are_shown_with_their_end_points(self):
        base = load("new-relationship")
        head = load("base")
        # Pretend the head view no longer shows the Email Service.
        email = next(s for s in head["model"]["softwareSystems"] if s["name"] == "Email Service")
        view(head)["elements"] = [e for e in view(head)["elements"] if e["id"] != email["id"]]
        highlight_diff.highlight(base, head, model_diff.diff_ids(base, head))
        self.assertIn(email["id"], {e["id"] for e in view(head)["elements"]})


class KeepsExistingTest(unittest.TestCase):
    def test_existing_tags_are_kept_and_the_diff_tag_comes_last(self):
        workspace, diff = highlighted("base", "tag-change")
        before, _ = highlight_diff.index(load("tag-change"))
        after, _ = highlight_diff.index(workspace)
        item_id = diff["changed"][0]["id"]
        self.assertEqual(tags(after[item_id][0]), tags(before[item_id][0]) + ["Diff: Changed"])

    def test_existing_styles_are_kept(self):
        original = load("base")["views"]["configuration"]["styles"]["elements"]
        workspace, _ = highlighted("base", "new-element")
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
        workspace = load("views-only")
        diff = model_diff.diff_ids(load("base"), workspace)
        self.assertEqual(highlight_diff.highlight(load("base"), workspace, diff), {})
        self.assertEqual(workspace, load("views-only"))


class CommandLineTest(unittest.TestCase):
    def test_writes_the_highlighted_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            diff_path = pathlib.Path(tmp) / "diff.json"
            output = pathlib.Path(tmp) / "out.json"
            diff_path.write_text(json.dumps(model_diff.diff_ids(load("new-relationship"), load("new-element"))))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = highlight_diff.main(
                    [
                        "highlight-diff",
                        str(FIXTURES / "new-relationship.json"),
                        str(FIXTURES / "new-element.json"),
                        str(diff_path),
                        str(output),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("1 Diff: Added, 1 Diff: Removed", err.getvalue())
            self.assertEqual(sorted(diff_tagged(json.loads(output.read_text())).values()), ["Diff: Added", "Diff: Removed"])

    def test_bad_usage_exits_2(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(highlight_diff.main(["highlight-diff", "a", "b", "c"]), 2)
            self.assertEqual(highlight_diff.main(["highlight-diff", "nope.json", "nope.json", "nope.json", "x"]), 2)


if __name__ == "__main__":
    unittest.main()
