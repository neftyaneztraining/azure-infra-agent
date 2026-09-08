import json
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logging.info("APPROVAL API LOGGING INITIALIZED")

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from azure.storage.queue import QueueClient

from audit import write_audit_event

app = FastAPI(
    title="Azure Infrastructure Approval API",
    description="API para gestionar aprobaciones de infraestructura Azure.",
    version="0.3.0"
)


# ============================================================
# QUEUES
# ============================================================

QUEUE_NAME = "architecture-approval"

TERRAFORM_QUEUE_NAME = "terraform-generation"

TERRAFORM_PLAN_QUEUE_NAME = "terraform-plan"

TERRAFORM_APPLY_REQUEST_QUEUE_NAME = "terraform-apply-request"


# ============================================================
# QUEUE CLIENT
# ============================================================

def get_queue_client(queue_name: str) -> QueueClient:

    connection_string = os.environ.get(
        "AzureWebJobsStorage"
    )

    if not connection_string:

        raise HTTPException(
            status_code=500,
            detail="AzureWebJobsStorage is not configured"
        )

    return QueueClient.from_connection_string(
        conn_str=connection_string,
        queue_name=queue_name
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    logging.info(
        "APPROVAL API HEALTH LOG TEST"
    )

    return {
        "status": "ok",
        "service": "approval-api"
    }


# ============================================================
# APPROVAL UI
# ============================================================

@app.get("/", response_class=HTMLResponse)
def approval_ui():

    return """
<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Azure Infrastructure Approval Center</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
            background: #f3f4f6;
            color: #111827;
        }

        header {
            background: #111827;
            color: white;
            padding: 24px 32px;
        }

        header h1 {
            margin: 0;
            font-size: 24px;
        }

        header p {
            margin: 6px 0 0;
            color: #d1d5db;
        }

        main {
            max-width: 1200px;
            margin: 30px auto;
            padding: 0 20px;
        }

        .section {
            margin-bottom: 40px;
        }

        .section-title {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 16px;
        }

        .cards {
            display: grid;
            grid-template-columns:
                repeat(
                    auto-fit,
                    minmax(320px, 1fr)
                );
            gap: 20px;
        }

        .card {
            background: white;
            border-radius: 12px;
            padding: 22px;
            box-shadow:
                0 2px 8px rgba(0, 0, 0, 0.08);
            border: 1px solid #e5e7eb;
        }

        .card h3 {
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 18px;
        }

        .request-id {
            font-family: monospace;
            font-size: 13px;
            color: #4b5563;
            background: #f3f4f6;
            padding: 6px 8px;
            border-radius: 6px;
            display: inline-block;
        }

        .metadata {
            margin: 16px 0;
        }

        .metadata div {
            margin: 7px 0;
        }

        .label {
            font-weight: 600;
        }

        .badge {
            display: inline-block;
            padding: 5px 9px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
        }

        .badge-pending {
            background: #fef3c7;
            color: #92400e;
        }

        .badge-approve {
            background: #dcfce7;
            color: #166534;
        }

        .resources {
            margin-top: 15px;
            padding-left: 0;
            list-style: none;
        }

        .resources li {
            padding: 6px 0;
        }

        .resources li::before {
            content: "âœ“";
            color: #16a34a;
            font-weight: bold;
            margin-right: 8px;
        }

        .request {
            background: #f9fafb;
            border-left: 4px solid #6b7280;
            padding: 12px;
            margin-top: 15px;
            white-space: pre-wrap;
        }

        .comments {
            margin-top: 15px;
            background: #f9fafb;
            padding: 12px;
            border-radius: 8px;
        }

        .actions {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }

        button {
            border: none;
            border-radius: 8px;
            padding: 11px 18px;
            font-weight: 700;
            cursor: pointer;
            font-size: 14px;
        }

        .approve {
            background: #16a34a;
            color: white;
        }

        .approve:hover {
            background: #15803d;
        }

        .reject {
            background: #dc2626;
            color: white;
        }

        .reject:hover {
            background: #b91c1c;
        }

        .refresh {
            background: #2563eb;
            color: white;
            margin-bottom: 20px;
        }

        .refresh:hover {
            background: #1d4ed8;
        }

        .empty {
            background: white;
            border: 1px dashed #d1d5db;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            color: #6b7280;
        }

        .plan-output {
            background: #111827;
            color: #e5e7eb;
            padding: 15px;
            border-radius: 8px;
            margin-top: 15px;
            overflow-x: auto;
            white-space: pre-wrap;
            font-family: Consolas, monospace;
            font-size: 12px;
            max-height: 400px;
            overflow-y: auto;
        }

        .status {
            margin-bottom: 20px;
            padding: 12px 15px;
            border-radius: 8px;
            display: none;
        }

        .status.success {
            display: block;
            background: #dcfce7;
            color: #166534;
        }

        .status.error {
            display: block;
            background: #fee2e2;
            color: #991b1b;
        }

        @media (max-width: 600px) {

            header {
                padding: 20px;
            }

            main {
                margin: 20px auto;
            }

            .actions {
                flex-direction: column;
            }

            button {
                width: 100%;
            }
        }

    </style>

</head>


<body>

<header>

    <h1>
        Azure Infrastructure Approval Center
    </h1>

    <p>
        Human approval workflow for Azure infrastructure
    </p>

</header>


<main>

    <button
        class="refresh"
        onclick="loadAll()"
    >
        Refresh
    </button>


    <div
        id="status"
        class="status"
    ></div>


    <!-- ====================================================
         ARCHITECTURE APPROVAL
         ==================================================== -->

    <section class="section">

        <div class="section-title">
            Architecture Approval
        </div>

        <div
            id="architecture-container"
            class="cards"
        ></div>

    </section>


    <!-- ====================================================
         TERRAFORM PLAN APPROVAL
         ==================================================== -->

    <section class="section">

        <div class="section-title">
            Terraform Plan Approval
        </div>

        <div
            id="terraform-container"
            class="cards"
        ></div>

    </section>

</main>


<script>

    function escapeHtml(value) {

        if (value === null || value === undefined) {
            return "";
        }

        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }


    function showStatus(
        message,
        type
    ) {

        const element =
            document.getElementById("status");

        element.textContent = message;

        element.className =
            "status " + type;

        setTimeout(
            () => {
                element.className = "status";
            },
            5000
        );
    }


    async function loadArchitectureApprovals() {

        const container =
            document.getElementById(
                "architecture-container"
            );

        container.innerHTML =
            "<div class='empty'>Loading...</div>";

        try {

            const response =
                await fetch("/approvals");

            if (!response.ok) {
                throw new Error(
                    "HTTP " + response.status
                );
            }

            const data =
                await response.json();

            if (
                !data.approvals ||
                data.approvals.length === 0
            ) {

                container.innerHTML =
                    "<div class='empty'>" +
                    "No architecture approvals pending." +
                    "</div>";

                return;
            }


            container.innerHTML =
                data.approvals.map(
                    item => {

                        const content =
                            item.content || {};

                        const resources =
                            Array.isArray(
                                content.resources
                            )
                            ? content.resources
                            : [];


                        return `

<div class="card">

    <h3>
        ${escapeHtml(
            content.architecture_type ||
            "Architecture"
        )}
    </h3>

    <span class="request-id">
        ${escapeHtml(
            content.request_id
        )}
    </span>


    <div class="metadata">

        <div>
            <span class="label">
                Environment:
            </span>

            ${escapeHtml(
                content.environment ||
                "unknown"
            )}
        </div>


        <div>

            <span class="label">
                Status:
            </span>

            <span class="badge badge-pending">
                ${escapeHtml(
                    content.status ||
                    "pending_approval"
                )}
            </span>

        </div>


        <div>

            <span class="label">
                AI Recommendation:
            </span>

            <span class="badge badge-approve">
                ${escapeHtml(
                    content.recommendation ||
                    "N/A"
                )}
            </span>

        </div>

    </div>


    <div>

        <span class="label">
            Resources:
        </span>

        <ul class="resources">

            ${
                resources.length
                ? resources.map(
                    resource =>
                        `<li>${escapeHtml(
                            resource
                        )}</li>`
                ).join("")
                : "<li>No resources listed</li>"
            }

        </ul>

    </div>


    ${
        content.request
        ? `
        <div class="request">
            <strong>Request</strong><br>
            ${escapeHtml(
                content.request
            )}
        </div>
        `
        : ""
    }


    ${
        Array.isArray(content.comments) &&
        content.comments.length
        ? `
        <div class="comments">

            <strong>
                Review comments
            </strong>

            <ul>
                ${
                    content.comments.map(
                        comment =>
                            `<li>${escapeHtml(
                                comment
                            )}</li>`
                    ).join("")
                }
            </ul>

        </div>
        `
        : ""
    }


    <div class="actions">

        <button
            class="approve"
            onclick="approveArchitecture(
                '${escapeHtml(
                    content.request_id
                )}'
            )"
        >
            APPROVE
        </button>


        <button
            class="reject"
            onclick="rejectArchitecture(
                '${escapeHtml(
                    content.request_id
                )}'
            )"
        >
            REJECT
        </button>

    </div>

</div>

                        `;

                    }
                ).join("");

        } catch (error) {

            container.innerHTML =
                "<div class='empty'>" +
                "Error loading approvals: " +
                escapeHtml(error.message) +
                "</div>";
        }
    }


    async function loadTerraformPlans() {

        const container =
            document.getElementById(
                "terraform-container"
            );

        container.innerHTML =
            "<div class='empty'>Loading...</div>";

        try {

            const response =
                await fetch("/terraform-plans");

            if (!response.ok) {
                throw new Error(
                    "HTTP " + response.status
                );
            }

            const data =
                await response.json();

            if (
                !data.plans ||
                data.plans.length === 0
            ) {

                container.innerHTML =
                    "<div class='empty'>" +
                    "No Terraform plans pending." +
                    "</div>";

                return;
            }


            container.innerHTML =
                data.plans.map(
                    item => {

                        const content =
                            item.content || {};


                        return `

<div class="card">

    <h3>
        Terraform Plan
    </h3>

    <span class="request-id">
        ${escapeHtml(
            content.request_id
        )}
    </span>


    <div class="metadata">

        <div>

            <span class="label">
                Status:
            </span>

            <span class="badge badge-pending">
                ${escapeHtml(
                    content.status ||
                    "unknown"
                )}
            </span>

        </div>


        <div>

            <span class="label">
                Working directory:
            </span>

            <br>

            <code>
                ${escapeHtml(
                    content.working_directory ||
                    "N/A"
                )}
            </code>

        </div>


        <div>

            <span class="label">
                Plan file:
            </span>

            <br>

            <code>
                ${escapeHtml(
                    content.plan_file ||
                    "N/A"
                )}
            </code>

        </div>

    </div>


    ${
        content.plan_output
        ? `
        <div class="plan-output">
            ${escapeHtml(
                content.plan_output
            )}
        </div>
        `
        : ""
    }


    <div class="actions">

        <button
            class="approve"
            onclick="approveTerraformPlan(
                '${escapeHtml(
                    content.request_id
                )}'
            )"
        >
            APPROVE PLAN
        </button>


        <button
            class="reject"
            onclick="rejectTerraformPlan(
                '${escapeHtml(
                    content.request_id
                )}'
            )"
        >
            REJECT PLAN
        </button>

    </div>

</div>

                        `;

                    }
                ).join("");

        } catch (error) {

            container.innerHTML =
                "<div class='empty'>" +
                "Error loading Terraform plans: " +
                escapeHtml(error.message) +
                "</div>";
        }
    }


    async function approveArchitecture(
        requestId
    ) {

        if (
            !confirm(
                "Approve architecture " +
                requestId +
                "?"
            )
        ) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/approvals/" +
                    encodeURIComponent(
                        requestId
                    ) +
                    "/approve",
                    {
                        method: "POST"
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Approval failed"
                );
            }


            showStatus(
                "Architecture approved: " +
                requestId,
                "success"
            );


            await loadAll();

        } catch (error) {

            showStatus(
                error.message,
                "error"
            );
        }
    }


    async function rejectArchitecture(
        requestId
    ) {

        if (
            !confirm(
                "Reject architecture " +
                requestId +
                "?"
            )
        ) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/approvals/" +
                    encodeURIComponent(
                        requestId
                    ) +
                    "/reject",
                    {
                        method: "POST"
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Rejection failed"
                );
            }


            showStatus(
                "Architecture rejected: " +
                requestId,
                "success"
            );


            await loadAll();

        } catch (error) {

            showStatus(
                error.message,
                "error"
            );
        }
    }


    async function approveTerraformPlan(
        requestId
    ) {

        if (
            !confirm(
                "Approve Terraform plan " +
                requestId +
                " and allow deployment?"
            )
        ) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/terraform-plans/" +
                    encodeURIComponent(
                        requestId
                    ) +
                    "/approve",
                    {
                        method: "POST"
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Terraform approval failed"
                );
            }


            showStatus(
                "Terraform plan approved: " +
                requestId,
                "success"
            );


            await loadAll();

        } catch (error) {

            showStatus(
                error.message,
                "error"
            );
        }
    }


    async function rejectTerraformPlan(
        requestId
    ) {

        if (
            !confirm(
                "Reject Terraform plan " +
                requestId +
                "?"
            )
        ) {
            return;
        }


        try {

            const response =
                await fetch(
                    "/terraform-plans/" +
                    encodeURIComponent(
                        requestId
                    ) +
                    "/reject",
                    {
                        method: "POST"
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    "Terraform rejection failed"
                );
            }


            showStatus(
                "Terraform plan rejected: " +
                requestId,
                "success"
            );


            await loadAll();

        } catch (error) {

            showStatus(
                error.message,
                "error"
            );
        }
    }


    async function loadAll() {

        await Promise.all([
            loadArchitectureApprovals(),
            loadTerraformPlans()
        ]);

    }


    loadAll();

</script>

</body>

</html>
"""


# ============================================================
# ARCHITECTURE APPROVAL API
# ============================================================

@app.get("/approvals")
def get_approvals():

    queue_client = get_queue_client(
        QUEUE_NAME
    )

    approvals = []

    try:

        messages = queue_client.peek_messages(
            max_messages=32
        )

        for message in messages:

            try:

                content = json.loads(
                    message.content
                )

            except json.JSONDecodeError:

                content = message.content

            approvals.append({

                "message_id":
                    message.id,

                "content":
                    content
            })

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error reading approval queue: "
                f"{exc}"
            )
        )

    return {

        "count":
            len(approvals),

        "approvals":
            approvals
    }


