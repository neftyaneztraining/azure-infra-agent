import azure.functions as func
import logging
import json
import os
from pathlib import Path

from azure.storage.queue import QueueClient

from request_analyzer import analyze_request
from architecture_generator import generate_architecture
from architecture_reviewer import review_architecture_request
from terraform_generator import generate_terraform
from audit import write_audit_event

from terraform_runner import (
    generate_terraform_plan,
    apply_terraform,
)

app = func.FunctionApp()


# ============================================================
# HELPER: DECODE QUEUE MESSAGE
# ============================================================

def decode_queue_message(msg: func.QueueMessage) -> str:
    """
    Decodes an Azure Storage Queue message.

    utf-8-sig is intentionally used so both normal UTF-8
    and UTF-8 with BOM are supported.
    """

    body = msg.get_body()

    if not body:
        raise ValueError(
            "Queue message body is empty"
        )

    message = body.decode(
        "utf-8-sig"
    ).strip()

    if not message:
        raise ValueError(
            "Queue message body is empty after decoding"
        )

    logging.info(
        "Decoded queue message: %s",
        message
    )

    return message


def send_architecture_review(
    architecture,
    environment,
    request
):
    connection_string = os.environ["AzureWebJobsStorage"]

    queue_client = QueueClient.from_connection_string(
        conn_str=connection_string,
        queue_name="architecture-review"
    )

    review_message = {
        "request_id":
            architecture.request_id,

        "environment":
            environment,

        "request":
            request,

        "architecture_type":
            architecture.architecture_type,

        "resources":
            architecture.resources,

        "status":
            "pending_review"
    }

    queue_client.send_message(
        json.dumps(review_message)
    )

    logging.info(
        "Architecture review message sent successfully: %s",
        architecture.request_id
    )


# ============================================================
# HELPER: SEND ARCHITECTURE TO REVIEW QUEUE
# ============================================================

def send_architecture_approval(
    review_result,
    environment,
    request
):
    connection_string = os.environ["AzureWebJobsStorage"]

    queue_client = QueueClient.from_connection_string(
        conn_str=connection_string,
        queue_name="architecture-approval"
    )

    approval_message = {
        "request_id":
            review_result.request_id,

        "environment":
            environment,

        "request":
            request,

        "architecture_type":
            review_result.architecture_type,

        "resources":
            review_result.resources,

        "status":
            "pending_approval",

        "recommendation":
            review_result.recommendation,

        "comments":
            review_result.comments
    }

    queue_client.send_message(
        json.dumps(approval_message)
    )

    write_audit_event(
        request_id=review_result.request_id,
        stage="architecture_approval",
        status="architecture_approval_pending",
        actor="system",
        message="Architecture is waiting for human approval"
    )

    logging.info(
        "Architecture approval message sent successfully: %s",
        review_result.request_id
    )


# ============================================================
# HELPER: SEND TERRAFORM GENERATION REQUEST
# ============================================================

def send_terraform_generation_request(
    approval
):
    connection_string = os.environ["AzureWebJobsStorage"]

    queue_client = QueueClient.from_connection_string(
        conn_str=connection_string,
        queue_name="terraform-generation"
    )

    terraform_message = {
        "request_id": approval["request_id"],

        "environment": approval.get(
            "environment",
            "dev"
        ),

        "request": approval.get(
            "request",
            ""
        ),

        "architecture_type": approval.get(
            "architecture_type",
            ""
        ),

        "resources": approval.get(
            "resources",
            []
        ),

        "decision": "APPROVED",

        "comments": approval.get(
            "comments",
            ""
        ),

        "status": "terraform_pending"
    }

    queue_client.send_message(
        json.dumps(terraform_message)
    )

    logging.info(
        "Terraform generation request sent successfully: %s",
        approval["request_id"]
    )


# ============================================================
# 1. PROCESS INFRASTRUCTURE REQUEST
# ============================================================

