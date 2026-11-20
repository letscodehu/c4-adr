# C4 + ADR demo

A demo repository showing how the [C4 model](https://c4model.com/) and
[Architecture Decision Records](https://adr.github.io/) (ADRs) work together in one
repository.

The story is told through an imaginary **webshop**. Every architectural decision is
recorded as an ADR, and the C4 model (written in [Structurizr DSL](https://docs.structurizr.com/dsl))
changes in the same pull request as the decision that justifies it.

Three ideas run through the whole repository:

1. ADRs and C4 diagrams change together, in one pull request.
2. A decision drives a diagram change: the ADR explains *why* the C4 model changed.
3. Docs as code: the architecture lives next to the code, reviewed, versioned and enforced by CI.

There is no application code here, only documentation and CI.

## Published site

The model and the decisions are published to GitHub Pages:
**<https://letscodehu.github.io/c4-adr/>**

Browse the diagrams there, and open the **Decisions** menu to read the ADRs.

## Repository structure

```
docs/
  architecture/
    workspace.dsl            # Structurizr DSL workspace (C4 model + views)
    decisions/               # ADRs in MADR format, imported via !adrs
      0001-record-architecture-decisions.md
.github/
  workflows/
    validate.yml             # validates the DSL on every pull request and push to main
    pages.yml                # builds the Structurizr site and deploys it to GitHub Pages
    adr-guard.yml            # fails a pull request that changes the model without an ADR, or vice versa
    diagrams.yml             # renders the views and comments Before / After images on every pull request
  scripts/
    export-workspace.sh      # exports the workspace of any git revision with the Structurizr CLI
    model-diff               # compares the C4 model of two JSON exports
    render-views             # renders every view of a git revision to PNG and SVG
    publish-previews         # pushes rendered images to the orphan diagram-previews branch
    preview-comment          # builds the Before / After diagram preview comment
    tests/                   # unit tests and fixtures for model-diff and preview-comment
```

Rendered images are never committed to `main`. They are produced by CI and published to
GitHub Pages, to workflow artifacts and to the orphan `diagram-previews` branch (see
[diagrams](#diagrams)).

## How the CI works

| Workflow | Runs on | What it does |
| --- | --- | --- |
| `validate` | every pull request, push to `main` | Validates `workspace.dsl` with the Structurizr CLI. |
| `pages` | push to `main` | Builds the Structurizr site and deploys it to GitHub Pages. |
| `adr-guard` | every pull request | Checks that model changes and ADR changes go together (see below), and runs the unit tests of the CI scripts. |
| `diagrams` | every pull request | Renders every view before and after the pull request, and keeps one bot comment with Before / After images up to date (see below). |

### adr-guard

The rule: **the C4 model changes if and only if the pull request adds or modifies an ADR**
in `docs/architecture/decisions/`.

| Model changed? | ADR added or modified? | Result |
| --- | --- | --- |
| yes | yes | ✅ pass |
| no | no | ✅ pass (e.g. README or CI changes) |
| yes | no | ❌ fail: a model change needs a decision |
| no | yes | ❌ fail: a decision without a model change |

How it works: the workflow exports the workspace of the base revision (the merge base
with the target branch, checked out into a temporary `git worktree`) and of the pull
request to JSON with the Structurizr CLI, and `.github/scripts/model-diff` compares the
`model` part of the two exports. ADR changes are detected with
`git diff --name-only --diff-filter=AM origin/<base>...HEAD -- docs/architecture/decisions/`.
Only the presence of an added or modified ADR file is checked, not its content.

**Counts as a model change:**

- an added or removed element: person, software system, container, component,
  deployment node, infrastructure node, software system or container instance;
- an added or removed relationship;
- a changed name, description, technology, tag, URL, group, property or perspective of
  an element or relationship (for example a new tag on a deployment node).

**Does not count as a model change:**

- anything in `views`: new or removed views, `include`/`exclude`, `autolayout`,
  descriptions of views;
- `styles` (colours, shapes) and other `configuration`;
- the ADRs and documentation themselves;
- generated ids and the order in which elements, relationships or tags are declared;
- renaming a DSL identifier (the variable name, stored by Structurizr as the
  `structurizr.dsl.identifier` property), because it does not change the architecture;
- implied relationships that Structurizr derives from an explicit one (the explicit
  relationship is compared instead).

**If adr-guard is red**, open the failed run: the first line of the log and the job
summary say which case you hit, list every model difference (`+` added, `-` removed,
`~` changed) and the ADRs touched, and say what to do:

- *Model changed, no ADR:* add an ADR (`docs/architecture/decisions/NNNN-kebab-title.md`,
  MADR format) that explains why the model changes, or update the ADR this change
  implements. If the model change was not intended, revert it.
- *ADR changed, model did not:* add the model change the decision drives to
  `workspace.dsl` in the same pull request, or move the ADR edit into the pull request
  that changes the model.

Run the `model-diff` tests and the comparison locally (Docker and Python 3 needed):

```sh
python3 -m unittest discover -s .github/scripts/tests -v

.github/scripts/export-workspace.sh origin/main json build/base
.github/scripts/export-workspace.sh --working-tree json build/head
.github/scripts/model-diff build/base/workspace.json build/head/workspace.json
```

### diagrams

Every pull request gets **one** bot comment, *Diagram preview*, that shows what the
pull request does to the diagrams. Every push to the pull request updates the same
comment with the new images instead of adding another one.

- A view that **changed** gets a two-column table: **Before** (the base branch) and
  **After** (the pull request).
- A **new view** says "new view" in the Before column, a **removed** view says
  "removed" in the After column.
- Unchanged views are collapsed in a `<details>` block at the end.
- If nothing changed, the comment says **No diagram changes**.

How it works:

1. `.github/scripts/render-views` renders every view of the base revision (the merge
   base with the target branch, the same one adr-guard uses) and of the pull request.
   It exports the workspace with `export-workspace.sh` as `plantuml/structurizr`
   (this flavour keeps the colours and shapes of the workspace `styles`) and renders
   each view to PNG and SVG with the `plantuml/plantuml` Docker image.
2. A view counts as changed when its PlantUML source differs, so anything drawn on it
   counts: elements, relationships, descriptions, styles, layout, title.
3. All PNG, SVG and PlantUML files are uploaded as the
   `diagrams-pr-<number>-<short-sha>` **workflow artifact**: open the run from the
   comment's footer link (or the PR's Checks tab) to download them.
4. `.github/scripts/publish-previews` pushes the images to the **orphan
   `diagram-previews` branch**, to `pr-<number>/<short-sha>/base/<view-key>.png` and
   `pr-<number>/<short-sha>/head/<view-key>.png` (and `.svg`). If several pull requests
   push at the same time, a rejected push is rebuilt on the new tip of the branch and
   retried. The workflow creates the branch on its first run.
5. `.github/scripts/preview-comment` builds the comment, with images linked from
   `https://raw.githubusercontent.com/letscodehu/c4-adr/diagram-previews/...`. The
   workflow finds its earlier comment by the hidden `<!-- diagram-preview -->` marker
   and edits it, or creates it on the first run.

**Why no images on `main`?** Generated files in the main history only add noise: every
model change would come with binary diffs, and the images could drift from the DSL
they were rendered from. The DSL is the source of truth; images are build output. The
comment still needs a stable URL for each image, and a workflow artifact cannot be
embedded in a comment, so the images live on `diagram-previews`, a branch that shares
no history with `main` and is never merged. Each push gets its own `<short-sha>`
folder, so older comment versions keep their images.

Not covered (yet): pull requests from forks (their token cannot push or comment, so the
job is skipped) and cleaning up `diagram-previews` after pull requests are closed.

Render the views and build the comment locally (Docker and Python 3 needed):

```sh
python3 -m unittest discover -s .github/scripts/tests -v

.github/scripts/render-views origin/main build/diagrams/base
.github/scripts/render-views --working-tree build/diagrams/head
.github/scripts/preview-comment build/diagrams/base build/diagrams/head base head
```

## Walkthrough

_Coming soon._ This section will guide you through the pull requests in order, one
architecture decision at a time.

## Running locally

You only need Docker. Run the commands from the repository root.

Validate the DSL:

```sh
docker run --rm -v "$PWD:/usr/local/structurizr" structurizr/cli:2025.11.09 \
  validate -workspace docs/architecture/workspace.dsl
```

Generate the static site into `build/site` (git-ignored):

```sh
docker run --rm -v "$PWD:/var/model" ghcr.io/avisi-cloud/structurizr-site-generatr:1.6.0 \
  generate-site --workspace-file docs/architecture/workspace.dsl \
  --default-branch main --output-dir build/site
```

Then open `build/site/index.html` in a browser, or serve it with live reload:

```sh
docker run --rm -p 8080:8080 -v "$PWD:/var/model" ghcr.io/avisi-cloud/structurizr-site-generatr:1.6.0 \
  serve --workspace-file docs/architecture/workspace.dsl
```

and browse to <http://localhost:8080>.

## License

[MIT](LICENSE.md)
