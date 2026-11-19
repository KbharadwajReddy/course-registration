"""One-process REPL over a single RegistrationService."""

from __future__ import annotations

import shlex
import sys
from typing import TextIO

from registration.service import RegistrationService


class _Unparseable(Exception):
    """The line is not a command this REPL can dispatch."""


def _parse(line: str) -> tuple[str, list[str]]:
    try:
        parts = shlex.split(line, posix=True)
    except ValueError as exc:
        raise _Unparseable from exc
    if not parts:
        raise _Unparseable
    command, args = parts[0], parts[1:]
    expected = {
        "configure": 3,
        "enroll": 1,
        "drop": 1,
        "complete": 2,
        "inspect": 0,
        "quit": 0,
    }
    if command not in expected or len(args) != expected[command]:
        raise _Unparseable
    if command == "configure" and not _is_integer_token(args[1]):
        raise _Unparseable
    return command, args


def _is_integer_token(token: str) -> bool:
    if token.startswith("-"):
        token = token[1:]
    return token.isdigit() and token != ""


def _format(result: object) -> str:
    code = getattr(result.code, "value", str(result.code))
    if code == "updated":
        return f"updated promoted_count={result.promoted_count}"
    if code == "dropped":
        promoted = "null" if result.promoted_learner_id is None else result.promoted_learner_id
        return f"dropped promoted_learner_id={promoted}"
    if code == "ok":
        snapshot = result.snapshot
        enrolled = ",".join(snapshot.enrolled)
        waitlist = ",".join(snapshot.waitlist)
        return (
            f"ok offering={snapshot.offering_code} capacity={snapshot.capacity} "
            f"prerequisite={snapshot.prerequisite_course_code} "
            f"enrolled=[{enrolled}] waitlist=[{waitlist}] seats_open={snapshot.seats_open}"
        )
    return code


def _dispatch(service: RegistrationService, command: str, args: list[str]) -> object:
    if command == "configure":
        return service.configure(args[0], int(args[1]), args[2])
    if command == "enroll":
        return service.enroll(args[0])
    if command == "drop":
        return service.drop(args[0])
    if command == "complete":
        return service.record_completed_course(args[0], args[1])
    if command == "inspect":
        return service.inspect()
    raise _Unparseable


def run(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    service: RegistrationService | None = None,
) -> int:
    """Read commands until quit or EOF. Return 0 for a service answer, 2 if a line cannot be parsed."""
    source = sys.stdin if stdin is None else stdin
    output = sys.stdout if stdout is None else stdout
    registration = RegistrationService() if service is None else service
    while True:
        line = source.readline()
        if line == "":
            return 0
        if line.strip() == "":
            continue
        try:
            command, args = _parse(line)
        except _Unparseable:
            print("unparseable", file=output)
            return 2
        if command == "quit":
            return 0
        print(_format(_dispatch(registration, command, args)), file=output)


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