@app.function_name(name="process_request")
@app.queue_trigger(
    arg_name="msg",
    queue_name="infrastructure-requests",
    connection="AzureWebJobsStorage"
)
def process_request(
    msg: func.QueueMessage
) -> None:

    message = msg.get_body().decode("utf-8")

    logging.info(
        "Raw message received: %s",
        message
    )

    try:

        request = json.loads(message)

        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        request_id = request.get(
            "request_id"
        )

        request_text = request.get(
            "request"
        )

        environment = request.get(
            "environment"
        )

        if not request_id:
            raise ValueError(
                "Missing required field: request_id"
            )

        if not request_text:
            raise ValueError(
                "Missing required field: request"
            )

        if not environment:
            raise ValueError(
                "Missing required field: environment"
            )

        # ----------------------------------------------------
        # Audit: infrastructure request received
        # ----------------------------------------------------

        write_audit_event(
            request_id=str(request_id).strip(),
            stage="infrastructure_request",
            status="infrastructure_request_received",
            actor="system",
            message=(
                "Infrastructure request received "
                "and validated successfully"
            )
        )

        # ----------------------------------------------------
        # Normalize request
        # ----------------------------------------------------

        normalized_request = {
            "request_id":
                str(request_id).strip(),

            "request":
                str(request_text).strip(),

            "environment":
                str(environment).strip().lower(),

            "status":
                "received"
        }

        logging.info(
            "Normalized request: %s",
            json.dumps(normalized_request)
        )

        logging.info(
            "Infrastructure request normalized successfully: %s",
            normalized_request["request_id"]
        )

        # ----------------------------------------------------
        # Analyze infrastructure request
        # ----------------------------------------------------

        analysis = analyze_request(
            normalized_request
        )

        logging.info(
            "Analysis result: %s",
            json.dumps({
                "request_id":
                    analysis.request_id,

                "resource_type":
                    analysis.resource_type,

                "request":
                    analysis.request,

                "environment":
                    analysis.environment,

                "status":
                    analysis.status,

                "requires_more_information":
                    analysis.requires_more_information,

                "missing_information":
                    analysis.missing_information,

                "decision":
                    analysis.decision
            })
        )

        logging.info(
            "Infrastructure request analyzed successfully: %s",
            analysis.request_id
        )

        # ----------------------------------------------------
        # Generate architecture only when ready
        # ----------------------------------------------------

        if analysis.decision == "READY_FOR_ARCHITECTURE":

            architecture = generate_architecture(
                analysis
            )

            logging.info(
                "Architecture result: %s",
                json.dumps({
                    "request_id":
                        architecture.request_id,

                    "architecture_type":
                        architecture.architecture_type,

                    "resources":
                        architecture.resources,

                    "status":
                        architecture.status
                })
            )

            logging.info(
                "Infrastructure architecture generated "
                "successfully: %s",
                architecture.request_id
            )

            # ------------------------------------------------
            # Send architecture to review queue
            # ------------------------------------------------

            send_architecture_review(
                architecture=architecture,
                environment=analysis.environment,
                request=analysis.request
            )

        else:

            logging.info(
                "Architecture generation skipped. "
                "Decision: %s",
                analysis.decision
            )

    except json.JSONDecodeError:

        logging.error(
            "Invalid JSON received: %s",
            message
        )

        raise

    except ValueError as exc:

        logging.error(
            "Invalid infrastructure request: %s",
            exc
        )

        raise


# ============================================================
# 2. REVIEW ARCHITECTURE
# ============================================================

