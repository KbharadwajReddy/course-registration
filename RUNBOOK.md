# Runbook

In-memory Python service and command-line REPL for one course offering. The service enrolls a learner, waitlists an eligible learner when the offering is full, and promotes the earliest eligible waiter when a seat opens. Behavior is defined in `specs/charter-and-persona.md`, `specs/architecture.md`, and `specs/intent.md`.

Runtime code uses only the Python standard library. Tests use pytest.

## Setup

Python 3.12 or newer is required.

```powershell
python --version
python -m pip install pytest
```

Run the commands from the repository root so `registration` imports as a package.

## Run the CLI

The REPL keeps one `RegistrationService` for the life of the process. Quitting, or closing the terminal, discards the roster.

```powershell
python -m registration.cli
```

The prompt is written to stderr. Each service answer is one line on stdout. A business refusal is still an answer, and the process exits 0. A line that is not a known command, or that has the wrong arguments, prints `unparseable` and exits 2 without calling the service. A blank line is ignored.

| Command | Arguments | Service call |
|---|---|---|
| `configure` | offering code, capacity, prerequisite course code | `configure` |
| `enroll` | learner id | `enroll` |
| `drop` | learner id | `drop` |
| `complete` | learner id, course code | `record_completed_course` |
| `inspect` | none | `inspect` |
| `quit` | none | ends the process |

Capacity must be an integer token such as `2` or `0`. A negative integer is passed to the service, which returns `invalid_request`. A token that is not an integer, such as `nope`, is unparseable.

```text
configure CS200 1 CS101
complete L1 CS101
enroll L1
complete L2 CS101
enroll L2
drop L1
inspect
quit
```

That session prints:

```text
configured
recorded
enrolled
recorded
waitlisted
dropped promoted_learner_id=L2
ok offering=CS200 capacity=1 prerequisite=CS101 enrolled=[L2] waitlist=[] seats_open=0
```

`updated` lines include `promoted_count`. `dropped` lines include `promoted_learner_id`, or `null` when the promotion pass moves nobody.

## Run the tests

```powershell
python -m pytest tests/test_waitlist.py
```

The tests call the service in-process. They cover the `CFG-*`, `REC-*`, `ENR-*`, `DRP-*`, and `CON-*` intents, and they check that enrollment stays within capacity and that a learner appears at most once across the enrolled list and the waitlist.

## Limitations and follow-up risks

- The roster lives on the service instance. Nothing is written to disk. A second process, or a restart, starts empty. The lock only coordinates threads inside that process.
- Recording a completed course never promotes, even when a seat is already open. A capacity increase promotes once per new seat and does not fill an older open seat. The next drop promotes at most one eligible waiter.
- An ineligible learner who is already waiting stays on the waitlist in FIFO order. This slice has no command to leave the waitlist.
- Completed courses are only added. Nothing revokes a course. Changing the prerequisite does not remove an enrolled learner who no longer meets it.
- The CLI does not check identity. Whoever has the terminal can configure, enroll, drop, and record completions.
- `Course-Registration-Rubric-Score.md` was not included. The tests check the assessment and the specs in this repository.
