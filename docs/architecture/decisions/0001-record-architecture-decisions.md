# Record architecture decisions

* Status: Accepted
* Date: 2026-11-19

## Context and Problem Statement

We need to record the architectural decisions made for the Webshop, so that current and future team members can understand why the system looks the way it does. Decisions that only live in people's heads, chat threads or meeting notes get lost, and the C4 diagrams alone show *what* the architecture is, not *why*.

How do we capture architecture decisions so that they stay close to the architecture model and change together with it?

## Considered Options

* Architecture Decision Records (ADRs) in [MADR](https://adr.github.io/madr/) format, stored in the repository next to the Structurizr DSL model
* A wiki page per decision
* No formal record (rely on pull request descriptions and chat history)

## Decision Outcome

Chosen option: "Architecture Decision Records in MADR format, stored in the repository", because it keeps decisions versioned and reviewed together with the C4 model in the same pull request, and Structurizr can import them into the workspace with the `!adrs` directive.

* ADRs live in `docs/architecture/decisions/` and are named `NNNN-kebab-case-title.md`.
* Each ADR has a Status (Proposed, Accepted, Deprecated, Superseded by ...).
* An ADR is never rewritten once accepted; a new ADR supersedes it instead.

## Consequences

* Good, because every architectural change has a documented reason that can be reviewed in the same pull request as the diagram change.
* Good, because the decisions are published together with the diagrams on the generated site.
* Bad, because writing an ADR adds a small amount of effort to every significant change.
