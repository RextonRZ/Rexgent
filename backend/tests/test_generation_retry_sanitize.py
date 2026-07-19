"""A content-inspection failure retried with the SAME prompt just fails
again — one cheap sanitize rewrite gives the retry a real chance."""
from app.services.generation_runner import is_inspection_error


def test_inspection_errors_recognized():
    assert is_inspection_error(RuntimeError("DataInspectionFailed: bad")) is True
    assert is_inspection_error(RuntimeError("IPInfringementSuspect")) is True
    assert is_inspection_error(RuntimeError("429 Throttling")) is False