@app.function_name(name="review_architecture")
@app.queue_trigger(
    arg_name="msg",
    queue_name="architecture-review",
    connection="AzureWebJobsStorage"
)
def review_architecture(
    msg: func.QueueMessage
) -> None:

    message = msg.get_body().decode("utf-8")

    logging.info(
        "Architecture review message received: %s",
        message
    )

    try:

        review = json.loads(message)

        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        request_id = review.get(
            "request_id"
        )

        architecture_type = review.get(
            "architecture_type"
        )

        resources = review.get(
            "resources",
            []
        )

        if not request_id:
            raise ValueError(
                "Missing required field: request_id"
            )

        if not architecture_type:
            raise ValueError(
                "Missing required field: architecture_type"
            )

        # ----------------------------------------------------
        # Normalize review request
        # ----------------------------------------------------

        review_request = {
            "request_id":
                str(request_id).strip(),

            "architecture_type":
                str(architecture_type).strip(),

            "resources":
                resources
        }

        logging.info(
            "Architecture review request normalized: %s",
            json.dumps(review_request)
        )

        # ----------------------------------------------------
        # Review architecture
        # ----------------------------------------------------

        result = review_architecture_request(
            review_request
        )

        logging.info(
            "Architecture review completed: %s",
            result
        )

        logging.info(
            "Architecture review result: %s",
            json.dumps({
                "request_id":
                    result.request_id,

                "architecture_type":
                    result.architecture_type,

                "resources":
                    result.resources,

                "status":
                    result.status,

                "recommendation":
                    result.recommendation,

                "comments":
                    result.comments
            })
        )

        logging.info(
            "Architecture review completed "
            "successfully: %s",
            result.request_id
        )

        # ----------------------------------------------------
        # Audit: architecture review completed
        # ----------------------------------------------------

        write_audit_event(
            request_id=result.request_id,
            stage="architecture_review",
            status="architecture_review_completed",
            actor="system",
            decision=result.recommendation,
            message=(
                "Architecture review completed successfully"
            )
        )


        # ----------------------------------------------------
        # Send approved architecture to approval queue
        # ----------------------------------------------------

        if result.recommendation == "APPROVE":

            send_architecture_approval(
                result,
                review.get("environment"),
                review.get("request")
            )

            logging.info(
                "Architecture approved and sent to "
                "architecture-approval: %s",
                result.request_id
            )

        else:

            logging.info(
                "Architecture was not approved: %s "
                "Recommendation: %s",
                result.request_id,
                result.recommendation
            )


    except json.JSONDecodeError:

        logging.error(
            "Invalid architecture review JSON: %s",
            message
        )

        raise

    except ValueError as exc:

        logging.error(
            "Invalid architecture review request: %s",
            exc
        )

        raise

# ============================================================
# 3. ARCHITECTURE APPROVAL PAGE
# ============================================================

