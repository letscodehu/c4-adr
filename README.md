# C4 + ADR demo

A demo repository showing how the [C4 model](https://c4model.com/) and
[Architecture Decision Records](https://adr.github.io/) (ADRs) work together in one
repository. It accompanies a lead magnet document that walks through the same flow.

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
```

Rendered images are never committed. They are produced by CI and published to GitHub Pages.

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
