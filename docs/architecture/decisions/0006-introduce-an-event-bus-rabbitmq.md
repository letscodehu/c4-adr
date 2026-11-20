---
status: accepted
date: 2026-11-20
---

# Introduce an event bus (RabbitMQ)

* Status: Accepted
* Supersedes: [ADR-0005: Synchronous REST between Order and Inventory](0005-synchronous-rest-between-order-and-inventory.md)
* Date: 2026-11-20

## Context and Problem Statement

ADR-0005 decided that `Order` reserves stock by calling an internal `Inventory` REST API synchronously, and waits for the answer before checkout continues. Its Consequences named the price up front:

> **synchronous coupling ties the availability of checkout to the availability of `Inventory`**: if `Inventory` is down, slow or overloaded, customers cannot place orders, even though `Order`, `Payments` and Stripe are healthy.

and that "a slow `Inventory` causes cascading failures" across the whole `Webshop Monolith`. ADR-0005 accepted these risks "for now, at current traffic", and promised to revisit the decision "if checkout availability or peak traffic becomes a problem".

It has become a problem. During the last sales peak, `Inventory` slowed down while it synchronised stock levels with the warehouse system. `Order`'s reservation calls hit their timeouts, the circuit breaker opened, and checkout rejected orders for minutes even though `Order`, `Payments` and Stripe were healthy. Waiting request threads also made catalogue browsing slow, because all modules share the same pods. Customer retries ("Pay" clicked again) made the load on `Inventory` worse. Timeouts and a circuit breaker limit the damage, but they cannot remove it: as long as checkout waits for `Inventory`, a slow `Inventory` means lost orders.

How should `Order` and `Inventory` communicate during checkout so that taking an order does not depend on `Inventory` being available at that moment?

## Considered Options

* Asynchronous events through a message broker (RabbitMQ): `Order` publishes `OrderPlaced`, `Inventory` consumes it and reserves the stock
* Keep the synchronous REST call (ADR-0005) and harden it further: more `Inventory` replicas, bulkheads, longer timeouts
* Asynchronous events through a log-based event streaming platform (Apache Kafka)

## Decision Outcome

Chosen option: "Asynchronous events through a message broker (RabbitMQ)", because it is the only option that removes `Inventory` from the critical path of taking an order: `Order` accepts the order and publishes an event without waiting, and `Inventory` catches up when it is healthy again. RabbitMQ gives us exactly what this use case needs (durable queues, acknowledgements, retries and dead-lettering) with less to operate than Kafka, and it is available as a managed service from our cloud provider.

This decision **supersedes [ADR-0005](0005-synchronous-rest-between-order-and-inventory.md)**: the synchronous `POST /internal/inventory/reservations` call is removed.

The new checkout flow works as follows:

1. When the customer submits the order, `Order` stores the order as `Placed` and, in the same local transaction, writes an `OrderPlaced` event (order ID and order lines) into an outbox table in the `order` schema (transactional outbox). A relay publishes outbox entries to the `Message Broker` over AMQP. Checkout does not wait for `Inventory`.
2. Checkout continues straight to payment (ADR-0004). `Payments` creates the Stripe payment intent with manual capture: the card is authorised, but not charged yet.
3. `Inventory` consumes `OrderPlaced` from its own durable queue, reserves the stock in its own `inventory` schema in one local transaction, and publishes `StockReserved` or `StockReservationFailed`. The consumer is idempotent: it is keyed by order ID, so a redelivered event never reserves the same stock twice.
4. `Order` consumes the result. On `StockReserved` the payment is captured and the order confirmation email is sent. On `StockReservationFailed` the order is cancelled, the payment authorisation is released and the customer is emailed about the unavailable items.
5. Messages that keep failing go to a dead-letter queue, which is monitored and alerted on.

Both modules still run in the single `Webshop Monolith` (ADR-0002) and keep their own schemas (ADR-0003). The event contracts (`OrderPlaced`, `StockReserved`, `StockReservationFailed`) are versioned and owned by the publishing module; they are now the only thing `Order` and `Inventory` share. The other module-to-module calls stay in-process.

