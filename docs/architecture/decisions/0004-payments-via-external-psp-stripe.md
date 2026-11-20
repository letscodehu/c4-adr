# Payments via an external PSP (Stripe)

* Status: Accepted
* Date: 2026-11-20

## Context and Problem Statement

Customers can place orders in the Webshop, but they cannot pay for them yet. We need to accept card payments (and, later, wallets such as Apple Pay and Google Pay) at checkout.

Card payments come with the Payment Card Industry Data Security Standard (PCI DSS). If card numbers pass through or are stored in our systems, the whole Webshop — the Web Application, the Webshop Monolith, the Database and the Kubernetes cluster they run on — is in PCI DSS scope, with the audits and controls that brings. The team is small and has no payment or compliance specialists.

How should the Webshop accept payments, and where should card details be handled?

## Considered Options

* Stripe, as an external payment service provider (PSP), with card details collected by Stripe.js
* Adyen, as an external payment service provider
* A direct integration with an acquiring bank's payment gateway, with card details passing through the Webshop

## Decision Outcome

Chosen option: "Stripe, as an external payment service provider", because card details go from the customer's browser straight to Stripe and never reach the Webshop, which keeps our PCI DSS scope as small as it can be (the self-assessment questionnaire for merchants who fully outsource card handling), while Stripe's API, documentation and test mode let a small team integrate it in days rather than months.

The payment flow is:

1. The `Order` module asks a new `Payments` module to start a payment for the order total.
2. `Payments` creates a *payment intent* at Stripe over its REST API and passes its client secret to the `Web Application`.
3. The `Web Application` confirms the payment with Stripe.js: the card form is hosted by Stripe, and the card details go directly to Stripe.
4. Stripe reports the result to `Payments` with a webhook. `Payments` verifies the webhook signature and marks the order as paid or failed in `Order`. The webhook, not the browser redirect, is the source of truth, because the customer may close the tab before the redirect happens.

All Stripe-specific code lives in the `Payments` module. Other modules see only its public interface ("request payment", "payment succeeded / failed"), as ADR-0002 requires. `Payments` keeps its own records (order, payment intent ID, status) in its own `payments` schema in the Database (ADR-0003); it never stores card details.

This changes the C4 model as follows:

* **System Context view (changed):** a new external software system, `Stripe`, the payment service provider. The `Webshop` uses it to take payments, and Stripe calls back into the Webshop with webhooks.
* **Container view (changed):** the `Web Application` sends card details directly to `Stripe` (Stripe.js, `HTTPS`), the `Webshop Monolith` creates payment intents at Stripe (`HTTPS/REST`), and Stripe notifies the monolith about payment results (webhook over `HTTPS`).
* **Component view (changed):** a new `Payments` module in the `Webshop Monolith`. `Order` requests payments from it, it is the only module that talks to Stripe, and it marks orders as paid or failed in `Order`.
* **Dynamic view (new):** a `Checkout` view shows the payment flow step by step: Customer → Web Application → Order → Payments → Stripe, the card confirmation from the browser to Stripe, Stripe's webhook back to Payments, Payments → Order, and the order confirmation email. The order of these calls (especially that the webhook, not the browser, completes the order) is part of this decision, which is why the Dynamic view is introduced now.
* **Deployment view:** unchanged. Stripe is an external service, not something we deploy.

### Confirmation

Stripe and its three relationships are visible in the System Context, Container and Component views, and the flow in the `Checkout` Dynamic view. A second payment provider, or any other module talking to Stripe directly, is a model change and therefore needs an ADR (enforced by the `adr-guard` check).

## Pros and Cons of the Options

### Stripe, as an external payment service provider

* Good, because card details never touch our systems, so the Webshop stays out of most of PCI DSS scope.
* Good, because it is quick to integrate: a well-documented REST API, client libraries, Stripe.js and a full test mode.
* Good, because it covers cards, wallets, 3-D Secure / Strong Customer Authentication and refunds with one integration.
* Neutral, because its per-transaction fees are typical for a PSP, but higher than what a large merchant can negotiate directly with an acquirer.
* Bad, because it is vendor lock-in: payment intents, webhooks and the Stripe.js card form are Stripe-specific, and saved payment methods cannot simply be moved to another provider.
* Bad, because checkout depends on an external service: if Stripe is unavailable, customers cannot pay.

### Adyen, as an external payment service provider

* Good, because it also keeps card details out of our systems with hosted components.
* Good, because it is strong for large, multi-country merchants with many local payment methods.
* Bad, because onboarding is heavier and aimed at larger merchants; minimum volumes and a longer contract do not fit a new webshop.
* Bad, because the team has no experience with it, while several developers have used Stripe before.

### Direct integration with an acquiring bank's payment gateway

* Good, because transaction fees can be the lowest of the three options.
* Good, because there is no PSP in between, so no PSP lock-in.
* Bad, because card details pass through the Webshop, which puts the Web Application, the Monolith, the Database and the infrastructure in full PCI DSS scope, with yearly audits.
* Bad, because we would build ourselves what a PSP gives us: 3-D Secure, wallets, retries, fraud screening and refunds.

## Consequences

* Good, because our PCI DSS scope stays minimal: we never see or store card numbers.
* Good, because the `Payments` module isolates Stripe behind its own interface, so replacing or adding a provider later touches one module.
* Good, because the webhook-driven flow marks orders as paid even when the customer's browser never comes back from the payment page.
* Bad, because the webhook endpoint is a new public entry point: every webhook must have its signature verified, and handling must be idempotent, because Stripe delivers events at least once and may retry them.
* Bad, because a Stripe outage stops checkout; orders must stay "awaiting payment" and be paid later, rather than being lost.
* Bad, because we accept Stripe lock-in for payment data; moving saved cards to another provider later needs Stripe's data migration process.
