import json
import subprocess
from pathlib import Path

import pytest

from function.terraform_runner import (
    apply_terraform,
    generate_terraform_plan,
)


def completed_process(
    returncode=0,
    stdout="",
    stderr="",
):
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_generate_plan_rejects_missing_directory(tmp_path):
    missing_directory = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        generate_terraform_plan(
            "runner-test-001",
            str(missing_directory),
        )


def test_generate_plan_requires_main_tf(tmp_path):
    with pytest.raises(FileNotFoundError, match="main.tf"):
        generate_terraform_plan(
            "runner-test-002",
            str(tmp_path),
        )


def test_generate_plan_fails_when_init_fails(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "main.tf").write_text(
        "terraform {}",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        return completed_process(
            returncode=1,
            stderr="init failed",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    with pytest.raises(RuntimeError, match="Terraform init failed"):
        generate_terraform_plan(
            "runner-test-003",
            str(tmp_path),
        )


def test_generate_plan_fails_when_validate_fails(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "main.tf").write_text(
        "terraform {}",
        encoding="utf-8",
    )

    calls = []

    def fake_run_command(command, working_directory):
        calls.append(command)

        if command[1] == "init":
            return completed_process()

        return completed_process(
            returncode=1,
            stderr="validate failed",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    with pytest.raises(
        RuntimeError,
        match="Terraform validate failed",
    ):
        generate_terraform_plan(
            "runner-test-004",
            str(tmp_path),
        )

    assert len(calls) == 2


def test_generate_plan_fails_when_plan_fails(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "main.tf").write_text(
        "terraform {}",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        if command[1] in {"init", "validate"}:
            return completed_process()

        return completed_process(
            returncode=1,
            stderr="plan failed",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    with pytest.raises(
        RuntimeError,
        match="Terraform plan failed",
    ):
        generate_terraform_plan(
            "runner-test-005",
            str(tmp_path),
        )


def test_generate_plan_fails_when_show_fails(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "main.tf").write_text(
        "terraform {}",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        if command[1] in {
            "init",
            "validate",
            "plan",
        }:
            return completed_process()

        return completed_process(
            returncode=1,
            stderr="show failed",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    with pytest.raises(
        RuntimeError,
        match="Terraform show failed",
    ):
        generate_terraform_plan(
            "runner-test-006",
            str(tmp_path),
        )


def test_generate_plan_succeeds(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "main.tf").write_text(
        "terraform {}",
        encoding="utf-8",
    )

    plan_output = """
Terraform will perform the following actions:

Plan: 3 to add, 0 to change, 0 to destroy.
"""

    calls = []

    def fake_run_command(command, working_directory):
        calls.append(command)

        if command[1] in {
            "init",
            "validate",
            "plan",
        }:
            return completed_process()

        if command[1] == "show":
            return completed_process(
                stdout=plan_output,
            )

        raise AssertionError(
            f"Unexpected command: {command}"
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    result = generate_terraform_plan(
        "runner-test-007",
        str(tmp_path),
    )

    assert result.request_id == "runner-test-007"
    assert result.status == "terraform_plan_generated"
    assert result.working_directory == str(tmp_path)
    assert result.plan_file == str(
        tmp_path / "terraform.tfplan"
    )
    assert result.plan_text_file == str(
        tmp_path / "plan.txt"
    )
    assert result.plan_output == plan_output
    assert result.message == (
        "Terraform plan generated successfully."
    )

    assert (tmp_path / "plan.txt").exists()
    assert (
        (tmp_path / "plan.txt").read_text(
            encoding="utf-8"
        )
        == plan_output
    )

    assert len(calls) == 4
    assert calls[0][1] == "init"
    assert calls[1][1] == "validate"
    assert calls[2][1] == "plan"
    assert calls[3][1] == "show"


def test_apply_rejects_missing_directory(tmp_path):
    missing_directory = tmp_path / "missing"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        apply_terraform(
            "runner-test-008",
            str(missing_directory),
        )


def test_apply_requires_plan_file(tmp_path):
    with pytest.raises(
        FileNotFoundError,
        match="terraform.tfplan",
    ):
        apply_terraform(
            "runner-test-009",
            str(tmp_path),
        )


def test_apply_returns_stale_plan_status(
    tmp_path,
    monkeypatch,
):
    plan_file = tmp_path / "terraform.tfplan"
    plan_file.write_text(
        "test plan",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        return completed_process(
            returncode=1,
            stderr="Error: Saved plan is stale",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    result = apply_terraform(
        "runner-test-010",
        str(tmp_path),
    )

    assert result.request_id == "runner-test-010"
    assert result.status == "terraform_plan_stale"
    assert result.terraform_outputs == {}
    assert "new Terraform plan" in result.message


def test_apply_raises_for_normal_failure(
    tmp_path,
    monkeypatch,
):
    plan_file = tmp_path / "terraform.tfplan"
    plan_file.write_text(
        "test plan",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        return completed_process(
            returncode=1,
            stderr="StorageAccountAlreadyExists",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    with pytest.raises(
        RuntimeError,
        match="Terraform apply failed",
    ):
        apply_terraform(
            "runner-test-011",
            str(tmp_path),
        )


def test_apply_fails_when_output_command_fails(
    tmp_path,
    monkeypatch,
):
    plan_file = tmp_path / "terraform.tfplan"
    plan_file.write_text(
        "test plan",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        if command[1] == "apply":
            return completed_process()

        return completed_process(
            returncode=1,
            stderr="output failed",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    result = apply_terraform(
        "runner-test-012",
        str(tmp_path),
    )

    assert result.status == "terraform_applied"
    assert result.terraform_outputs == {}
    assert result.request_id == "runner-test-012"


def test_apply_rejects_invalid_output_json(
    tmp_path,
    monkeypatch,
):
    plan_file = tmp_path / "terraform.tfplan"
    plan_file.write_text(
        "test plan",
        encoding="utf-8",
    )

    def fake_run_command(command, working_directory):
        if command[1] == "apply":
            return completed_process()

        return completed_process(
            stdout="not valid json",
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    result = apply_terraform(
        "runner-test-013",
        str(tmp_path),
    )

    assert result.status == "terraform_applied"
    assert result.terraform_outputs == {}
    assert result.request_id == "runner-test-013"


def test_apply_succeeds_and_returns_outputs(
    tmp_path,
    monkeypatch,
):
    plan_file = tmp_path / "terraform.tfplan"
    plan_file.write_text(
        "test plan",
        encoding="utf-8",
    )

    outputs = {
        "resource_group_name": {
            "value": "rg-test",
        },
        "storage_account_name": {
            "value": "sttest",
        },
    }

    calls = []

    def fake_run_command(command, working_directory):
        calls.append(command)

        if command[1] == "apply":
            return completed_process(
                stdout="Apply complete! Resources: 3 added.",
            )

        if command[1] == "output":
            return completed_process(
                stdout=json.dumps(outputs),
            )

        raise AssertionError(
            f"Unexpected command: {command}"
        )

    monkeypatch.setattr(
        "function.terraform_runner._run_command",
        fake_run_command,
    )

    result = apply_terraform(
        "runner-test-014",
        str(tmp_path),
    )

    assert result.request_id == "runner-test-014"
    assert result.status == "terraform_applied"
    assert result.working_directory == str(tmp_path)
    assert result.apply_output == (
        "Apply complete! Resources: 3 added."
    )
    assert result.terraform_outputs == outputs
    assert result.message == (
        "Terraform infrastructure applied successfully."
    )

    assert calls[0][1] == "apply"
    assert calls[1][1] == "output"