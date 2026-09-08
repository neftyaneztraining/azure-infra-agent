import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class AnalysisResult:
    request_id: str
    resource_type: Optional[str]
    request: str
    environment: str
    status: str
    requirements: dict
    requires_more_information: bool
    missing_information: list[str]
    decision: str


def analyze_request(request: dict) -> AnalysisResult:
    request_id = request["request_id"]
    request_text = request["request"]
    environment = request["environment"]

    text = request_text.lower()

    resource_type = None
    requirements = {}

    if "storage account" in text or "storage" in text:
        resource_type = "Microsoft.Storage/storageAccounts"
        requirements["resource"] = "Azure Storage Account"

    elif "virtual machine" in text or "vm" in text:
        resource_type = "Microsoft.Compute/virtualMachines"
        requirements["resource"] = "Azure Virtual Machine"

    elif "virtual network" in text or "vnet" in text:
        resource_type = "Microsoft.Network/virtualNetworks"
        requirements["resource"] = "Azure Virtual Network"

    elif "key vault" in text:
        resource_type = "Microsoft.KeyVault/vaults"
        requirements["resource"] = "Azure Key Vault"

    missing_information = []

    if resource_type is None:
        missing_information.append("resource_type")

    if resource_type == "Microsoft.Compute/virtualMachines":
        if not any(
            os_name in text
            for os_name in [
                "windows",
                "linux",
                "ubuntu",
                "red hat",
                "rhel",
                "debian"
            ]
        ):
            missing_information.append("operating_system")

    requires_more_information = len(missing_information) > 0

    if requires_more_information:
        decision = "NEEDS_INFORMATION"
    else:
        decision = "READY_FOR_ARCHITECTURE"

    result = AnalysisResult(
        request_id=request_id,
        resource_type=resource_type,
        request=request_text,
        environment=environment,
        status="analyzed",
        requirements=requirements,
        requires_more_information=requires_more_information,
        missing_information=missing_information,
        decision=decision,
    )

    logging.info(
        "Request analysis completed: %s",
        result
    )

    return result