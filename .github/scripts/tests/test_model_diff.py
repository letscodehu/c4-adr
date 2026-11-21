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


def json_against_base(name, base="base"):
    return model_diff.diff_ids(load(base), load(name))


def ids_by_key(workspace):
    info = {}
    model_diff.normalise(workspace, info)
    return info["ids"]


class JsonReportTest(unittest.TestCase):
    def assertReport(self, report, added=(), changed=(), removed=()):
        self.assertEqual(
            {section: [item["key"] for item in items] for section, items in report.items()},
            {"added": list(added), "changed": list(changed), "removed": list(removed)},
        )

    def test_new_element_with_head_id(self):
        report = json_against_base("new-element")
        self.assertReport(report, added=['Container "Webshop/Database"'])
        (item,) = report["added"]
        self.assertEqual(item["kind"], "element")
        self.assertEqual(item["id"], ids_by_key(load("new-element"))['Container "Webshop/Database"'])

    def test_changed_element_with_both_ids_and_its_deployment_instances(self):
        report = json_against_base("description-change")
        self.assertReport(report, changed=['Container "Webshop/API"'])
        (item,) = report["changed"]
        head_ids = ids_by_key(load("description-change"))
        self.assertEqual(item["id"], head_ids['Container "Webshop/API"'])
        self.assertEqual(item["baseId"], ids_by_key(load("base"))['Container "Webshop/API"'])
        self.assertEqual(item["related"], [head_ids['Container Instance "Production/AWS/EC2/[Webshop/API]"']])

    def test_tag_change_is_changed(self):
        self.assertReport(json_against_base("tag-change"), changed=['Software System "Email Service"'])

    def test_removed_element_with_base_id(self):
        report = json_against_base("base", base="new-element")
        self.assertReport(report, removed=['Container "Webshop/Database"'])
        self.assertEqual(report["removed"][0]["id"], ids_by_key(load("new-element"))['Container "Webshop/Database"'])

    def test_new_and_removed_relationship(self):
        key = 'Software System "Email Service" -> Person "Customer" "Delivers emails to"'
        added = json_against_base("new-relationship")
        self.assertReport(added, added=[key])
        self.assertEqual(added["added"][0]["kind"], "relationship")
        self.assertEqual(added["added"][0]["id"], ids_by_key(load("new-relationship"))[key])
        removed = json_against_base("base", base="new-relationship")
        self.assertReport(removed, removed=[key])
        self.assertEqual(removed["removed"][0]["id"], ids_by_key(load("new-relationship"))[key])

    def test_relationship_description_change_is_one_change(self):
        report = json_against_base("relationship-description-change")
        self.assertReport(
            report,
            changed=['Container "Webshop/API" -> Software System "Email Service" "Sends order emails using"'],
        )
        # The text report is unchanged: removed + added.
        self.assertEqual(len(changes_against_base("relationship-description-change")), 2)

    def test_deployment_node(self):
        report = json_against_base("deployment-node")
        self.assertReport(report, added=['Deployment Node "Production/AWS/RDS"'])
        self.assertEqual(report["added"][0]["id"], ids_by_key(load("deployment-node"))['Deployment Node "Production/AWS/RDS"'])

    def test_implied_relationships_are_related_to_the_explicit_one(self):
        # Orders -> Customer implies API -> Customer and Webshop -> Customer.
        workspace = load("implied-relationship")
        report = model_diff.diff_ids(load("base"), workspace)
        self.assertReport(report, added=['Component "Webshop/API/Orders" -> Person "Customer" "Notifies"'])
        (item,) = report["added"]
        implied = set()
        for system in workspace["model"]["softwareSystems"]:
            for element in [system, *system.get("containers", [])]:
                for relationship in element.get("relationships", []):
                    if relationship.get("linkedRelationshipId") == item["id"]:
                        implied.add(relationship["id"])
        self.assertEqual(len(implied), 2)
        self.assertEqual(set(item["related"]), implied)

    def test_implied_relationships_are_followed_transitively(self):
        info = {"links": {"1": None, "2": "1", "3": "2", "4": None}, "instances": {}}
        self.assertEqual(model_diff.related_ids("relationship", "1", info), ["2", "3"])

    def test_views_only_is_empty(self):
        self.assertReport(json_against_base("views-only"))
        self.assertReport(json_against_base("reordered"))


class CommandLineTest(unittest.TestCase):
    def run_main(self, *names, flag=None):
        out = io.StringIO()
        flags = [flag] if flag else []
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = model_diff.main(["model-diff", *flags, *[str(FIXTURES / f"{n}.json") for n in names]])
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

    def test_json_option_prints_json_with_the_same_exit_codes(self):
        code, lines = self.run_main("base", "views-only", flag="--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads("\n".join(lines)), {"added": [], "changed": [], "removed": []})
        code, lines = self.run_main("base", "new-relationship", flag="--json")
        self.assertEqual(code, 1)
        self.assertEqual(len(json.loads("\n".join(lines))["added"]), 1)

    def test_bad_input_exits_2(self):
        code, _ = self.run_main("base", "does-not-exist")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
