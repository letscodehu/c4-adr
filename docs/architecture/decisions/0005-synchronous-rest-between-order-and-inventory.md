---
status: superseded by ADR-0006
date: 2026-11-20
---

# Synchronous REST between Order and Inventory

* Status: Superseded by [ADR-0006: Introduce an event bus (RabbitMQ)](0006-introduce-an-event-bus-rabbitmq.md)
* Date: 2026-11-20

## Context and Problem Statement

With payments in place (ADR-0004), customers can complete a checkout, but nothing stops them from buying products that are out of stock. Two customers can pay for the last item at the same time, and we find out only when the warehouse cannot ship. Checkout must reserve stock in the `Inventory` module *before* the customer pays, and the customer must get an immediate answer: either the items are reserved, or the cart shows what is no longer available.

So far the model only says that `Order` "reserves stock using" `Inventory` through an in-process call, like every other module-to-module call (ADR-0002). Stock reservation is different from the other calls, though:

* `Inventory` is the module we most expect to extract first: stock levels will be synchronised with the warehouse system, and reservations are the hot spot during sales peaks.
* An in-process call makes it tempting to reserve stock in the same database transaction as the order, which would mean `Order` touching the `inventory` schema and breaking the one-schema-per-module rule (ADR-0003).

How should the `Order` module reserve stock in the `Inventory` module during checkout?

## Considered Options

* Synchronous REST/HTTP call from `Order` to an internal `Inventory` API
* In-process call on `Inventory`'s public Java interface (the current, implicit approach)
* Asynchronous messaging through a message broker (`Order` publishes "order placed", `Inventory` reserves stock and publishes the result)

## Decision Outcome

Chosen option: "Synchronous REST/HTTP call from `Order` to an internal `Inventory` API", because checkout needs an immediate yes/no answer before payment, a request/response call is the simplest way to get it, and an HTTP contract makes the boundary between the two modules explicit and enforceable today, while still running inside the single `Webshop Monolith` we deploy (ADR-0002).

The reservation works as follows:

1. When the customer submits the order, `Order` calls `Inventory`'s internal REST API (`POST /internal/inventory/reservations`, JSON over HTTP) with the order ID and the order lines, and waits for the response.
2. `Inventory` reserves the stock in its own `inventory` schema in one local transaction and answers `201 Created` with a reservation ID, or `409 Conflict` with the lines that are out of stock.
3. Only after a successful reservation does `Order` request the payment from `Payments` (ADR-0004). If the reservation fails, checkout stops and the customer sees which items are unavailable.
4. A reservation expires if the order is not paid within a time limit, so stock reserved for abandoned or failed payments becomes available again.

The API is internal: it is not exposed through the public JSON API that the `Web Application` uses. Its contract (request, response, error codes) is described with OpenAPI and owned by the `Inventory` module. `Order` does not use `Inventory`'s Java classes or its schema; the HTTP contract is the only thing the two modules share. The other module-to-module calls stay in-process, as ADR-0002 decided.

This changes the C4 model as follows:

* **Component view (changed):** the `Order` → `Inventory` relationship becomes explicit: "Reserves stock (synchronous)", technology `REST/HTTP`, instead of an in-process call. It is the only module-to-module relationship in the `Webshop Monolith` that goes over HTTP.
* **Dynamic view `Checkout` (changed):** a new step right after the order is submitted: `Order` reserves stock in `Inventory` with a synchronous REST call, and only then requests the payment from `Payments`. The position of this step (before payment, with checkout waiting for the answer) is the core of this decision.
* **System Context, Container and Deployment views:** unchanged. Both modules still run in the same `Webshop Monolith` container and pods.

### Confirmation

The `REST/HTTP` relationship is visible on the Component view and as a step of the `Checkout` Dynamic view. Changing how `Order` and `Inventory` talk to each other again (for example, going asynchronous or extracting `Inventory` into its own service) is a model change and therefore needs a new ADR (enforced by the `adr-guard` check).

## Pros and Cons of the Options

### Synchronous REST/HTTP call to an internal Inventory API

* Good, because checkout gets an immediate, consistent answer: stock is reserved before the customer pays, so we do not oversell.
* Good, because it is simple: request/response, no new infrastructure, and a familiar technology for the whole team.
* Good, because the HTTP contract is an explicit, versioned boundary: `Order` cannot reach into `Inventory`'s classes or schema, and the contract can be checked with contract tests.
* Good, because extracting `Inventory` into its own service later only changes the URL that `Order` calls, not the contract.
* Bad, because `Order` can only check out when `Inventory` is up and answers in time: the two are coupled at runtime (see Consequences).
* Bad, because it adds serialisation, an HTTP hop and network failure modes (timeouts, retries) to a call that could have been an in-process method call.

### In-process call on Inventory's public interface

* Good, because it is the fastest and simplest option: no network, no partial failures, as ADR-0002 promised for module-to-module calls.
* Good, because it needs no new contract or tooling.
* Bad, because it is also synchronous: `Order` still waits for `Inventory`, so it does not remove the runtime coupling, it only hides it.
* Bad, because it makes it easy to share Java types and a database transaction across the `order` and `inventory` schemas, which erodes the module boundary we most want to keep clean.
* Bad, because extracting `Inventory` later turns every call site into a remote call at once, with failure modes the code was never written for.

### Asynchronous messaging through a message broker

* Good, because `Order` does not wait for `Inventory`: orders can be accepted even when `Inventory` is slow or down, and failures do not cascade.
* Good, because the two modules are decoupled in time and can be scaled and deployed independently.
* Bad, because we would have to run and monitor a message broker, which the team has not operated before.
* Bad, because checkout becomes eventually consistent: the customer would have to wait for, or be notified about, the reservation result, which complicates the checkout flow and the Web Application.
* Bad, because it needs patterns the team does not use yet: a transactional outbox, idempotent consumers and compensating actions.

## Consequences

* Good, because stock is reserved before payment, so customers can no longer pay for items we cannot ship.
* Good, because the `Order` ↔ `Inventory` boundary is an explicit HTTP contract, which keeps the `inventory` schema private to its module (ADR-0003) and prepares `Inventory` for extraction.
* Good, because we get this without new infrastructure: no broker, no new container, no new deployment unit.
* Bad, because **synchronous coupling ties the availability of checkout to the availability of `Inventory`**: if `Inventory` is down, slow or overloaded, customers cannot place orders, even though `Order`, `Payments` and Stripe are healthy. The availability of checkout is at most the availability of `Order` multiplied by that of `Inventory`, and every further synchronous dependency lowers it again.
* Bad, because **a slow `Inventory` causes cascading failures**: while `Order` waits for stock reservations, its request threads and HTTP connections stay busy; during a sales peak they run out, requests queue up and time out, and the whole `Webshop Monolith` (catalogue browsing included, since it shares the same pods) becomes slow or unavailable. Retries from `Order` and from customers clicking "Pay" again make the load on `Inventory` even worse.
* Bad, because there is no distributed transaction between reservation and payment: if the payment fails or the customer abandons checkout, the reservation must be released by expiry, and a call that times out may or may not have reserved stock, so the reservation API must be idempotent (keyed by order ID).
* Neutral, because we accept these risks for now, at current traffic, and mitigate them with short timeouts, a circuit breaker and a limited connection pool on `Order`'s calls to `Inventory`. If checkout availability or peak traffic becomes a problem, we will revisit this decision and consider asynchronous messaging.
