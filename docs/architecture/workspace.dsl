workspace "Webshop" "C4 model of an imaginary webshop, evolved through Architecture Decision Records." {

    !identifiers hierarchical

    model {
        customer = person "Customer" "A person who browses the catalogue and places orders."

        webshop = softwareSystem "Webshop" "Lets customers browse products, place orders and track them." {
            webApp = container "Web Application" "Single-page application that customers use in their browser to browse products and place orders." "TypeScript, React" {
                tags "Web Browser"
            }

            monolith = container "Webshop Monolith" "Modular monolith that holds all of the webshop's business logic and exposes it as a JSON API." "Java, Spring Boot" {
                catalog = component "Catalog" "Products, categories, prices and product search." "Module"
                order = component "Order" "Shopping cart, checkout and order lifecycle." "Module"
                inventory = component "Inventory" "Stock levels and stock reservations for orders." "Module"
                customerAccounts = component "Customer Accounts" "Registration, sign-in and customer profiles." "Module"
                payments = component "Payments" "Creates payments at the payment service provider, receives its payment events and tracks the payment status of orders." "Module"
            }

            messageBroker = container "Message Broker" "Delivers domain events between modules: Order publishes OrderPlaced, Inventory publishes the stock reservation result." "RabbitMQ" {
                tags "Queue"
            }

            database = container "Database" "Stores products, orders, payment records, stock levels and customer accounts, one schema per module." "PostgreSQL" {
                tags "Database"
            }
        }

        emailService = softwareSystem "Email Service" "Third-party service that delivers transactional emails." {
            tags "External"
        }

        stripe = softwareSystem "Stripe" "Third-party payment service provider: collects card details and processes card payments." {
            tags "External"
        }

        customer -> webshop.webApp "Browses products and places orders using" "HTTPS"
        webshop.webApp -> webshop.monolith.catalog "Reads products and prices from" "JSON/HTTPS"
        webshop.webApp -> webshop.monolith.order "Places orders using" "JSON/HTTPS"
        webshop.webApp -> webshop.monolith.customerAccounts "Signs customers in and manages profiles using" "JSON/HTTPS"

        webshop.monolith.order -> webshop.monolith.catalog "Gets product details and prices from" "In-process call"
        webshop.monolith.order -> webshop.monolith.customerAccounts "Gets customer and delivery details from" "In-process call"
        webshop.monolith.order -> emailService "Sends order confirmation emails using" "HTTPS"
        emailService -> customer "Delivers emails to"

        webshop.webApp -> stripe "Sends card details directly to, using Stripe.js" "HTTPS"
        webshop.monolith.order -> webshop.monolith.payments "Requests payment for orders using" "In-process call"
        webshop.monolith.payments -> stripe "Creates payment intents using" "HTTPS/REST"
        stripe -> webshop.monolith.payments "Notifies about payment results using" "Webhook, HTTPS"
        webshop.monolith.payments -> webshop.monolith.order "Marks orders as paid or failed in" "In-process call"

        webshop.monolith.order -> webshop.messageBroker "Publishes OrderPlaced" "AMQP"
        webshop.messageBroker -> webshop.monolith.inventory "Consumes OrderPlaced" "AMQP"
        webshop.monolith.inventory -> webshop.messageBroker "Publishes StockReserved / StockReservationFailed" "AMQP"
        webshop.messageBroker -> webshop.monolith.order "Consumes StockReserved / StockReservationFailed" "AMQP"

        webshop.monolith -> webshop.database "Reads from and writes to" "SQL/TCP"

        production = deploymentEnvironment "Production" {
            deploymentNode "Customer's Computer" "The customer's desktop or mobile device." {
                deploymentNode "Web Browser" "" "Chrome, Firefox, Safari or Edge" {
                    containerInstance webshop.webApp
                }
            }

            deploymentNode "Cloud" "Public cloud region that hosts the Webshop." {
                deploymentNode "Kubernetes Cluster" "Managed Kubernetes cluster." "Kubernetes" {
                    deploymentNode "Webshop Monolith Pod" "" "Docker container" 2 {
                        containerInstance webshop.monolith
                    }
                }

                deploymentNode "Managed RabbitMQ" "Managed message broker service: a three-node cluster with quorum queues, TLS and automated upgrades." "RabbitMQ" {
                    containerInstance webshop.messageBroker
                }

                deploymentNode "Managed PostgreSQL" "Managed database service: automated backups, point-in-time recovery, encryption at rest and a standby replica." "PostgreSQL" {
                    containerInstance webshop.database
                }
            }
        }
    }

    views {
        systemContext webshop "SystemContext" {
            include *
            autolayout tb
            description "The System Context view of the Webshop."
        }

        container webshop "Containers" {
            include *
            autolayout lr
            description "The Container view of the Webshop: a single-page application, a modular monolith (ADR-0002), its PostgreSQL database (ADR-0003) and the external Stripe payment service provider (ADR-0004) and the RabbitMQ message broker between modules (ADR-0006)."
        }

        component webshop.monolith "Components" {
            include *
            autolayout lr
            description "The Component view of the Webshop Monolith: its business modules (ADR-0002), including the Payments module that integrates with Stripe (ADR-0004); Order and Inventory communicate only through events on the Message Broker (ADR-0006, supersedes ADR-0005)."
        }

        deployment webshop "Production" "Deployment" {
            include *
            autolayout lr
            description "The Production Deployment view of the Webshop: the monolith on Kubernetes and a managed PostgreSQL database (ADR-0003) and a managed RabbitMQ message broker (ADR-0006)."
        }

        dynamic webshop.monolith "Checkout" {
            customer -> webshop.webApp "Reviews the cart and clicks Pay"
            webshop.webApp -> webshop.monolith.order "Submits the order"
            webshop.monolith.order -> webshop.messageBroker "Publishes OrderPlaced via the transactional outbox (checkout does not wait for Inventory)"
            webshop.monolith.order -> webshop.monolith.payments "Requests payment for the order total"
            webshop.monolith.payments -> stripe "Creates a payment intent with manual capture (its client secret goes back to the Web Application)"
            webshop.webApp -> stripe "Confirms the payment with the card details (the card is authorised, not charged yet)"
            stripe -> webshop.monolith.payments "Sends a signed payment_intent.amount_capturable_updated webhook"
            webshop.monolith.payments -> webshop.monolith.order "Marks the order as payment authorised"
            webshop.messageBroker -> webshop.monolith.inventory "Delivers OrderPlaced; Inventory reserves the stock (idempotent on the order ID)"
            webshop.monolith.inventory -> webshop.messageBroker "Publishes StockReserved"
            webshop.messageBroker -> webshop.monolith.order "Delivers StockReserved"
            webshop.monolith.order -> webshop.monolith.payments "Captures the authorised payment"
            webshop.monolith.order -> emailService "Sends the order confirmation email"
            autolayout tb
            description "The checkout flow: Order publishes OrderPlaced to the Message Broker and continues to payment without waiting for Inventory (ADR-0006, supersedes ADR-0005); the card is authorised through Stripe (ADR-0004), Inventory reserves the stock asynchronously, and the payment is captured once StockReserved arrives."
        }

        styles {
            element "Element" {
                color #ffffff
            }
            element "Person" {
                background #08427b
                shape Person
            }
            element "Software System" {
                background #1168bd
            }
            element "External" {
                background #999999
            }
            element "Container" {
                background #438dd5
            }
            element "Web Browser" {
                shape WebBrowser
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
            element "Database" {
                shape Cylinder
            }
            element "Queue" {
                shape Pipe
            }
            element "Deployment Node" {
                color #444444
            }
        }
    }

}
