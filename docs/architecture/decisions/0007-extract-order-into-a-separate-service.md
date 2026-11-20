---
status: proposed
date: 2026-11-20
---

# Extract Order into a separate service

* Status: Proposed
* Date: 2026-11-20

## Context and Problem Statement

ADR-0002 started the Webshop as a modular monolith and promised to keep "the option to extract a module into its own service later". ADR-0006 replaced the synchronous `Order` → `Inventory` call with events on the `Message Broker`, and noted in its Consequences that the event contracts make the `Order` ↔ `Inventory` boundary loose enough for extraction.

Two things have changed since then:

* **Checkout has a different load profile from the rest of the monolith.** During sales peaks, checkout traffic grows much faster than catalogue browsing. Today we can only scale the whole `Webshop Monolith`, so we add pods (and database connections) for `Catalog`, `Inventory` and `Customer Accounts` that do not need them, just to give `Order` more capacity.
* **A second team is being formed for checkout and payments.** `Order` and `Payments` change far more often than the other modules (new payment methods, promotions, order states from ADR-0006), but every change is released together with the whole monolith, and every monolith release is a checkout release with checkout-level risk.

Should we extract the `Order` module from the `Webshop Monolith` into its own deployable service, and if so, what goes with it?

## Considered Options

* Extract `Order` together with `Payments` into an `Order Service` with its own database
* Extract only `Order`; `Payments` stays in the monolith and is called over HTTP
* Keep `Order` in the monolith, and scale and release it better there (more pods, feature flags, a dedicated checkout deployment of the same artifact)

## Decision Outcome

Proposed option: "Extract `Order` together with `Payments` into an `Order Service` with its own database", because `Order` and `Payments` call each other in-process in both directions during every checkout (request payment, mark as paid, capture). Splitting them would put a network hop, and a new failure mode, into both directions of the payment flow. Together they form one cohesive "checkout and payment" boundary that a single team can own, scale and release.

**This decision is not accepted yet.** The model change below shows what the extraction would look like, so that it can be reviewed. Before it is accepted, we need answers to the open questions in the Consequences (see the review on the pull request).

The proposal works as follows:

1. `Order` and `Payments` move into a new `Order Service` container (Java, Spring Boot), deployed and scaled independently on the same Kubernetes cluster.
2. The `Order Service` gets its own `Order Database` (PostgreSQL, a separate managed instance). The `order` and `payments` schemas, including the transactional outbox from ADR-0006, move there. The monolith's `Database` keeps only the catalogue, stock and customer account schemas.
3. The Web Application calls the `Order Service` directly to place orders.
4. Calls that were in-process from `Order` to `Catalog` (product details and prices) and `Customer Accounts` (customer and delivery details) become JSON/HTTPS calls to the monolith's API.
5. The `Order Service` publishes `OrderPlaced` to, and consumes `StockReserved` / `StockReservationFailed` from, the `Message Broker` exactly as before. The event contracts do not change.
6. The Stripe integration (ADR-0004) moves with `Payments`: the `Order Service` creates payment intents and receives Stripe's webhooks.

This changes the C4 model as follows:

* **Container view (changed):** a new `Order Service` container and a new `Order Database` container. The Web Application places orders using the `Order Service`; the `Order Service` talks to the `Message Broker` (AMQP), to Stripe (REST and webhooks), to the Email Service and to the `Webshop Monolith` (JSON/HTTPS). The monolith's `Database` no longer stores orders and payment records.
* **Component view `Components` (changed):** the `Webshop Monolith` keeps `Catalog`, `Inventory` and `Customer Accounts`. `Order` and `Payments` are gone from it.
* **Component view `OrderServiceComponents` (new):** the `Order` and `Payments` modules inside the `Order Service`, with Stripe, the `Message Broker`, the Email Service and the monolith's `Catalog` and `Customer Accounts` modules.
* **Deployment view (changed):** a new `Order Service Pod` (2 replicas) on the Kubernetes cluster, and a new `Managed PostgreSQL for Orders` deployment node running the `Order Database`.
* **Dynamic view `Checkout` (changed):** the flow is now scoped to the `Order Service`; the stock reservation happens in the `Webshop Monolith`, reached only through the `Message Broker`.
* **System Context view:** unchanged. The extraction is internal to the Webshop.

### Confirmation

If accepted, the `Order Service` and `Order Database` containers are visible on the Container and Deployment views, and the `Webshop Monolith` component view no longer contains `Order` or `Payments`. Any further relationship between the `Order Service` and the monolith is a model change and needs an ADR (enforced by the `adr-guard` check).

## Pros and Cons of the Options

### Extract `Order` together with `Payments` into an `Order Service`

* Good, because checkout can be scaled on its own during peaks, without scaling the rest of the monolith.
* Good, because the checkout team can release `Order` and `Payments` independently, and a monolith release no longer risks checkout.
* Good, because the payment flow stays in-process: no new network hop between `Order` and `Payments`.
* Good, because the `Order` ↔ `Inventory` boundary is already event-based (ADR-0006), so that part needs no change.
* Bad, because `Order` now calls `Catalog` and `Customer Accounts` over the network: checkout depends on the availability of the monolith's API again (see Consequences).
* Bad, because we operate a second service and a second database (deployments, dashboards, alerts, backups, on-call).
* Bad, because service-to-service calls cross a new trust boundary and need authentication.

### Extract only `Order`

* Good, because the new service is smaller.
* Bad, because `Order` and `Payments` call each other in both directions on every checkout, so the payment flow gets two network hops and partial failures between them (paid, but not marked as paid).
* Bad, because ownership is split: the checkout team would still depend on monolith releases for every payment change.

### Keep `Order` in the monolith and scale and release it better there

* Good, because it adds no new service, database or network calls.
* Good, because a dedicated checkout deployment of the same artifact can scale checkout traffic separately.
* Bad, because releases stay coupled: every change still ships the whole monolith.
* Bad, because the shared database stays shared, so a heavy checkout load still competes with the other modules for connections.

## Consequences

* Good, because checkout can be scaled and released independently of the rest of the Webshop.
* Good, because the checkout team owns one service, one database and one Stripe integration end to end.
* Bad, because **checkout depends on the monolith's API for prices and customer details** over the network. If the monolith is down or slow, checkout fails. Open question: should `Order` keep a local copy of prices and delivery details (from events, or a snapshot in the cart) instead of calling the monolith on every checkout?
* Bad, because we run a second service and a second managed PostgreSQL instance: more cost, more dashboards, alerts and runbooks. Open question: is the extra operating cost justified by the measured peak load, or does a dedicated checkout deployment of the monolith solve it more cheaply?
* Bad, because **calls between the `Order Service` and the monolith cross the network** and need service-to-service authentication and authorisation (for example mTLS or signed service tokens), so that only the `Order Service` can read customer delivery details. Open question: which mechanism do we use?
* Neutral, because orders and payment records move to a new database; this needs a one-off data migration and a cut-over plan.
