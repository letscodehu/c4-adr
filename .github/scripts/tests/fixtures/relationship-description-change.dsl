workspace "Fixture" "Base model for the model-diff tests." {

    !identifiers hierarchical

    model {
        customer = person "Customer" "Places orders."

        webshop = softwareSystem "Webshop" "Sells products." {
            web = container "Web App" "Storefront." "React"
            api = container "API" "Order API." "Java" {
                orders = component "Orders" "Handles orders." "Spring"
            }
        }

        email = softwareSystem "Email Service" "Delivers emails." {
            tags "External" "Third Party"
        }

        customer -> webshop.web "Places orders using" "HTTPS"
        webshop.web -> webshop.api.orders "Calls" "JSON/HTTPS"
        webshop.api -> email "Sends order emails using"

        production = deploymentEnvironment "Production" {
            aws = deploymentNode "AWS" "" "Amazon Web Services" {
                lb = infrastructureNode "Load Balancer" "" "ALB"
                ec2 = deploymentNode "EC2" "" "Ubuntu" {
                    webInstance = containerInstance webshop.web
                    apiInstance = containerInstance webshop.api
                }
                lb -> ec2.webInstance "Forwards requests to"
            }
        }
    }

    views {
        systemContext webshop "SystemContext" {
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