@app.post("/approvals/{request_id}/approve")
def approve_architecture(
    request_id: str
):

    approval_queue = get_queue_client(
        QUEUE_NAME
    )

    terraform_queue = get_queue_client(
        TERRAFORM_QUEUE_NAME
    )

    try:

        messages = approval_queue.receive_messages(
            max_messages=32
        )

        target_message = None
        target_content = None

        for message in messages:

            try:

                content = json.loads(
                    message.content
                )

            except json.JSONDecodeError:

                continue

            if content.get(
                "request_id"
            ) == request_id:

                target_message = message
                target_content = content

                break

        if not target_message:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Approval not found: "
                    f"{request_id}"
                )
            )

        terraform_request = {

            "request_id":
                request_id,

            "decision":
                "APPROVED",

            "comments":
                "Architecture approved by human reviewer.",

            "environment":
                target_content.get(
                    "environment",
                    "dev"
                ),

            "request":
                target_content.get(
                    "request",
                    ""
                ),

            "architecture_type":
                target_content.get(
                    "architecture_type",
                    ""
                ),

            "resources":
                target_content.get(
                    "resources",
                    []
                )
        }

        terraform_queue.send_message(
            json.dumps(
                terraform_request,
                ensure_ascii=False
            )
        )

        approval_queue.delete_message(
            target_message
        )

        logging.info(
            "BEFORE ARCHITECTURE APPROVAL AUDIT: %s",
            request_id
        )

        write_audit_event(
            request_id=request_id,
            stage="architecture_approval",
            status="architecture_approved",
            actor="human",
            decision="APPROVED",
            message=(
                "Architecture approved by human reviewer "
                "and sent to terraform-generation."
            )
        )

        logging.info(
            "AFTER ARCHITECTURE APPROVAL AUDIT: %s",
            request_id
        )

        return {

            "status":
                "approved",

            "request_id":
                request_id,

            "message":
                (
                    "Architecture approved and "
                    "sent to terraform-generation."
                )
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error approving architecture: "
                f"{exc}"
            )
        )


