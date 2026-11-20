"""Unit tests for .github/scripts/model-diff.

Run from the repository root:

    python3 -m unittest discover -s .github/scripts/tests -v

The fixtures are real Structurizr CLI JSON exports of the `.dsl` files next to
them. Every variant is `base.dsl` with one kind of change. To regenerate them:

    cd .github/scripts/tests/fixtures
    for f in *.dsl; do
      docker run --rm -v "$PWD:/usr/local/structurizr" structurizr/cli:2025.11.09 \
        export -workspace "$f" -format json -output .
    done
"""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPT = HERE.parent / "model-diff"

loader = importlib.machinery.SourceFileLoader("model_diff", str(SCRIPT))
spec = importlib.util.spec_from_loader("model_diff", loader)
model_diff = importlib.util.module_from_spec(spec)
loader.exec_module(model_diff)


def load(name):
    with open(FIXTURES / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


def changes_against_base(name):
    return model_diff.diff(load("base"), load(name))


class ModelChangesTest(unittest.TestCase):
    def test_new_element_is_a_model_change(self):
        self.assertEqual(
            changes_against_base("new-element"),
            ['+ added element: Container "Webshop/Database"'],
        )

    def test_new_relationship_is_a_model_change(self):
        self.assertEqual(
            changes_against_base("new-relationship"),
            ['+ added relationship: Software System "Email Service" -> Person "Customer" "Delivers emails to"'],
        )

    def test_description_change_is_a_model_change(self):
        self.assertEqual(
            changes_against_base("description-change"),
            ['~ changed element: Container "Webshop/API": description "Order API." -> "Order and payment API."'],
        )

    def test_tag_change_is_a_model_change(self):
        (change,) = changes_against_base("tag-change")
        self.assertTrue(change.startswith('~ changed element: Software System "Email Service": tags'), change)
        self.assertIn('"Third Party"', change)

    def test_deployment_node_change_is_a_model_change(self):
        self.assertEqual(
            changes_against_base("deployment-node"),
            ['+ added element: Deployment Node "Production/AWS/RDS"'],
        )

    def test_removal_is_reported_as_removed(self):
        self.assertEqual(
            model_diff.diff(load("new-element"), load("base")),
            ['- removed element: Container "Webshop/Database"'],
        )


class NoModelChangeTest(unittest.TestCase):
    def test_identical_workspaces(self):
        self.assertEqual(changes_against_base("base"), [])

    def test_only_ids_order_and_dsl_identifiers_changed(self):
        # Same model declared in a different order: other generated ids,
        # other element/relationship/tag order, renamed DSL identifiers.
        self.assertNotEqual(load("base")["model"], load("reordered")["model"])
        self.assertEqual(changes_against_base("reordered"), [])

    def test_only_views_and_styles_changed(self):
        # New view, different autolayout direction, new style colour.
        self.assertNotEqual(load("base")["views"], load("views-only")["views"])
        self.assertEqual(changes_against_base("views-only"), [])

    def test_documentation_and_decisions_are_ignored(self):
        head = load("base")
        head["documentation"] = {"decisions": [{"id": "1", "title": "Something", "content": "Text"}]}
        head["model"]["softwareSystems"][0]["documentation"] = {"sections": [{"content": "Text"}]}
        self.assertEqual(model_diff.diff(load("base"), head), [])


class CommandLineTest(unittest.TestCase):
    def run_main(self, *names):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = model_diff.main(["model-diff", *[str(FIXTURES / f"{n}.json") for n in names]])
        return code, out.getvalue().splitlines()

    def test_unchanged_exits_0_and_says_so_first(self):
        code, lines = self.run_main("base", "views-only")
        self.assertEqual(code, 0)
        self.assertEqual(lines, ["Model unchanged."])

    def test_changed_exits_1_verdict_first_then_changes(self):
        code, lines = self.run_main("base", "new-relationship")
        self.assertEqual(code, 1)
        self.assertEqual(lines[0], "Model changed: 1 difference(s).")
        self.assertIn("Delivers emails to", lines[1])

    def test_bad_input_exits_2(self):
        code, _ = self.run_main("base", "does-not-exist")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
