# AI usage log

Record of AI assistance for this single-offering enrollment, drop, and waitlist prototype. No starter repository was provided, and `Course-Registration-Rubric-Score.md` was not included. The approved specs are `specs/charter-and-persona.md`, `specs/architecture.md`, and `specs/intent.md`.

Decision is Accepted, Edited, or Rejected. Policy forks were not guessed. Each one was asked, then the spec was written from the answer.

## Charter and personas

- **Prompt:** Write `specs/charter-and-persona.md` for a minimal in-memory Python service and CLI covering one offering's enroll, drop, and FIFO waitlist promotion. Include the charter, learner and operator personas, and the prerequisite and waitlist policy. Ask before assuming. Do not write application code.
- **AI response summary:** The assistant asked three questions, then drafted the charter from the answers. Eligibility is one required course code on the learner's completed courses. An ineligible learner at the front of the waitlist is skipped and stays in FIFO order. Drop applies only to an enrolled learner. A waitlisted learner who is not enrolled gets an invalid result and stays on the waitlist. Personas are the learner and the course coordinator. Frontend, catalog, payments, identity, multi-term registration, an external database, and a policy engine are out of scope.
- **Decision:** Edited. The three policy answers were applied as given. The charter prose was accepted after those answers. A later architecture decision edited the promotion trigger so a capacity increase also promotes. See Architecture.
- **Files informed:** `specs/charter-and-persona.md`
- **Independent verification evidence:** The charter states the completed-course rule, skip-and-retain, and enrolled-only drop. It records that no starter repository and no scorecard file were provided. No application code was added in this step.

## Architecture

- **Prompt:** Read the charter and write `specs/architecture.md`. Cover the `registration/` layout (`models.py`, `service.py`, `cli.py`, `tests/test_waitlist.py`), action and result types, capacity and uniqueness invariants, the FIFO rule, in-memory tradeoffs, and a single `threading.Lock`. Ask before assuming. Do not write application code.
- **AI response summary:** The assistant asked what a capacity increase should do while people are already waiting. The answer was to fill each new seat immediately with the same FIFO pass, and still not promote when a completed course is recorded. The spec then defines result codes for configure, enroll, drop, record, and inspect. Duplicate and invalid drops change nothing. Promotion is private, runs under the caller's lock, and is not re-entrant. The CLI is one process because the store is in memory.
- **Decision:** Edited. The capacity-increase answer was applied as given. The module layout, result codes, invariants, and `threading.Lock` from the prompt were accepted. `specs/charter-and-persona.md` was edited so it no longer said a seat is offered only after a drop.
- **Files informed:** `specs/architecture.md`, `specs/charter-and-persona.md`
- **Independent verification evidence:** The architecture names `registration/__init__.py`, `models.py`, `service.py`, `cli.py`, and `tests/test_waitlist.py`. It lists the result codes, the seven invariants, and the rule that `record_completed_course` never promotes. No application code was added in this step.

## Behavioral intents

- **Prompt:** Read the charter and architecture and write `specs/intent.md` with testable outcomes for configure, inspect, recording courses, enroll, drop, and concurrent enroll and drop. Ask before assuming. Do not write application code.
- **AI response summary:** The assistant asked which configure failure wins when more than one applies. The answer was this order: `invalid_request`, then `offering_mismatch`, then `capacity_below_enrollment`. A blank or negative capacity is `invalid_request` even when the offering code also mismatches. The intent file then lists concrete `CFG-*`, `REC-*`, `ENR-*`, `DRP-*`, and `CON-*` scenarios, including skip-and-retain, one promotion pass per drop, one pass per new seat, and the legal result pairs when an enroll races a drop.
- **Decision:** Edited. The configure precedence answer was applied as given. The scenario groups requested in the prompt were accepted. `specs/architecture.md` was edited so its configure checks use that same order.
- **Files informed:** `specs/intent.md`, `specs/architecture.md`
- **Independent verification evidence:** `specs/intent.md` contains CFG-1 through CFG-16, REC-1 through REC-6, ENR-1 through ENR-13, DRP-1 through DRP-10, and CON-1 through CON-4. Each scenario names the result code and the roster afterward. No application code was added in this step.

## Implementation and tests

