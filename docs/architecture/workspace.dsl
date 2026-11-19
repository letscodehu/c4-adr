workspace "Webshop" "C4 model of an imaginary webshop, evolved through Architecture Decision Records." {

    !identifiers hierarchical
    !adrs decisions madr

    model {
        customer = person "Customer" "A person who browses the catalogue and places orders."

        webshop = softwareSystem "Webshop" "Lets customers browse products, place orders and track them."

        emailService = softwareSystem "Email Service" "Third-party service that delivers transactional emails." {
            tags "External"
        }

        customer -> webshopp "Browses products and places orders using"
        webshop -> emailService "Sends order confirmation emails using"
        emailService -> customer "Delivers emails to"
    }

    views {
        systemContext webshop "SystemContext" {
            include *
            autolayout lr
            description "The System Context view of the Webshop."
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
        }
    }

}
