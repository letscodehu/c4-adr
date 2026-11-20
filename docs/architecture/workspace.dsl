workspace "Webshop" "C4 model of an imaginary webshop, evolved through Architecture Decision Records." {

    !identifiers hierarchical
    !adrs decisions madr

    model {
        customer = person "Customer" "A person who browses the catalogue and places orders."

        webshop = softwareSystem "Webshop" "Lets customers browse products, place orders and track them." {
            webApp = container "Web Application" "Single-page application that customers use in their browser to browse products and place orders." "TypeScript, React" {
                tags "Web Browser"
            }

            monolith = container "Webshop Monolith" "Modular monolith that holds the catalogue, stock and customer account logic and exposes it as a JSON API." "Java, Spring Boot" {
                catalog = component "Catalog" "Products, categories, prices and product search." "Module"
                inventory = component "Inventory" "Stock levels and stock reservations for orders." "Module"
                customerAccounts = component "Customer Accounts" "Registration, sign-in and customer profiles." "Module"
            }

            orderService = container "Order Service" "Separately deployed service that owns the shopping cart, checkout, the order lifecycle and the payment of orders, and exposes them as a JSON API." "Java, Spring Boot" {
                order = component "Order" "Shopping cart, checkout and order lifecycle." "Module"
                payments = component "Payments" "Creates payments at the payment service provider, receives its payment events and tracks the payment status of orders." "Module"
            }

            messageBroker = container "Message Broker" "Delivers domain events between the Order Service and the Webshop Monolith: Order publishes OrderPlaced, Inventory publishes the stock reservation result." "RabbitMQ" {
                tags "Queue"
            }

            database = container "Database" "Stores products, stock levels and customer accounts, one schema per module." "PostgreSQL" {
                tags "Database"
            }

            orderDatabase = container "Order Database" "Stores orders, payment records and the event outbox of the Order Service." "PostgreSQL" {
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
        webshop.webApp -> webshop.orderService.order "Places orders using" "JSON/HTTPS"
        webshop.webApp -> webshop.monolith.customerAccounts "Signs customers in and manages profiles using" "JSON/HTTPS"

        webshop.orderService.order -> webshop.monolith.catalog "Gets product details and prices from" "JSON/HTTPS"
        webshop.orderService.order -> webshop.monolith.customerAccounts "Gets customer and delivery details from" "JSON/HTTPS"
        webshop.orderService.order -> emailService "Sends order confirmation emails using" "HTTPS"
        emailService -> customer "Delivers emails to"

        webshop.webApp -> stripe "Sends card details directly to, using Stripe.js" "HTTPS"
        webshop.orderService.order -> webshop.orderService.payments "Requests payment for orders using" "In-process call"
        webshop.orderService.payments -> stripe "Creates payment intents using" "HTTPS/REST"
        stripe -> webshop.orderService.payments "Notifies about payment results using" "Webhook, HTTPS"
        webshop.orderService.payments -> webshop.orderService.order "Marks orders as paid or failed in" "In-process call"

        webshop.orderService.order -> webshop.messageBroker "Publishes OrderPlaced" "AMQP"
        webshop.messageBroker -> webshop.monolith.inventory "Consumes OrderPlaced" "AMQP"
        webshop.monolith.inventory -> webshop.messageBroker "Publishes StockReserved / StockReservationFailed" "AMQP"
        webshop.messageBroker -> webshop.orderService.order "Consumes StockReserved / StockReservationFailed" "AMQP"

        webshop.monolith -> webshop.database "Reads from and writes to" "SQL/TCP"
        webshop.orderService -> webshop.orderDatabase "Reads from and writes to" "SQL/TCP"

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

                    deploymentNode "Order Service Pod" "" "Docker container" 2 {
                        containerInstance webshop.orderService
                    }
                }

                deploymentNode "Managed RabbitMQ" "Managed message broker service: a three-node cluster with quorum queues, TLS and automated upgrades." "RabbitMQ" {
                    containerInstance webshop.messageBroker
                }

                deploymentNode "Managed PostgreSQL" "Managed database service: automated backups, point-in-time recovery, encryption at rest and a standby replica." "PostgreSQL" {
                    containerInstance webshop.database
                }

                deploymentNode "Managed PostgreSQL for Orders" "Separate managed database instance of the Order Service, with the same backup, encryption and standby replica setup." "PostgreSQL" {
                    containerInstance webshop.orderDatabase
                }
            }
        }
    }

    views {
        systemContext webshop "SystemContext" {
            include *
            autolayout lr
            description "The System Context view of the Webshop."
        }

        container webshop "Containers" {
            include *
            autolayout lr
            description "The Container view of the Webshop: a single-page application, a modular monolith (ADR-0002) and its PostgreSQL database (ADR-0003), the RabbitMQ message broker (ADR-0006), and the Order Service extracted from the monolith with its own Order Database, which integrates with Stripe (ADR-0004, ADR-0007)."
        }

        component webshop.monolith "Components" {
            include *
            autolayout lr
            description "The Component view of the Webshop Monolith: its remaining business modules (ADR-0002); Order and Payments moved to the Order Service (ADR-0007), which calls Catalog and Customer Accounts over JSON/HTTPS and talks to Inventory only through events on the Message Broker (ADR-0006)."
        }

        component webshop.orderService "OrderServiceComponents" {
            include *
            autolayout lr
            description "The Component view of the Order Service (ADR-0007): the Order and Payments modules, extracted from the monolith together, with Stripe (ADR-0004), the Message Broker (ADR-0006) and their own Order Database."
        }

        deployment webshop "Production" "Deployment" {
            include *
            autolayout lr
            description "The Production Deployment view of the Webshop: the monolith and the Order Service (ADR-0007) on Kubernetes, a managed PostgreSQL database each (ADR-0003, ADR-0007) and a managed RabbitMQ message broker (ADR-0006)."
        }

        dynamic webshop.orderService "Checkout" {
            customer -> webshop.webApp "Reviews the cart and clicks Pay"
            webshop.webApp -> webshop.orderService.order "Submits the order"
            webshop.orderService.order -> webshop.messageBroker "Publishes OrderPlaced via the transactional outbox (checkout does not wait for Inventory)"
            webshop.orderService.order -> webshop.orderService.payments "Requests payment for the order total"
            webshop.orderService.payments -> stripe "Creates a payment intent with manual capture (its client secret goes back to the Web Application)"
            webshop.webApp -> stripe "Confirms the payment with the card details (the card is authorised, not charged yet)"
            stripe -> webshop.orderService.payments "Sends a signed payment_intent.amount_capturable_updated webhook"
            webshop.orderService.payments -> webshop.orderService.order "Marks the order as payment authorised"
            webshop.messageBroker -> webshop.monolith "Delivers OrderPlaced; Inventory reserves the stock (idempotent on the order ID)"
            webshop.monolith -> webshop.messageBroker "Publishes StockReserved"
            webshop.messageBroker -> webshop.orderService.order "Delivers StockReserved"
            webshop.orderService.order -> webshop.orderService.payments "Captures the authorised payment"
            webshop.orderService.order -> emailService "Sends the order confirmation email"
            autolayout tb
            description "The checkout flow, now inside the Order Service (ADR-0007): Order publishes OrderPlaced to the Message Broker and continues to payment without waiting for Inventory in the Webshop Monolith (ADR-0006); the card is authorised through Stripe (ADR-0004), Inventory reserves the stock asynchronously, and the payment is captured once StockReserved arrives."
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