- **Prompt:** Use the `spec-driven-python` skill and implement the service, REPL, pytest suite, and runbook strictly from the charter, architecture, and intents. Runtime code stays on the standard library. Refusals return result objects. Do not add a frontend, catalog, payments, identity, multi-term registration, an external database, or a policy engine.
- **AI response summary:** The assistant added `RegistrationService` with one `threading.Lock`, private FIFO promotion, and the result types from the architecture. The REPL supports `configure`, `enroll`, `drop`, `complete`, `inspect`, and `quit`. Business answers exit 0. Unparseable input exits 2 and does not call the service. `tests/test_waitlist.py` maps the intent ids to tests. `RUNBOOK.md` documents setup, the REPL, pytest, and the in-memory limitations. A locked `completed_courses` read was added so tests can see recorded courses. It is not a REPL command and does not enroll, waitlist, or promote.
- **Decision:** Accepted. The implementation follows the specs and the skill. The `completed_courses` read is the only addition beyond the listed service actions, and it does not change the roster rules.
- **Files informed:** `registration/__init__.py`, `registration/models.py`, `registration/service.py`, `registration/cli.py`, `tests/test_waitlist.py`, `RUNBOOK.md`, `.cursor/skills/spec-driven-python/SKILL.md`
- **Independent verification evidence:** The first local run of this suite, before the enum correction, was 52 passed in 0.07s. The current run is recorded in the Verification section.

## Result codes and enroll check order

- **Prompt:** Review and fix `registration/service.py` and `registration/cli.py`, staying on the standard library. Construct results with the `StrEnum` members in `registration/models.py` instead of raw strings. In `enroll()`, return `invalid_request` for a blank or non-string `learner_id` before returning `not_configured` when no offering exists. Format CLI codes with `result.code.value` so the printed token is the lowercase value. Update `tests/test_waitlist.py` and re-run pytest.
- **AI response summary:** Result objects now store `ConfigureCode`, `EnrollCode`, `DropCode`, `RecordCode`, and `InspectCode` members. `enroll("")`, `enroll(" ")`, and a non-string id return `EnrollCode.INVALID_REQUEST` even when no offering exists, and they do not create one. `enroll("L1")` with no offering still returns `EnrollCode.NOT_CONFIGURED`. The REPL formatter reads `.value`, so a qualified name such as `EnrollCode.ENROLLED` is not printed. Tests assert enum identity and the formatter. `specs/intent.md` ENR-8 and the enroll check list in `specs/architecture.md` were updated afterward so a blank id returns `invalid_request` before the offering check. A non-blank id with no offering is still `not_configured`. The roster rules, lock, and promotion behavior were left as they were.
- **Decision:** Edited. The enum members and the CLI `.value` formatting were applied as requested. The enroll check order was steered by this prompt and overrides the earlier intent for a blank id before configure.
- **Files informed:** `registration/service.py`, `registration/cli.py`, `tests/test_waitlist.py`
- **Independent verification evidence:** `python -m pytest tests/test_waitlist.py` was run again after this correction. It collected 54 tests, including `test_result_codes_are_enum_members` and `test_cli_format_uses_enum_value_not_qualified_name`. The exact output is in the Verification section.

## Verification

- **Prompt:** Review the implementation against the specs, then leave room for the author to paste their own pytest run and CLI checks for exit 0 and exit 2.
- **AI response summary:** Review checked the public check order, result codes, private promotion, the single lock, and that recording a course does not promote. The test module names the `CFG-*`, `REC-*`, `ENR-*`, `DRP-*`, and `CON-*` cases. The REPL contract is exit 0 for a service answer and exit 2 for a line that is not dispatched. No scorecard file was available to score against. The pytest paste below is the run after the enum and enroll-order correction. The CLI pastes are from the earlier REPL checks and were not re-run for this update.
- **Decision:** Accepted. The current suite run is 54 passed. The CLI exit checks remain the earlier local runs.
- **Files informed:** `registration/service.py`, `registration/cli.py`, `tests/test_waitlist.py`, `RUNBOOK.md`, `README.md`
- **Independent verification evidence:**

Command:

```powershell
python -m pytest tests/test_waitlist.py
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\Proj\course-registration
collected 54 items

tests\test_waitlist.py ................................................. [ 90%]
.....                                                                    [100%]

============================= 54 passed in 0.05s ==============================
```

Command (expect exit code 0):

```powershell
python -m registration.cli
configure CS200 1 CS101
complete L1 CS101
enroll L1
complete L2 CS101
enroll L2
drop L1
inspect
quit
Write-Output "exit=$LASTEXITCODE"
```

Output:

```text
configured
recorded
enrolled
recorded
waitlisted
dropped promoted_learner_id=L2
ok offering=CS200 capacity=1 prerequisite=CS101 enrolled=[L2] waitlist=[] seats_open=0
exit=0
```

Command (expect exit code 2, and no service call):

```powershell
"enroll" | python -m registration.cli
Write-Output "exit=$LASTEXITCODE"
```

Output:

```text
unparseable
exit=2
```