import hashlib
import json


def create_submission_key(
    student_id: int,
    context: str,
    client_submission_id: str | None,
    answers: dict[str, str],
) -> str:
    if client_submission_id:
        identity = {
            "studentId": student_id,
            "context": context,
            "clientSubmissionId": client_submission_id,
        }
    else:
        identity = {
            "studentId": student_id,
            "context": context,
            "answers": sorted(answers.items()),
        }
    serialized = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
