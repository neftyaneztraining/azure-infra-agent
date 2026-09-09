from function.request_analyzer import analyze_request


def test_storage_account_is_ready_for_architecture():
    request = {
        "request_id": "analyzer-001",
        "request": "Create an Azure Storage Account",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == (
        "Microsoft.Storage/storageAccounts"
    )
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_vm_without_operating_system_needs_information():
    request = {
        "request_id": "analyzer-002",
        "request": "Create a virtual machine",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == (
        "Microsoft.Compute/virtualMachines"
    )
    assert result.requires_more_information is True
    assert result.missing_information == [
        "operating_system"
    ]
    assert result.decision == "NEEDS_INFORMATION"


def test_vm_with_ubuntu_is_ready_for_architecture():
    request = {
        "request_id": "analyzer-003",
        "request": "Create an Ubuntu virtual machine",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == (
        "Microsoft.Compute/virtualMachines"
    )
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_unknown_resource_needs_resource_type():
    request = {
        "request_id": "analyzer-004",
        "request": "Create something unknown",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type is None
    assert result.requires_more_information is True
    assert result.missing_information == [
        "resource_type"
    ]
    assert result.decision == "NEEDS_INFORMATION"


def test_windows_vm_is_ready_for_architecture():
    request = {
        "request_id": "analyzer-005",
        "request": "Create a Windows virtual machine",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == (
        "Microsoft.Compute/virtualMachines"
    )
    assert result.requirements["resource"] == (
        "Azure Virtual Machine"
    )
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_virtual_network_is_ready_for_architecture():
    request = {
        "request_id": "analyzer-006",
        "request": "Create an Azure VNet",
        "environment": "test",
    }

    result = analyze_request(request)

    assert result.resource_type == (
        "Microsoft.Network/virtualNetworks"
    )
    assert result.requirements["resource"] == (
        "Azure Virtual Network"
    )
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_key_vault_is_ready_for_architecture():
    request = {
        "request_id": "analyzer-007",
        "request": "Create an Azure Key Vault",
        "environment": "prod",
    }

    result = analyze_request(request)

    assert result.resource_type == (
        "Microsoft.KeyVault/vaults"
    )
    assert result.requirements["resource"] == (
        "Azure Key Vault"
    )
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_analysis_result_preserves_request_metadata():
    request = {
        "request_id": "analyzer-008",
        "request": "Create a storage account",
        "environment": "prod",
    }

    result = analyze_request(request)

    assert result.request_id == "analyzer-008"
    assert result.request == (
        "Create a storage account"
    )
    assert result.environment == "prod"
    assert result.status == "analyzed"
    assert result.resource_type == (
        "Microsoft.Storage/storageAccounts"
    )
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"