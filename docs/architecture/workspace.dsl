workspace "Webshop" "C4 model of an imaginary webshop, evolved through Architecture Decision Records." {

    !identifiers hierarchical
    !adrs decisions madr

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
            }
        }

        emailService = softwareSystem "Email Service" "Third-party service that delivers transactional emails." {
            tags "External"
        }

        customer -> webshop.webApp "Browses products and places orders using" "HTTPS"
        webshop.webApp -> webshop.monolith.catalog "Reads products and prices from" "JSON/HTTPS"
        webshop.webApp -> webshop.monolith.order "Places orders using" "JSON/HTTPS"
        webshop.webApp -> webshop.monolith.customerAccounts "Signs customers in and manages profiles using" "JSON/HTTPS"

        webshop.monolith.order -> webshop.monolith.catalog "Gets product details and prices from" "In-process call"
        webshop.monolith.order -> webshop.monolith.inventory "Reserves stock using" "In-process call"
        webshop.monolith.order -> webshop.monolith.customerAccounts "Gets customer and delivery details from" "In-process call"
        webshop.monolith.order -> emailService "Sends order confirmation emails using" "HTTPS"
        emailService -> customer "Delivers emails to"
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
            description "The Container view of the Webshop: a single-page application and a modular monolith (ADR-0002)."
        }

        component webshop.monolith "Components" {
            include *
            autolayout lr
            description "The Component view of the Webshop Monolith: its business modules (ADR-0002)."
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
        }
    }

}
