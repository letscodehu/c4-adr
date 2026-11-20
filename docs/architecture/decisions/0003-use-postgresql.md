# Use PostgreSQL

* Status: Accepted
* Date: 2026-11-20

## Context and Problem Statement

The Webshop Monolith (ADR-0002) needs to store its data somewhere: products and prices, orders, stock levels and customer accounts. Most of this data is relational and must stay consistent: placing an order has to reserve stock and create the order in one step, or not at all. At the same time, product attributes vary by category, so the catalogue needs some schema flexibility.

The team is small and has no dedicated database administrator, so we also want to spend as little time as possible on running the database itself.

Which database should the Webshop use, and how should it run in production?

## Considered Options

* PostgreSQL, as a managed cloud service
* MySQL, as a managed cloud service
* MongoDB (document database)

## Decision Outcome

Chosen option: "PostgreSQL, as a managed cloud service", because it gives us ACID transactions across orders and stock, a mature relational model for our mostly relational data, and `jsonb` columns for the category-specific product attributes, while the managed service takes backups, patching and failover off the team's plate.

The monolith uses one database, with one schema per module (`catalog`, `order`, `inventory`, `customer_accounts`). A module reads and writes only its own schema; it reaches other modules' data through their public interfaces, as ADR-0002 requires. This keeps the option to give an extracted service its own database later.

This changes the C4 model as follows:

* **Container view (changed):** the `Webshop` software system gets a new `Database` container (PostgreSQL, drawn as a cylinder). The `Webshop Monolith` reads from and writes to it over `SQL/TCP`.
* **Deployment view (new):** a `Production` deployment environment shows where the system runs. The `Web Application` runs in the customer's web browser. The `Webshop Monolith` runs as pods in a managed Kubernetes cluster, and the `Database` runs on a managed PostgreSQL service, both in the same cloud region. Choosing a managed service is part of this decision, which is why the Deployment view is introduced now.
* **System Context and Component views:** unchanged. The database is internal to the Webshop, and the relationship is drawn at container level, so it does not appear on the Component view.

### Confirmation

The database and its single client are visible in the Container view, and the managed service in the Deployment view. A new client of the database, or a second data store, is a model change and therefore needs an ADR (enforced by the `adr-guard` check).

## Pros and Cons of the Options

### PostgreSQL, as a managed cloud service

* Good, because ACID transactions keep orders and stock reservations consistent.
* Good, because `jsonb` covers flexible product attributes without a second database.
* Good, because it is open source, widely known, and offered as a managed service by every major cloud provider, so we are not locked into one vendor.
* Good, because the managed service handles backups, point-in-time recovery, patching, encryption at rest and failover to a standby replica.
* Bad, because a managed service costs more than a self-hosted instance and gives less control over tuning and versions.
* Bad, because a single relational database is scaled vertically first; read replicas or partitioning come with extra work.

### MySQL, as a managed cloud service

* Good, because it is also relational, transactional, widely known and available as a managed service.
* Neutral, because for our current needs it would work about as well as PostgreSQL.
* Bad, because its JSON support and indexing on JSON fields are less capable than PostgreSQL's `jsonb`, which we want for the catalogue.

### MongoDB (document database)

* Good, because a flexible document model fits product attributes well.
* Good, because it scales horizontally by sharding.
* Bad, because most of our data is relational (orders reference customers, products and stock), so we would model joins and consistency in application code.
* Bad, because multi-document transactions are possible but are not the default way to work with it, which makes the order + stock consistency harder to get right.
* Bad, because the team has less experience operating and modelling data in it.

## Consequences

* Good, because the order and stock data stays consistent with standard database transactions.
* Good, because the team does not operate the database server; backups and failover are the provider's job.
* Good, because one schema per module keeps the module boundaries of ADR-0002 visible in the data as well.
* Bad, because the database is a single shared dependency: if it is unavailable, the whole Webshop is unavailable.
* Bad, because cross-schema queries are tempting in a single database; we have to keep modules from reading each other's tables, by convention and review.
