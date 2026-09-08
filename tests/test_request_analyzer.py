from function.request_analyzer import analyze_request


def test_storage_account_is_ready_for_architecture():
    request = {
        "request_id": "test-storage-001",
        "request": "Create a small Azure Storage Account",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == "Microsoft.Storage/storageAccounts"
    assert result.requirements["resource"] == "Azure Storage Account"
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_vm_without_operating_system_needs_information():
    request = {
        "request_id": "test-vm-001",
        "request": "Create a virtual machine",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == "Microsoft.Compute/virtualMachines"
    assert result.requires_more_information is True
    assert "operating_system" in result.missing_information
    assert result.decision == "NEEDS_INFORMATION"


def test_vm_with_ubuntu_is_ready_for_architecture():
    request = {
        "request_id": "test-vm-002",
        "request": "Create an Ubuntu virtual machine",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type == "Microsoft.Compute/virtualMachines"
    assert result.requires_more_information is False
    assert result.missing_information == []
    assert result.decision == "READY_FOR_ARCHITECTURE"


def test_unknown_resource_needs_resource_type():
    request = {
        "request_id": "test-unknown-001",
        "request": "Create something that is not supported",
        "environment": "dev",
    }

    result = analyze_request(request)

    assert result.resource_type is None
    assert result.requires_more_information is True
    assert "resource_type" in result.missing_information
    assert result.decision == "NEEDS_INFORMATION"
