from .schema import AttemptState, HookResult, HookStatus, OperationRecord
from .validation import identifier


def parse_operation(raw: object, scope: str) -> OperationRecord:
    if not isinstance(raw, dict) or raw.get("scope") != scope:
        raise ValueError("Invalid operation scope")
    request = identifier(raw.get("request"), "operation request")
    policy = identifier(raw.get("policy"), "operation policy")
    result = raw.get("result")
    if not isinstance(result, dict):
        raise TypeError("Invalid operation result")
    status = HookStatus(identifier(result.get("status"), "operation status"))
    reason = identifier(result.get("reason"), "operation reason")
    completed = raw.get("completed")
    files = raw.get("files")
    if type(completed) is not bool or not isinstance(files, dict):
        raise ValueError("Invalid operation completion or file fingerprints")
    if not completed and status in (HookStatus.PASS, HookStatus.CHECK_FAILED):
        raise ValueError("Verification outcome has no completion marker")
    if status == HookStatus.PASS and not files:
        raise ValueError("PASS has no verified file coverage")
    if completed and status == HookStatus.PREPARED:
        raise ValueError("Preparation is not a completed verification")
    for name, fingerprint in files.items():
        identifier(name, "operation file")
        if fingerprint is not None and (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            raise ValueError("Invalid operation file fingerprint")
    return OperationRecord(
        scope, request, policy, HookResult(status, reason), completed, files
    )


def parse_attempts(raw: object, scope: str) -> AttemptState:
    if not isinstance(raw, dict):
        raise TypeError("Invalid retry state: expected an object")
    version = raw.get("schema_version", 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Unsupported retry state version")
    count = raw.get("consecutive_failed_attempts")
    if type(count) is not int or count < 0:
        raise ValueError("Invalid retry state: consecutive_failed_attempts")
    failure = raw["last_failure"]
    if count > 0:
        identifier(failure, "retry state last_failure")
    elif failure is not None and not isinstance(failure, str):
        raise ValueError("Invalid retry state: last_failure")
    operations = raw.get("operations", {})
    if not isinstance(operations, dict):
        raise TypeError("Invalid operation records")
    return AttemptState(
        count,
        failure,
        {
            identifier(key, "operation id"): parse_operation(value, scope)
            for key, value in operations.items()
        },
    )