@app.function_name(
    name="architecture_approval"
)
@app.route(
    route="architecture/{request_id}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS
)
def architecture_approval(
    req: func.HttpRequest
) -> func.HttpResponse:

    request_id = req.route_params.get(
        "request_id"
    )

    html = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <title>
            Architecture Approval
        </title>

        <style>

            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #f5f7fa;
            }}

            .container {{
                max-width: 800px;
                margin: auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow:
                    0 2px 10px rgba(0,0,0,0.1);
            }}

            h1 {{
                color: #333;
            }}

            .request-id {{
                background: #eef2f7;
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}

            textarea {{
                width: 100%;
                height: 120px;
                margin-top: 10px;
                margin-bottom: 20px;
            }}

            button {{
                padding: 12px 25px;
                margin-right: 10px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }}

            .approve {{
                background: #28a745;
                color: white;
            }}

            .reject {{
                background: #dc3545;
                color: white;
            }}

            #result {{
                margin-top: 20px;
                padding: 15px;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <h1>
                Azure Architecture Approval
            </h1>

            <div class="request-id">

                <strong>
                    Request ID:
                </strong>

                {request_id}

            </div>

            <p>
                Review the proposed Azure architecture
                and approve or reject it.
            </p>

            <textarea
                id="comments"
                placeholder="Comments">
            </textarea>

            <br>

            <button
                class="approve"
                onclick="submitDecision('APPROVED')">

                APPROVE

            </button>

            <button
                class="reject"
                onclick="submitDecision('REJECTED')">

                REJECT

            </button>

            <div id="result"></div>

        </div>

        <script>

            async function submitDecision(decision) {{

                const comments =
                    document
                    .getElementById("comments")
                    .value;

                const response =
                    await fetch(
                        "/api/architecture/{request_id}/decision",
                        {{
                            method: "POST",

                            headers: {{
                                "Content-Type":
                                    "application/json"
                            }},

                            body: JSON.stringify({{
                                request_id:
                                    "{request_id}",

                                decision:
                                    decision,

                                comments:
                                    comments
                            }})
                        }}
                    );

                const data =
                    await response.json();

                document
                    .getElementById("result")
                    .innerText =
                        JSON.stringify(
                            data,
                            null,
                            2
                        );
            }}

        </script>

    </body>

    </html>
    """

    return func.HttpResponse(
        html,
        status_code=200,
        mimetype="text/html"
    )


# ============================================================
# 5. GENERATE TERRAFORM
# ============================================================

@app.function_name(name="generate_terraform_configuration")
@app.queue_trigger(
    arg_name="msg",
    queue_name="terraform-generation",
    connection="AzureWebJobsStorage"
)
def generate_terraform_configuration(
    msg: func.QueueMessage
) -> None:

    message = msg.get_body().decode("utf-8-sig")

    logging.info(
        "Terraform generation message received: %s",
        message
    )

    try:

        # ----------------------------------------------------
        # Parse message
        # ----------------------------------------------------

        architecture = json.loads(
            message
        )

        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        request_id = architecture.get(
            "request_id"
        )

        decision = architecture.get(
            "decision"
        )

        if not request_id:

            raise ValueError(
                "Missing required field: request_id"
            )

        if not decision:

            raise ValueError(
                "Missing required field: decision"
            )

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        architecture["request_id"] = str(
            request_id
        ).strip()

        architecture["decision"] = str(
            decision
        ).strip().upper()

        # ----------------------------------------------------
        # Validate approval
        # ----------------------------------------------------

        if architecture["decision"] != "APPROVED":

            raise ValueError(
                "Terraform generation requires decision APPROVED"
            )

        logging.info(
            "Terraform generation request normalized: %s",
            json.dumps(
                architecture,
                ensure_ascii=False
            )
        )

        # ----------------------------------------------------
        # Generate Terraform configuration
        # ----------------------------------------------------

        result = generate_terraform(
            architecture
        )

        logging.info(
             "Terraform generation result: %s",
            json.dumps(
                 {
                      "request_id":
                            result.request_id,

                        "status":
                             result.status,

                        "output_directory":
                            result.output_directory,

                        "files":
                            result.files,

                        "message":
                            result.message
                    },
                     ensure_ascii=False
                )
            )

        write_audit_event(
                request_id=result.request_id,
                stage="terraform_generation",
                status="terraform_generated",
                actor="system",
                message="Terraform configuration generated successfully"
            )
        # ----------------------------------------------------
        # Send Terraform plan request
        # ----------------------------------------------------

        plan_request_queue = QueueClient.from_connection_string(
            conn_str=os.environ["AzureWebJobsStorage"],
            queue_name="terraform-plan-request"
        )

        plan_request_message = {

            "request_id":
                result.request_id,

            "terraform_directory":
                result.output_directory,

            "decision":
                architecture["decision"]
        }

        plan_request_queue.send_message(
            json.dumps(
                plan_request_message,
                ensure_ascii=False
            )
        )

        logging.info(
            "Terraform plan request sent successfully: %s",
            result.request_id
        )

    except json.JSONDecodeError:

        logging.error(
            "Invalid Terraform generation JSON: %s",
            message
        )

        raise

    except ValueError as exc:

        logging.error(
            "Invalid Terraform generation request: %s",
            exc
        )

        raise

    except Exception as exc:

        logging.exception(
            "Unexpected error during Terraform generation: %s",
            exc
        )

        raise

# ============================================================
# 6. GENERATE TERRAFORM PLAN
# ============================================================

@app.function_name(name="generate_terraform_plan")
@app.queue_trigger(
    arg_name="msg",
    queue_name="terraform-plan-request",
    connection="AzureWebJobsStorage"
)
def generate_terraform_plan_function(
    msg: func.QueueMessage
) -> None:

    message = decode_queue_message(msg)

    logging.info(
        "Terraform plan request received: %s",
        message
    )

    try:

        # ----------------------------------------------------
        # Parse message
        # ----------------------------------------------------

        plan_request = json.loads(
            message
        )

        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        request_id = plan_request.get(
            "request_id"
        )

        terraform_directory = plan_request.get(
            "terraform_directory"
        )

        decision = plan_request.get(
            "decision"
        )

        if not request_id:
            raise ValueError(
                "Missing required field: request_id"
            )

        if not terraform_directory:
            raise ValueError(
                "Missing required field: terraform_directory"
            )

        if not decision:
            raise ValueError(
                "Missing required field: decision"
            )

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        request_id = str(
            request_id
        ).strip()

        terraform_directory = str(
            terraform_directory
        ).strip()

        decision = str(
            decision
        ).strip().upper()

        # ----------------------------------------------------
        # Validate decision
        # ----------------------------------------------------

        if decision != "APPROVED":
            raise ValueError(
                "Terraform plan requires "
                "decision APPROVED"
            )

        logging.info(
            "Terraform plan request validated: %s",
            json.dumps(
                {
                    "request_id": request_id,
                    "terraform_directory":
                        terraform_directory,
                    "decision": decision
                },
                ensure_ascii=False
            )
        )

        # ----------------------------------------------------
        # Generate Terraform PLAN
        # ----------------------------------------------------

        result = generate_terraform_plan(
            request_id=request_id,
            terraform_directory=terraform_directory
        )

        # ----------------------------------------------------
        # Audit Terraform PLAN generation
        # ----------------------------------------------------

        write_audit_event(
            request_id=result.request_id,
            stage="terraform_plan",
            status="terraform_plan_generated",
            actor="system",
            message="Terraform plan generated successfully"
        )

        # ----------------------------------------------------
        # Log result
        # ----------------------------------------------------

        logging.info(
            "Terraform plan generated successfully: %s",
            result.request_id
        )

        logging.info(
            "Terraform plan result: %s",
            json.dumps(
                {
                    "request_id":
                        result.request_id,

                    "status":
                        result.status,

                    "working_directory":
                        result.working_directory,

                    "plan_file":
                        result.plan_file,

                    "plan_text_file":
                        result.plan_text_file,

                    "message":
                        result.message
                },
                ensure_ascii=False
            )
        )

        # ----------------------------------------------------
        # Send result to terraform-plan queue
        # ----------------------------------------------------

        connection_string = os.environ[
            "AzureWebJobsStorage"
        ]

        plan_queue = QueueClient.from_connection_string(
            conn_str=connection_string,
            queue_name="terraform-plan"
        )

        plan_message = {

            "request_id":
                result.request_id,

            "status":
                result.status,

            "working_directory":
                result.working_directory,

            "plan_file":
                result.plan_file,

            "plan_text_file":
                result.plan_text_file,

            "plan_output":
                result.plan_output,

            "message":
                result.message
        }

        plan_queue.send_message(
            json.dumps(
                plan_message,
                ensure_ascii=False
            )
        )

        logging.info(
            "Terraform plan result sent to "
            "terraform-plan queue: %s",
            result.request_id
        )

    except json.JSONDecodeError as exc:

        logging.error(
            "Invalid Terraform plan JSON: %s",
            message
        )

        logging.error(
            "JSON error: %s",
            exc
        )

        raise

    except ValueError as exc:

        logging.error(
            "Invalid Terraform plan request: %s",
            exc
        )

        raise

    except Exception as exc:

        logging.exception(
            "Unexpected error during Terraform plan: %s",
            exc
        )

        raise



# ============================================================
# 7. APPLY TERRAFORM
# ============================================================

@app.function_name(name="apply_terraform")
@app.queue_trigger(
    arg_name="msg",
    queue_name="terraform-apply-request",
    connection="AzureWebJobsStorage"
)
def apply_terraform_function(
    msg: func.QueueMessage
) -> None:

    message = decode_queue_message(msg)

    logging.info(
        "Terraform apply request received: %s",
        message
    )

    terraform_apply_completed = False

    try:
        
        # ----------------------------------------------------
        # Parse message
        # ----------------------------------------------------

        apply_request = json.loads(
            message
        )

        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        request_id = apply_request.get(
            "request_id"
        )

        terraform_directory = apply_request.get(
            "terraform_directory"
        )

        decision = apply_request.get(
            "decision"
        )

        if not request_id:
            raise ValueError(
                "Missing required field: request_id"
            )

        if not terraform_directory:
            raise ValueError(
                "Missing required field: terraform_directory"
            )

        if not decision:
            raise ValueError(
                "Missing required field: decision"
            )

        # ----------------------------------------------------
        # Normalize
        # ----------------------------------------------------

        request_id = str(
            request_id
        ).strip()

        terraform_directory = str(
            terraform_directory
        ).strip()

        decision = str(
            decision
        ).strip().upper()

        # ----------------------------------------------------
        # Validate approval
        # ----------------------------------------------------

        if decision != "APPROVED":

            raise ValueError(
                "Terraform apply requires "
                "decision APPROVED"
            )

        logging.info(
            "Terraform apply request approved: %s",
            json.dumps(
                {
                    "request_id":
                        request_id,

                    "terraform_directory":
                        terraform_directory,

                    "decision":
                        decision
                },
                ensure_ascii=False
            )
        )

        write_audit_event(
            request_id=request_id,
            stage="terraform_apply",
            status="terraform_apply_started",
            actor="system",
            message="Terraform apply started"
        )

        # ----------------------------------------------------
        # Apply previously generated plan
        # ----------------------------------------------------

        result = apply_terraform(
            request_id=request_id,
            terraform_directory=terraform_directory
        )

        if result.status == "terraform_applied":
            terraform_apply_completed = True

        connection_string = os.environ[
            "AzureWebJobsStorage"
        ]

        # ----------------------------------------------------
        # Log result
        # ----------------------------------------------------

        logging.info(
            "Terraform apply result: %s",
            json.dumps(
                {
                    "request_id":
                        result.request_id,

                    "status":
                        result.status,

                    "working_directory":
                        result.working_directory,

                    "message":
                        result.message
                },
                ensure_ascii=False
            )
        )

              # ----------------------------------------------------
        # Handle stale Terraform plan
        # ----------------------------------------------------

        if result.status == "terraform_plan_stale":

            logging.warning(
                "Terraform plan is stale. "
                "Generating a new plan request: %s",
                result.request_id
            )

            plan_request_queue = (
                QueueClient.from_connection_string(
                    conn_str=connection_string,
                    queue_name="terraform-plan-request"
                )
            )

            plan_request_message = {

                "request_id":
                    result.request_id,

                "terraform_directory":
                    result.working_directory,

                "decision":
                    "APPROVED",

                "reason":
                    "terraform_plan_stale"
            }

            plan_request_queue.send_message(
                json.dumps(
                    plan_request_message,
                    ensure_ascii=False
                )
            )

            logging.info(
                "New Terraform plan requested because "
                "the previous plan was stale: %s",
                result.request_id
            )

            return

        write_audit_event(
            request_id=result.request_id,
            stage="terraform_apply",
            status="terraform_applied",
            actor="system",
            message="Terraform apply completed successfully"
        )

        # ----------------------------------------------------
        # Send successful apply result to terraform-apply
        # ----------------------------------------------------

        apply_queue = QueueClient.from_connection_string(
            conn_str=connection_string,
            queue_name="terraform-apply"
        )

        apply_message = {

            "request_id":
                result.request_id,

            "status":
                result.status,

            "working_directory":
                result.working_directory,

            "apply_output":
                result.apply_output,

            "terraform_outputs":
                result.terraform_outputs,

            "message":
                result.message
        }

        apply_queue.send_message(
            json.dumps(
                apply_message,
                ensure_ascii=False
            )
        )

        logging.info(
            "Terraform apply result sent to "
            "terraform-apply queue: %s",
            result.request_id
        )

    except ValueError as exc:

        logging.error(
            "Invalid Terraform apply request: %s",
            exc
        )

        raise

    except Exception as exc:

        if not terraform_apply_completed:

            write_audit_event(
                request_id=request_id,
                stage="terraform_apply",
                status="terraform_apply_failed",
                actor="system",
                message=f"Terraform apply failed: {exc}"
            )

        else:

            logging.error(
                "Terraform apply completed successfully, "
                "but post-apply processing failed: %s",
                exc
            )

        logging.exception(
            "Terraform apply processing failed: %s",
            exc
        )

        raise


# ============================================================
# PROCESS TERRAFORM RESULT
# ============================================================

@app.function_name(name="process_terraform_result")
@app.queue_trigger(
    arg_name="msg",
    queue_name="terraform-apply",
    connection="AzureWebJobsStorage"
)
def process_terraform_result(
    msg: func.QueueMessage
) -> None:

    message = decode_queue_message(msg)

    logging.info(
        "Terraform result received: %s",
        message
    )

    try:

        # ----------------------------------------------------
        # Parse JSON
        # ----------------------------------------------------

        result = json.loads(
            message
        )

        # ----------------------------------------------------
        # Read required fields
        # ----------------------------------------------------

        request_id = result.get(
            "request_id"
        )

        status = result.get(
            "status"
        )

        working_directory = result.get(
            "working_directory"
        )

        terraform_outputs = result.get(
            "terraform_outputs",
            {}
        )

        apply_output = result.get(
            "apply_output",
            ""
        )

        # ----------------------------------------------------
        # Validate required fields
        # ----------------------------------------------------

        if not request_id:

            raise ValueError(
                "Missing required field: request_id"
            )

        if not status:

            raise ValueError(
                "Missing required field: status"
            )

        # ----------------------------------------------------
        # Normalize values
        # ----------------------------------------------------

        request_id = str(
            request_id
        ).strip()

        status = str(
            status
        ).strip().lower()

        working_directory = str(
            working_directory or ""
        ).strip()

        # ----------------------------------------------------
        # Validate Terraform result
        # ----------------------------------------------------

        if status != "terraform_applied":

            raise ValueError(
                "Expected terraform_applied status, "
                f"received: {status}"
            )

        # ----------------------------------------------------
        # Validate Terraform outputs
        # ----------------------------------------------------

        if not isinstance(
            terraform_outputs,
            dict
        ):

            raise ValueError(
                "terraform_outputs must be a JSON object"
            )

        logging.info(
            "Terraform deployment completed: %s",
            json.dumps(
                {
                    "request_id": request_id,
                    "status": status,
                    "terraform_outputs":
                        terraform_outputs
                },
                ensure_ascii=False
            )
        )

        # ----------------------------------------------------
        # Build final deployment result
        # ----------------------------------------------------

        deployment_result = {

            "request_id":
                request_id,

            "status":
                "deployment_completed",

            "working_directory":
                working_directory,

            "terraform_outputs":
                terraform_outputs,

            "apply_output":
                apply_output,

            "message":
                "Azure infrastructure deployment "
                "completed successfully."
        }

        # ----------------------------------------------------
        # Send final deployment result
        # ----------------------------------------------------

        connection_string = os.environ[
            "AzureWebJobsStorage"
        ]

        deployment_queue = QueueClient.from_connection_string(
            conn_str=connection_string,
            queue_name="deployment-results"
        )

        deployment_queue.send_message(
            json.dumps(
                deployment_result,
                ensure_ascii=False
            )
        )

        logging.info(
            "Deployment result sent successfully: %s",
            request_id
        )
        write_audit_event(
            request_id=request_id,
            stage="deployment",
            status="deployment_completed",
            actor="system",
            message="Azure infrastructure deployment completed successfully"
        )

    except json.JSONDecodeError:

        logging.error(
            "Invalid Terraform result JSON: %s",
            message
        )

        raise

    except ValueError as exc:

        logging.error(
            "Invalid Terraform result: %s",
            exc
        )

        raise

    except Exception as exc:

        logging.exception(
            "Unexpected error processing Terraform result: %s",
            exc
        )

        raise
