import json
import logging
import subprocess
import os
from dataclasses import dataclass
from pathlib import Path


# ============================================================
# TERRAFORM PLAN RESULT
# ============================================================

@dataclass
class TerraformPlanResult:
    request_id: str
    status: str
    working_directory: str
    plan_file: str
    plan_text_file: str
    plan_output: str
    message: str


# ============================================================
# TERRAFORM APPLY RESULT
# ============================================================

@dataclass
class TerraformApplyResult:
    request_id: str
    status: str
    working_directory: str
    apply_output: str
    terraform_outputs: dict
    message: str


# ============================================================
# RUN TERRAFORM COMMAND
# ============================================================

def _run_command(
    command: list[str],
    working_directory: Path
) -> subprocess.CompletedProcess:

    logging.info(
        "Executing Terraform command: %s",
        " ".join(command)
    )

    result = subprocess.run(
        command,
        cwd=working_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    if result.stdout:

        logging.info(
            "Terraform stdout:\n%s",
            result.stdout
        )

    if result.stderr:

        logging.info(
            "Terraform stderr:\n%s",
            result.stderr
        )

    return result


# ============================================================
# GENERATE TERRAFORM PLAN
# ============================================================

def generate_terraform_plan(
    request_id: str,
    terraform_directory: str
) -> TerraformPlanResult:

    working_directory = Path(
        terraform_directory
    )

    if not working_directory.exists():

        raise FileNotFoundError(
            f"Terraform directory does not exist: "
            f"{working_directory}"
        )

    if not (
        working_directory / "main.tf"
    ).exists():

        raise FileNotFoundError(
            f"main.tf was not found in: "
            f"{working_directory}"
        )

    # --------------------------------------------------------
    # Terraform INIT
    # --------------------------------------------------------

    init_result = _run_command(
        [
            "terraform",
            "init",
            "-input=false"
        ],
        working_directory
    )

    if init_result.returncode != 0:

        raise RuntimeError(
            "Terraform init failed:\n"
            + init_result.stdout
            + "\n"
            + init_result.stderr
        )

    # --------------------------------------------------------
    # Terraform VALIDATE
    # --------------------------------------------------------

    validate_result = _run_command(
        [
            "terraform",
            "validate"
        ],
        working_directory
    )

    if validate_result.returncode != 0:

        raise RuntimeError(
            "Terraform validate failed:\n"
            + validate_result.stdout
            + "\n"
            + validate_result.stderr
        )

    # --------------------------------------------------------
    # Terraform PLAN
    # --------------------------------------------------------

    plan_file = (
        working_directory
        / "terraform.tfplan"
    )

    plan_text_file = (
        working_directory
        / "plan.txt"
    )

    plan_result = _run_command(
        [
            "terraform",
            "plan",
            "-input=false",
            "-out=terraform.tfplan"
        ],
        working_directory
    )

    if plan_result.returncode != 0:

        raise RuntimeError(
            "Terraform plan failed:\n"
            + plan_result.stdout
            + "\n"
            + plan_result.stderr
        )

    # --------------------------------------------------------
    # Terraform SHOW
    # --------------------------------------------------------

    show_result = _run_command(
        [
            "terraform",
            "show",
            "-no-color",
            "terraform.tfplan"
        ],
        working_directory
    )

    if show_result.returncode != 0:

        raise RuntimeError(
            "Terraform show failed:\n"
            + show_result.stdout
            + "\n"
            + show_result.stderr
        )

    plan_text_file.write_text(
        show_result.stdout,
        encoding="utf-8"
    )

    logging.info(
        "Terraform plan generated successfully: %s",
        request_id
    )

    return TerraformPlanResult(

        request_id=request_id,

        status="terraform_plan_generated",

        working_directory=str(
            working_directory
        ),

        plan_file=str(
            plan_file
        ),

        plan_text_file=str(
            plan_text_file
        ),

        plan_output=(
            show_result.stdout
        ),

        message=(
            "Terraform plan generated successfully."
        )
    )


# ============================================================
# APPLY TERRAFORM
# ============================================================

def apply_terraform(
    request_id: str,
    terraform_directory: str
) -> TerraformApplyResult:

    working_directory = Path(
        terraform_directory
    )

    # --------------------------------------------------------
    # Validate Terraform directory
    # --------------------------------------------------------

    if not working_directory.exists():

        raise FileNotFoundError(
            f"Terraform directory does not exist: "
            f"{working_directory}"
        )

    # --------------------------------------------------------
    # Validate Terraform plan
    # --------------------------------------------------------

    plan_file = (
        working_directory
        / "terraform.tfplan"
    )

    if not plan_file.exists():

        raise FileNotFoundError(
            f"terraform.tfplan was not found in: "
            f"{working_directory}"
        )

    logging.info(
    "Terraform apply starting: %s",
    request_id
)




    # --------------------------------------------------------
    # Terraform APPLY
    #
    # IMPORTANT:
    # We apply the previously generated plan.
    # Terraform will NOT create a new plan here.
    # --------------------------------------------------------

    apply_result = _run_command(
        [
            "terraform",
            "apply",
            "-input=false",
            "terraform.tfplan"
        ],
        working_directory
    )

    if apply_result.returncode != 0:

        terraform_error = (
            apply_result.stdout
            + "\n"
            + apply_result.stderr
        )

        # --------------------------------------------------------
        # Terraform plan is stale
        #
        # The saved plan can no longer be applied because
        # Terraform state changed after the plan was generated.
        #
        # This is NOT a normal apply failure.
        # The caller must generate a new plan and request
        # human approval again.
        # --------------------------------------------------------

        if "Saved plan is stale" in terraform_error:

            logging.warning(
                "Terraform plan is stale: %s",
                request_id
            )

            return TerraformApplyResult(

                request_id=request_id,

                status="terraform_plan_stale",

                working_directory=str(
                    working_directory
                ),

                apply_output=terraform_error,

                terraform_outputs={},

                message=(
                    "Terraform plan is stale. "
                    "A new Terraform plan must be generated "
                    "and approved before applying."
                )
            )

        # --------------------------------------------------------
        # Normal Terraform apply failure
        # --------------------------------------------------------

        raise RuntimeError(
            "Terraform apply failed:\n"
            + terraform_error
        )

    logging.info(
        "Terraform apply completed successfully: %s",
        request_id
    )

    # --------------------------------------------------------
    # Terraform OUTPUT
    #
    # Retrieve structured Terraform outputs after apply.
    # --------------------------------------------------------

    output_result = _run_command(
        [
            "terraform",
            "output",
            "-json"
        ],
        working_directory
    )

    if output_result.returncode != 0:

        raise RuntimeError(
            "Terraform output failed:\n"
            + output_result.stdout
            + "\n"
            + output_result.stderr
        )

    try:

        terraform_outputs = json.loads(
            output_result.stdout
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "Terraform output returned invalid JSON."
        ) from exc

    logging.info(
        "Terraform outputs retrieved successfully: %s",
        request_id
    )

    # --------------------------------------------------------
    # Return Terraform apply result
    # --------------------------------------------------------

    return TerraformApplyResult(

        request_id=request_id,

        status="terraform_applied",

        working_directory=str(
            working_directory
        ),

        apply_output=(
            apply_result.stdout
        ),

        terraform_outputs=terraform_outputs,

        message=(
            "Terraform infrastructure "
            "applied successfully."
        )
    )