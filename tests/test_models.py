from app.models.error import ErrorBody, ErrorResponse


def test_error_body_with_details() -> None:
    body = ErrorBody(
        code="VALIDATION_ERROR", message="Invalid input", details={"field": "email"}
    )
    assert body.code == "VALIDATION_ERROR"
    assert body.message == "Invalid input"
    assert body.details == {"field": "email"}


def test_error_body_without_details() -> None:
    body = ErrorBody(code="NOT_FOUND", message="Resource not found")
    assert body.details is None


def test_error_response_envelope_shape() -> None:
    resp = ErrorResponse(error=ErrorBody(code="UNAUTHORIZED", message="Auth required"))
    data = resp.model_dump()
    assert data == {
        "error": {"code": "UNAUTHORIZED", "message": "Auth required", "details": None}
    }


def test_error_response_json_matches_api_contract() -> None:
    resp = ErrorResponse(
        error=ErrorBody(
            code="VALIDATION_ERROR",
            message="Invalid task data",
            details={"fields": [{"path": "email", "issue": "must be a valid email"}]},
        )
    )
    json_str = resp.model_dump_json()
    assert '"code":"VALIDATION_ERROR"' in json_str
    assert '"message":"Invalid task data"' in json_str
