# Start with a modular monolith

* Status: Accepted
* Date: 2026-11-20

## Context and Problem Statement

The Webshop is a new product built by a single, small team. The business domain is still being discovered: we expect the boundaries between catalogue, ordering, stock and customer data to move as we learn. At the same time, we do not want to end up with a "big ball of mud" that is impossible to split later if parts of the system need to scale or be owned by separate teams.

How should we structure and deploy the Webshop backend for its first releases?

## Considered Options

* Modular monolith: one deployable backend, split internally into business modules with explicit boundaries
* Microservices from day one: one service per business capability
* Traditional layered monolith without explicit module boundaries

## Decision Outcome

Chosen option: "Modular monolith", because it gives us one simple unit to build, deploy and operate while the team is small and the domain is still moving, and its explicit module boundaries keep the option to extract a module into its own service later.

This changes the C4 model as follows:

* **Container view (new):** the `Webshop` software system now has two containers: a `Web Application` (single-page application in the customer's browser) and the `Webshop Monolith` (the backend, one deployable unit). The Customer uses the Web Application, which calls the Monolith's JSON API.
* **Component view (new):** the `Webshop Monolith` is split into four business modules: `Catalog`, `Order`, `Inventory` and `Customer Accounts`. Modules talk to each other only through in-process calls on each other's public interfaces. `Order` is the module that sends order confirmation emails through the external Email Service.
* **System Context view:** unchanged in meaning; the existing relationships are now derived from the container- and component-level relationships.

The database is deliberately not part of this decision; it is decided in a separate ADR.

### Confirmation

Module boundaries are visible in the Component view and reviewed in pull requests: any new dependency between modules is a model change and therefore needs an ADR (enforced by the `adr-guard` check).

## Pros and Cons of the Options

### Modular monolith

* Good, because there is one build, one deployment and one runtime to monitor.
* Good, because calls between modules are in-process: no network latency, partial failures or distributed transactions.
* Good, because refactoring across module boundaries is cheap while the domain is still changing.
* Good, because clear module boundaries make a later extraction into a service possible (see "Consequences").
* Bad, because all modules scale and are released together.

### Microservices from day one

* Good, because each capability can be scaled, deployed and owned independently.
* Bad, because it adds service discovery, network failures, distributed data and observability work before we know the right boundaries.
* Bad, because a wrong service boundary is expensive to move once it is a network API.

### Traditional layered monolith

* Good, because it is the simplest to start with.
* Bad, because without explicit module boundaries, dependencies grow in every direction, which makes later splitting very hard.

## Consequences

* Good, because the team can ship the first releases quickly with minimal operational overhead.
* Good, because the module structure gives a clear map of ownership and dependencies in the Component view.
* Bad, because module boundaries are only enforced by convention and review, not by the network; we have to keep them clean deliberately.
* Bad, because a fault or a resource-hungry module can affect the whole Webshop backend, since everything runs in one process.
