from types import SimpleNamespace

from function.architecture_generator import generate_architecture


def test_storage_architecture():
    analysis = SimpleNamespace(
        request_id="architecture-001",
        resource_type="Microsoft.Storage/storageAccounts",
    )

    result = generate_architecture(analysis)

    assert result.request_id == "architecture-001"
    assert result.architecture_type == "Azure Storage Account"
    assert result.status == "architecture_generated"
    assert result.resources == [
        "Resource Group",
        "Storage Account",
        "Blob Service",
        "HTTPS Only",
        "Storage Account Security",
    ]


def test_virtual_machine_architecture():
    analysis = SimpleNamespace(
        request_id="architecture-002",
        resource_type="Microsoft.Compute/virtualMachines",
    )

    result = generate_architecture(analysis)

    assert result.request_id == "architecture-002"
    assert result.architecture_type == "Azure Virtual Machine"
    assert result.status == "architecture_generated"
    assert result.resources == [
        "Resource Group",
        "Virtual Network",
        "Subnet",
        "Network Interface",
        "Network Security Group",
        "Virtual Machine",
    ]


def test_virtual_network_architecture():
    analysis = SimpleNamespace(
        request_id="architecture-003",
        resource_type="Microsoft.Network/virtualNetworks",
    )

    result = generate_architecture(analysis)

    assert result.request_id == "architecture-003"
    assert result.architecture_type == "Azure Virtual Network"
    assert result.status == "architecture_generated"
    assert result.resources == [
        "Resource Group",
        "Virtual Network",
        "Subnet",
        "Network Security Group",
    ]


def test_key_vault_architecture():
    analysis = SimpleNamespace(
        request_id="architecture-004",
        resource_type="Microsoft.KeyVault/vaults",
    )

    result = generate_architecture(analysis)

    assert result.request_id == "architecture-004"
    assert result.architecture_type == "Azure Key Vault"
    assert result.status == "architecture_generated"
    assert result.resources == [
        "Resource Group",
        "Key Vault",
        "Access Policy / RBAC",
        "Private Endpoint",
    ]


def test_unknown_resource_generates_fallback_architecture():
    analysis = SimpleNamespace(
        request_id="architecture-005",
        resource_type="unknown.resource/type",
    )

    result = generate_architecture(analysis)

    assert result.request_id == "architecture-005"
    assert result.architecture_type == (
        "Unknown Azure Architecture"
    )
    assert result.status == "architecture_generated"
    assert result.resources == [
        "Resource Group",
    ]