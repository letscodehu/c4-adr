# Notify customers about order status changes

* Status: Proposed
* Date: 2026-11-19

## Context and Problem Statement

Demo ADR for the adr-guard check (issue #3). Customers want to know when their order changes status. How does the Webshop tell them?

## Considered Options

* The Webshop sends order status updates to the customer
* Customers check the order page themselves

## Decision Outcome

Chosen option: "The Webshop sends order status updates to the customer".

## Consequences

* Good, because customers do not need to poll the order page.
