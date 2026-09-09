from pathlib import Path

from function.terraform_generator import (
    _terraform_name,
    generate_terraform,
)

def test_terraform_name_normalizes_value():
    assert _terraform_name("My Request 001") == "my-request-001"
    assert _terraform_name("Azure_Storage/Test") == "azure-storage-test"
    assert _terraform_name("---") == "azure-infra"


def test_generate_terraform_rejects_non_dictionary():
    try:
        generate_terraform("invalid")
        assert False, "Expected TypeError"
    except TypeError as exc:
        assert str(exc) == "architecture must be a dictionary"


def test_generate_terraform_requires_request_id():
    architecture = {
        "decision": "APPROVED",
    }

    try:
        generate_terraform(
            architecture,
            output_root="unused",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "Missing required field: request_id"


def test_generate_terraform_requires_approval(tmp_path):
    architecture = {
        "request_id": "terraform-test-001",
        "decision": "REJECTED",
    }

    try:
        generate_terraform(
            architecture,
            output_root=str(tmp_path),
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert (
            str(exc)
            == "Terraform generation requires decision APPROVED"
        )


def test_generate_terraform_creates_expected_files(tmp_path):
    architecture = {
        "request_id": "Terraform Test 001",
        "architecture_type": "Azure Storage",
        "resources": [
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Storage/storageAccounts/blobServices",
        ],
        "environment": "prod",
        "decision": "APPROVED",
    }

    result = generate_terraform(
        architecture,
        output_root=str(tmp_path),
    )

    expected_directory = (
        tmp_path / "terraform-test-001"
    )

    assert result.request_id == "Terraform Test 001"
    assert result.status == "terraform_generated"
    assert result.output_directory == str(
        expected_directory
    )
    assert len(result.files) == 4

    expected_files = {
        "main.tf",
        "variables.tf",
        "terraform.tfvars",
        "outputs.tf",
    }

    assert {
        Path(path).name
        for path in result.files
    } == expected_files

    for filename in expected_files:
        assert (
            expected_directory / filename
        ).exists()

    main_tf = (
        expected_directory / "main.tf"
    ).read_text(encoding="utf-8")

    variables_tf = (
        expected_directory / "variables.tf"
    ).read_text(encoding="utf-8")

    terraform_tfvars = (
        expected_directory / "terraform.tfvars"
    ).read_text(encoding="utf-8")

    outputs_tf = (
        expected_directory / "outputs.tf"
    ).read_text(encoding="utf-8")

    assert "Request ID: Terraform Test 001" in main_tf
    assert "Architecture: Azure Storage" in main_tf
    assert "Environment: prod" in main_tf
    assert 'name = "rg-generated-terraform-test-001"' in main_tf
    assert 'name = "stgenterraformtest001"' in main_tf
    assert "Microsoft.Storage/storageAccounts" in main_tf

    assert 'variable "location"' in variables_tf
    assert 'variable "environment"' in variables_tf
    assert '"dev", "test", "prod"' in variables_tf

    assert 'environment = "prod"' in terraform_tfvars

    assert 'output "resource_group_name"' in outputs_tf
    assert 'output "storage_account_name"' in outputs_tf
    assert 'output "storage_account_id"' in outputs_tf
    assert 'output "storage_container_name"' in outputs_tf