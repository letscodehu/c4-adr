workspace "Fixture" "Same model as base.dsl, declared in a different order, with renamed DSL identifiers." {

    !identifiers hierarchical

    model {
        mailer = softwareSystem "Email Service" "Delivers emails." {
            tags "Third Party" "External"
        }

        shop = softwareSystem "Webshop" "Sells products." {
            backend = container "API" "Order API." "Java" {
                orderComponent = component "Orders" "Handles orders." "Spring"
            }
            frontend = container "Web App" "Storefront." "React"
        }

        buyer = person "Customer" "Places orders."

        shop.backend -> mailer "Sends emails using"
        shop.frontend -> shop.backend.orderComponent "Calls" "JSON/HTTPS"
        buyer -> shop.frontend "Places orders using" "HTTPS"

        prod = deploymentEnvironment "Production" {
            cloud = deploymentNode "AWS" "" "Amazon Web Services" {
                vm = deploymentNode "EC2" "" "Ubuntu" {
                    a = containerInstance shop.backend
                    w = containerInstance shop.frontend
                }
                balancer = infrastructureNode "Load Balancer" "" "ALB"
                balancer -> vm.w "Forwards requests to"
            }
        }
    }

    views {
        systemContext shop "SystemContext" {
            include *
            autolayout lr
        }

        styles {
            element "Person" {
                shape Person
            }
        }
    }

}
