# Azure Infrastructure Agent

Azure Infrastructure Agent is an automation workflow for processing Azure infrastructure requests, generating and reviewing architectures, generating Terraform configurations, creating Terraform plans, obtaining human approval, and deploying approved infrastructure.

## Architecture

The project is composed of three main areas:

- `function/` — Azure Functions that implement the infrastructure workflow.
- `approval-api/` — FastAPI application used for human approval of architecture and Terraform plans.
- `terraform/bootstrap/` — Terraform configuration used to provision the Azure Function infrastructure.

## Workflow

The intended end-to-end workflow is:

1. An Azure infrastructure request is placed in `infrastructure-requests`.
2. The request is analyzed and validated.
3. An architecture is generated.
4. The architecture is reviewed.
5. The architecture is sent to `architecture-approval`.
6. A human reviewer approves or rejects the architecture.
7. Approved architectures are sent to `terraform-generation`.
8. Terraform configuration is generated.
9. A Terraform plan is generated.
10. The Terraform plan is presented for human approval.
11. A human reviewer approves or rejects the Terraform plan.
12. An approved plan is sent to `terraform-apply-request`.
13. Terraform applies the approved plan.
14. The deployment result is sent to `deployment-results`.
15. Audit events are written to `audit-events`.

## Azure Storage Queues

The workflow uses Azure Storage Queues for asynchronous communication between stages.

Important queues include:

- `infrastructure-requests`
- `architecture-review`
- `architecture-approval`
- `terraform-generation`
- `terraform-plan-request`
- `terraform-apply-request`
- `deployment-results`
- `audit-events`

Poison queues are used by Azure Functions for messages that exceed the configured dequeue retry limit.

## Human Approval

The `approval-api` project provides an Approval Center for two human approval stages:

### Architecture approval

An architecture can be:

- Approved — the workflow continues to Terraform generation.
- Rejected — Terraform generation is skipped.

### Terraform plan approval

A Terraform plan can be:

- Approved — the workflow continues to Terraform apply.
- Rejected — Terraform apply is skipped.

The API is implemented with FastAPI and provides endpoints for retrieving pending approvals and approving or rejecting them.

## Audit Trail

The workflow records significant state transitions in the `audit-events` queue.

Examples include:

- `infrastructure_request_received`
- `architecture_review_completed`
- `architecture_approval_pending`
- `architecture_approved`
- `architecture_rejected`
- `terraform_generated`
- `terraform_plan_generated`
- `terraform_plan_approved`
- `terraform_plan_rejected`
- `terraform_apply_started`
- `terraform_apply_failed`
- `terraform_plan_stale`
- `terraform_applied`
- `deployment_completed`

Human decisions are recorded with `actor: human`, while automated workflow transitions use `actor: system`.

## Error Handling

The workflow includes explicit handling for important failure conditions.

### Architecture rejection

A rejected architecture terminates the infrastructure deployment path before Terraform generation.

### Terraform plan rejection

A rejected Terraform plan prevents Terraform apply and deployment.

### Terraform apply failure

Terraform apply failures are recorded as:

`terraform_apply_failed`

A failed apply must not produce:

- `terraform_applied`
- `deployment_completed`

### Stale Terraform plan

If Terraform reports that a saved plan is stale, the workflow records the stale-plan condition and requests generation of a new Terraform plan.

The regenerated plan requires human approval again before it can be applied.

## Project Structure

```text
azure-infra-agent/
├── approval-api/
│   ├── audit.py
│   └── main.py
├── function/
│   ├── architecture_generator.py
│   ├── architecture_reviewer.py
│   ├── audit.py
│   ├── function_app.py
│   ├── host.json
│   ├── request_analyzer.py
│   ├── requirements.txt
│   ├── terraform_generator.py
│   └── terraform_runner.py
├── terraform/
│   └── bootstrap/
│       ├── .terraform.lock.hcl
│       ├── function_app.tf
│       ├── main.tf
│       ├── outputs.tf
│       ├── variables.tf
│       └── versions.tf
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md