@app.post("/approvals/{request_id}/reject")
def reject_architecture(
    request_id: str
):

    approval_queue = get_queue_client(
        QUEUE_NAME
    )

    try:

        messages = approval_queue.receive_messages(
            max_messages=32
        )

        target_message = None

        for message in messages:

            try:

                content = json.loads(
                    message.content
                )

            except json.JSONDecodeError:

                continue

            if content.get(
                "request_id"
            ) == request_id:

                target_message = message

                break

        if not target_message:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Approval not found: "
                    f"{request_id}"
                )
            )

        approval_queue.delete_message(
            target_message
        )

        write_audit_event(
            request_id=request_id,
            stage="architecture_approval",
            status="architecture_rejected",
            actor="human",
            decision="REJECTED",
            message=(
                "Architecture rejected by human reviewer. "
                "Terraform generation skipped."
            )
        )

        return {

            "status":
                "rejected",

            "request_id":
                request_id,

            "message":
                (
                    "Architecture rejected. "
                    "Terraform generation skipped."
                )
        }

        return {

            "status":
                "rejected",

            "request_id":
                request_id,

            "message":
                (
                    "Architecture rejected. "
                    "Terraform generation skipped."
                )
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error rejecting architecture: "
                f"{exc}"
            )
        )


# ============================================================
# TERRAFORM PLAN API
# ============================================================

