variable "resource_group_name" {
  description = "Nombre del Resource Group para la plataforma de automatizaciÃ³n"
  type        = string
  default     = "rg-azure-infra-agent-dev"
}

variable "location" {
  description = "RegiÃ³n de Azure donde se desplegarÃ¡ la plataforma"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Ambiente de despliegue"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "El ambiente debe ser dev, test o prod."
  }
}