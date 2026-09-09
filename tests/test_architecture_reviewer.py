from function.architecture_reviewer import review_architecture_request


def test_valid_architecture_is_approved():
    review = {
        "request_id": "review-001",
        "architecture_type": "Azure Storage",
        "resources": [
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Storage/storageAccounts/blobServices",
        ],
    }

    result = review_architecture_request(review)

    assert result.request_id == "review-001"
    assert result.architecture_type == "Azure Storage"
    assert result.resources == review["resources"]
    assert result.status == "pending_approval"
    assert result.recommendation == "APPROVE"
    assert result.comments == [
        "Architecture contains the required structural components "
        "for initial review."
    ]


def test_missing_architecture_type_is_rejected():
    review = {
        "request_id": "review-002",
        "architecture_type": "",
        "resources": ["Microsoft.Storage/storageAccounts"],
    }

    result = review_architecture_request(review)

    assert result.recommendation == "REJECT"
    assert "Missing architecture type." in result.comments
    assert "No Azure resources were defined." not in result.comments


def test_missing_resources_is_rejected():
    review = {
        "request_id": "review-003",
        "architecture_type": "Azure Storage",
        "resources": [],
    }

    result = review_architecture_request(review)

    assert result.recommendation == "REJECT"
    assert "No Azure resources were defined." in result.comments
    assert "Missing architecture type." not in result.comments


def test_missing_architecture_type_and_resources_is_rejected():
    review = {
        "request_id": "review-004",
        "architecture_type": "",
        "resources": [],
    }

    result = review_architecture_request(review)

    assert result.recommendation == "REJECT"
    assert "Missing architecture type." in result.comments
    assert "No Azure resources were defined." in result.comments
    assert len(result.comments) == 2
