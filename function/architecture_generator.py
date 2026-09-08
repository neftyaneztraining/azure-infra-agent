import logging
from dataclasses import dataclass, field


@dataclass
class ArchitectureResult:
    request_id: str
    architecture_type: str
    resources: list[str] = field(default_factory=list)
    status: str = "architecture_generated"


def generate_architecture(analysis) -> ArchitectureResult:
    """
    Generate a basic Azure architecture from an AnalysisResult.
    """

    request_id = analysis.request_id
    resource_type = analysis.resource_type

    resources = []

    if resource_type == "Microsoft.Storage/storageAccounts":
        architecture_type = "Azure Storage Account"

        resources = [
            "Resource Group",
            "Storage Account",
            "Blob Service",
            "HTTPS Only",
            "Storage Account Security"
        ]

    elif resource_type == "Microsoft.Compute/virtualMachines":
        architecture_type = "Azure Virtual Machine"

        resources = [
            "Resource Group",
            "Virtual Network",
            "Subnet",
            "Network Interface",
            "Network Security Group",
            "Virtual Machine"
        ]

    elif resource_type == "Microsoft.Network/virtualNetworks":
        architecture_type = "Azure Virtual Network"

        resources = [
            "Resource Group",
            "Virtual Network",
            "Subnet",
            "Network Security Group"
        ]

    elif resource_type == "Microsoft.KeyVault/vaults":
        architecture_type = "Azure Key Vault"

        resources = [
            "Resource Group",
            "Key Vault",
            "Access Policy / RBAC",
            "Private Endpoint"
        ]

    else:
        architecture_type = "Unknown Azure Architecture"

        resources = [
            "Resource Group"
        ]

    result = ArchitectureResult(
        request_id=request_id,
        architecture_type=architecture_type,
        resources=resources
    )

    logging.info(
        "Architecture generated successfully: %s",
        result
    )

    return result