@app.get("/terraform-plans")
def get_terraform_plans():

    queue_client = get_queue_client(
        TERRAFORM_PLAN_QUEUE_NAME
    )

    plans = []

    try:

        messages = queue_client.peek_messages(
            max_messages=32
        )

        for message in messages:

            try:

                content = json.loads(
                    message.content
                )

            except json.JSONDecodeError:

                content = message.content

            plans.append({

                "message_id":
                    message.id,

                "content":
                    content
            })

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error reading Terraform plan queue: "
                f"{exc}"
            )
        )

    return {

        "count":
            len(plans),

        "plans":
            plans
    }


@app.post(
    "/terraform-plans/{request_id}/approve"
)
def approve_terraform_plan(
    request_id: str
):

    plan_queue = get_queue_client(
        TERRAFORM_PLAN_QUEUE_NAME
    )

    apply_queue = get_queue_client(
        TERRAFORM_APPLY_REQUEST_QUEUE_NAME
    )

    try:

        messages = plan_queue.receive_messages(
            max_messages=32
        )

        target_message = None
        target_content = None

        for message in messages:

            try:

                content = json.loads(
                    message.content
                )

            except json.JSONDecodeError:

                continue

            if content.get(
                "request_id"
            ) == request_id:

                target_message = message
                target_content = content

                break

        if not target_message:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Terraform plan not found: "
                    f"{request_id}"
                )
            )

        plan_status = str(
            target_content.get(
                "status",
                ""
            )
        ).strip().lower()

        if plan_status != (
            "terraform_plan_generated"
        ):

            raise HTTPException(
                status_code=409,
                detail=(
                    "Terraform plan is not "
                    "ready for approval."
                )
            )

        working_directory = str(
            target_content.get(
                "working_directory",
                ""
            )
        ).strip()

        if not working_directory:

            raise HTTPException(
                status_code=409,
                detail=(
                    "Terraform plan is missing "
                    "working_directory."
                )
            )

        apply_request = {

            "request_id":
                request_id,

            "terraform_directory":
                working_directory,

            "decision":
                "APPROVED"
        }

        apply_queue.send_message(
            json.dumps(
                apply_request,
                ensure_ascii=False
            )
        )

        plan_queue.delete_message(
            target_message
        )

        write_audit_event(
            request_id=request_id,
            stage="terraform_plan",
            status="terraform_plan_approved",
            actor="human",
            decision="APPROVED",
            message=(
                "Terraform plan approved by human reviewer "
                "and sent to terraform-apply-request."
            )
        )

        return {

            "status":
                "approved",

            "request_id":
                request_id,

            "message":
                (
                    "Terraform plan approved and "
                    "sent to terraform-apply-request."
                )
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error approving Terraform plan: "
                f"{exc}"
            )
        )


@app.post(
    "/terraform-plans/{request_id}/reject"
)
def reject_terraform_plan(
    request_id: str
):

    plan_queue = get_queue_client(
        TERRAFORM_PLAN_QUEUE_NAME
    )

    try:

        messages = plan_queue.receive_messages(
            max_messages=32
        )

        target_message = None

        for message in messages:

            try:

                content = json.loads(
                    message.content
                )

            except json.JSONDecodeError:

                continue

            if content.get(
                "request_id"
            ) == request_id:

                target_message = message

                break

        if not target_message:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Terraform plan not found: "
                    f"{request_id}"
                )
            )

        plan_queue.delete_message(
            target_message
        )

        write_audit_event(
            request_id=request_id,
            stage="terraform_plan",
            status="terraform_plan_rejected",
            actor="human",
            decision="REJECTED",
            message=(
                "Terraform plan rejected by human reviewer. "
                "Terraform apply skipped."
            )
        )

        return {

            "status":
                "rejected",

            "request_id":
                request_id,

            "message":
                (
                    "Terraform plan rejected. "
                    "Terraform apply skipped."
                )
        }

    except HTTPException:

        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Error rejecting Terraform plan: "
                f"{exc}"
            )
        )