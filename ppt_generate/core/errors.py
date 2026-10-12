"""Stable machine-readable errors without echoing remote response bodies."""


def failure(error):
    if isinstance(error, FileNotFoundError):
        return {
            "success": False,
            "error": {"code": "not_found", "message": "Requested local file or job was not found"},
        }
    if isinstance(error, (ValueError, TypeError, KeyError)):
        message = str(error)
        result = {
            "success": False,
            "error": {
                "code": "conflict" if "revision conflict" in message else "invalid_input",
                "message": message,
            },
        }
        if getattr(error, "diagnostics", None):
            result["error"]["code"] = (
                "planning_timeout"
                if error.diagnostics.get("status") == "deadline_exceeded"
                else "quality_failed"
            )
            result["diagnostics"] = error.diagnostics
        return result
    if isinstance(error, PermissionError):
        return {
            "success": False,
            "error": {"code": "permission_denied", "message": "Local filesystem access denied"},
        }
    name = type(error).__name__
    if name == "PreviewUnavailable":
        code, message = "preview_unavailable", str(error)
    elif name in {"AuthenticationError", "PermissionDeniedError"}:
        code, message = "authentication", "Provider rejected credentials or access"
    elif name in {"APITimeoutError", "APIConnectionError", "RateLimitError", "InternalServerError"}:
        code, message = (
            "provider_unavailable",
            "Model provider is unavailable, timed out, or rate limited",
        )
    elif name == "Timeout":
        code, message = "job_busy", "Job is being edited; retry later"
    else:
        code, message = (
            "internal_error",
            "Operation failed; inspect local configuration and dependencies",
        )
    result = {"success": False, "error": {"code": code, "message": message}}
    if getattr(error, "diagnostics", None):
        result["diagnostics"] = error.diagnostics
    return result