This changes the C4 model as follows:

* **Container view (changed):** a new `Message Broker` container (RabbitMQ, shown as a pipe). The `Webshop Monolith` publishes events to it and consumes events from it over AMQP.
* **Component view (changed):** the synchronous `Order` → `Inventory` relationship ("Reserves stock (synchronous)", `REST/HTTP`) is removed. Instead, `Order` publishes `OrderPlaced` to the `Message Broker`, which delivers it to `Inventory`; `Inventory` publishes the reservation result to the `Message Broker`, which delivers it to `Order`. There is no direct relationship between `Order` and `Inventory` any more.
* **Deployment view (changed):** a new `Managed RabbitMQ` deployment node in the cloud region, running the `Message Broker`, next to `Managed PostgreSQL`.
* **Dynamic view `Checkout` (changed):** the synchronous "reserves stock" step is replaced by `Order` publishing `OrderPlaced`, and checkout continues to payment without waiting. The reservation happens in parallel, through the broker, and its result decides whether the payment is captured.
* **System Context view:** unchanged. The broker is an internal part of the Webshop.

### Confirmation

The `Message Broker` container is visible on the Container, Component and Deployment views, and the `Checkout` Dynamic view shows the events instead of the synchronous call. There is no `Order` → `Inventory` relationship in the model; adding a direct one back is a model change and needs a new ADR (enforced by the `adr-guard` check).

## Pros and Cons of the Options

### Asynchronous events through a message broker (RabbitMQ)

* Good, because checkout no longer depends on `Inventory` being up or fast: orders are accepted during an `Inventory` outage and reserved when it recovers.
* Good, because a slow `Inventory` cannot cascade into `Order`'s request threads, so catalogue browsing and checkout stay responsive during peaks.
* Good, because the queue absorbs peak load: `Inventory` processes reservations at its own pace.
* Good, because RabbitMQ is mature, well understood, and available as a managed service.
* Bad, because checkout becomes eventually consistent: a customer can pay for an item that turns out to be out of stock, and we must cancel the order and release the payment authorisation afterwards.
* Bad, because we have to run and monitor a new piece of infrastructure (see Consequences).
* Bad, because it needs patterns the team does not use yet: a transactional outbox, idempotent consumers and dead-letter handling.

### Keep the synchronous REST call and harden it further

* Good, because it needs no new infrastructure and no new patterns.
* Good, because the customer still gets an immediate, consistent answer.
* Bad, because it does not remove the coupling, it only makes it more expensive: checkout is still only as available as `Inventory`.
* Bad, because more replicas and longer timeouts make the cascading-failure scenario slower, not impossible.

### Asynchronous events through Apache Kafka

* Good, because it gives the same decoupling, plus event replay and very high throughput.
* Bad, because it is much more to operate (partitions, consumer groups, retention), for a throughput we do not need.
* Bad, because per-message retries and dead-lettering, which this use case needs, are built into RabbitMQ but have to be built by hand on Kafka.

## Consequences

* Good, because taking an order no longer depends on the availability of `Inventory`; the availability of checkout is no longer the product of the two modules' availability.
* Good, because the event contracts make the `Order` ↔ `Inventory` boundary even looser than the HTTP contract did, which still prepares `Inventory` for extraction.
* Bad, because **checkout is eventually consistent**: a small share of orders will be paid (authorised) and then cancelled for lack of stock. We accept this; the customer is emailed, and the authorisation is released, so they are never charged.
* Bad, because the `Message Broker` is a new critical component: it needs high availability (a three-node cluster with quorum queues), monitoring of queue depth, consumer lag and the dead-letter queue, and on-call runbooks. If the broker is down, the outbox keeps accepting orders, but reservations wait until it is back.
* Bad, because the broker is a new trust boundary: it needs its own credentials per module, TLS, and permissions that restrict who can publish and consume each event.
* Neutral, because the order lifecycle gets new states (`Placed`, `Reserved`, `Cancelled`), which the Web Application has to show to the customer.
