# Patient Appointment Scheduler

<!-- 
  WORKSHOP PARTICIPANTS: Fill in sections marked [TODO].
  The more specific you are, the better Claude understands your project.
  Run the verification prompt from M2 after filling this in.
-->

## Project Overview

[TODO: 2–3 sentences describing what this project does and who uses it]

Example: Patient appointment scheduling REST API for NHS clinic admin staff.
Allows booking, rescheduling, and cancelling appointments across multiple
doctors and departments. Internal tool — not patient-facing.

## Tech Stack

- Language: Python 3.13
- Framework: Flask 3.0
- ORM: Flask-SQLAlchemy 3.1
- Database: SQLite (db/appointments.db)
- Entry point: app.py
- Key files: routes/appointments.py, routes/doctors.py, models.py, utils/conflict.py

## Coding Conventions

- Use snake_case for all variable and function names
- All route handlers return JSON with exactly three keys: data, error, status
- No inline SQL — use SQLAlchemy ORM only
- HTTP status codes: 200 success, 201 created, 400 bad request, 404 not found, 409 conflict

## Naming Conventions

- Files and modules: lowercase snake_case (seed_data.py, conflict.py). One file per resource in routes/.
- Blueprints: `<resource>_bp = Blueprint('<resource>', __name__)`, registered inside create_app(), not at import time.
- Route handlers: `<verb>_<resource>`. Plural for lists (get_appointments), singular for by-ID (get_appointment), domain verbs for actions (reschedule_appointment, cancel_appointment).
- URLs: plural lowercase nouns (/appointments, /doctors), sub-resources nested under the ID (/doctors/<id>/slots). Path params are typed and named for the resource, e.g. `<int:appt_id>`, `<int:doctor_id>`.
- Models: singular PascalCase classes with a lowercase plural `__tablename__` (Doctor -> 'doctors').
- Columns: snake_case. Foreign keys are `<model>_id` (patient_id, doctor_id), datetimes that mark a slot are `<what>_time` (start_time, end_time), and audit timestamps end in `_at` (created_at).
- Status values are lowercase strings ('scheduled', 'cancelled'). check_overlap() matches 'scheduled' exactly, so a differently-cased or new status would not block a slot.
- Tests: files are `tests/test_<topic>.py`, functions are `test_<behaviour>` (e.g. `test_post_unknown_id_is_404_and_creates_nothing`), and the shared fixtures are named `app` and `client`. Module-level test constants are UPPER_SNAKE_CASE (`VALID`).
- Local variable names follow the resource: `appt` / `appt_id` for an Appointment, `doctor`, `patient`, `data` for the parsed JSON body, `start` / `end` (create) and `new_start` / `new_end` (reschedule) for parsed datetimes. Do not shadow `db`, `app` or `data` with something else.

## Best Practices

- Always write a Google-style docstring for every function or method you add, including route handlers, utils and helpers: a one-line summary, `Args` with types (for route handlers, list URL/query/JSON-body inputs and say where each comes from), `Returns` with type and status codes, and one `Example`. Add `Raises` where relevant. Update the docstring whenever you change a function's behaviour, and match the existing ones in routes/ and utils/conflict.py.
- Validate in a fixed order and return early: JSON body present -> required fields -> parse ISO 8601 -> `end_time > start_time` -> `check_overlap()` -> write. Any new endpoint that accepts a time range must follow it, so bad input (400) is reported before a conflict (409).
- Error responses are `{'data': None, 'error': '<Sentence-case message>', 'status': <code>}` where `status` equals the HTTP status; success responses use `'error': None`.
- Every model has a `to_dict()`. Routes return its output, never model objects, and datetimes go out via `.isoformat()`.
- Prefer state changes over deleting rows (cancelling sets status='cancelled'), and commit once per request, only after every check has passed.
- Confirm that referenced records exist (e.g. patient_id, doctor_id) and return 404 if not, because SQLite will not enforce the foreign keys.
- Add pytest tests under tests/ for new logic (pytest and pytest-cov are already in requirements.txt), including boundary cases such as back-to-back and zero-length slots. Run them against an in-memory database, not db/appointments.db.
- Formatting: 4-space indentation (no tabs), single-quoted strings (double quotes only for docstrings and to avoid escaping), and no trailing whitespace. There is no enforced line limit, but wrap docstrings at about 80 columns and break a long `jsonify({...})` or dict literal across lines with a 4-space hanging indent only when it does not fit on one line.
- Blank lines: existing modules (`models.py`, `routes/`, `utils/`) use ONE blank line between top-level definitions, while `tests/` files use two (PEP 8). Match the file you are editing rather than reformatting it, and keep each edit's diff limited to the lines you meant to change.
- Keep the envelope keys in the order `data`, `error`, `status`, use `isoformat()` for datetimes, and end every file with a newline. Line endings are handled by git (`core.autocrlf=true`: LF in the repo, CRLF in the Windows working copy), so the "LF will be replaced by CRLF" warnings are harmless; do not convert files by hand. Put new imports with the existing ones at the top of the file; do not import inside a function except for the circular-import case in `create_app()`.
- Prefer `db.session.get(Model, id)` over the legacy `Model.query.get(id)` in new code, and catch the narrowest exceptions that can actually occur (for example `(ValueError, TypeError)` around `datetime.fromisoformat()`), never a bare `except:`.

## Do Not Touch

- Do not edit the /health endpoint in app.py
- Do not write raw SQL queries — use SQLAlchemy ORM
- Do not change the JSON response shape (data / error / status)
- Do not run db/seed_data.py without asking first — it calls db.drop_all() and permanently deletes every row in db/appointments.db (gitignored, so there is no backup)
- Do not change the strict `<` / `>` comparisons in `check_overlap()` (utils/conflict.py), its `ValueError` guard for `end_time <= start_time`, or the route-level `end_time > start_time` 400 checks without updating tests/test_conflict.py and asking first. Changing either side silently allows or rejects real bookings, and the result can depend on booking order.

## Useful Context

- The overlap check in utils/conflict.py is the core business logic
- db/seed_data.py must be re-run after schema changes in development
- All datetime values use ISO 8601 format
- check_overlap() uses strict `<` / `>` on purpose so back-to-back slots (09:00–09:30, 09:30–10:00) are allowed; changing to `<=` / `>=` rejects them, and changing only one makes results depend on booking order. tests/test_conflict.py guards this (back-to-back, containment, 1-microsecond overlap).
- Cancellation is a soft delete: DELETE /appointments/<id> sets status='cancelled'. check_overlap() only counts status='scheduled', so cancelled slots can be rebooked. GET /appointments does not filter by status and still returns cancelled rows.
- /doctors/<id>/slots returns a doctor's BOOKED appointments, not free slots. It takes an optional `?date=YYYY-MM-DD` filter (bad format -> 400, unknown doctor -> 404), compares via `db.func.date(Appointment.start_time)`, and, unlike GET /appointments, excludes cancelled rows. Its response `data` is `{'doctor': {...}, 'booked_slots': [...]}`, not a bare list.
- Layering is deliberately thin: route handlers query the models and call `db.session` directly, and `utils/` currently holds only `check_overlap()` (used by POST and PUT). Put new reusable business rules in `utils/` with their own tests; keep handlers to validate -> check -> write -> respond.
- db/seed_data.py runs db.drop_all() before recreating tables, so it wipes ALL data in db/appointments.db (gitignored, so unrecoverable). It creates 5 doctors, 10 patients and 20 non-overlapping appointments dated 1–5 July 2025 (in the past). Run it from the project root.
- db.create_all() runs on every app start (app.py) but never alters existing tables, which is why schema changes need a re-seed.
- Importing app runs create_app() at module level (app = create_app()), which touches the DB as a side effect. models.py does `from app import db`, and blueprints are imported inside create_app() to avoid a circular import; keep that pattern.
- SQLite foreign keys are not enforced (no PRAGMA foreign_keys=ON), so the route must validate IDs. POST /appointments now does: patient_id/doctor_id must be integers (400, bool rejected), then the patient and doctor must exist (404 'Patient not found' / 'Doctor not found'), checked after the time-range 400s and before check_overlap() (409). Orphaned rows created before this check may still exist in an old db/appointments.db.
- There are no routes to create patients or doctors; the seed script is the only way to add them.
- /health is the only route that does not use the data/error/status envelope; leave it alone.
- POST and PUT both reject end_time <= start_time with 400, so zero-length and inverted appointments cannot be created via the API. check_overlap() also raises ValueError for end_time <= start_time (it used to report a zero-length slot at a boundary as free), so the route-level 400 check must stay before the call or callers get a 500.
- POST and PUT use request.get_json(silent=True): a missing, malformed, null or non-object body returns 400 'No data provided', and non-string datetimes return 400, all in the data/error/status envelope. PUT on a cancelled appointment returns 409 'Cancelled appointments cannot be rescheduled' (after the 400 checks, before check_overlap()); cancelled slots are rebooked with a new POST.
- Known remaining gaps: Flask's own 404/405/415 pages are HTML, not the envelope (no JSON error handlers); timezone-aware input such as `+01:00` is compared against naive stored datetimes; GET /appointments silently ignores invalid filters (`?doctor_id=abc` or `0` returns everything); check_overlap() and the insert are not atomic, so concurrent bookings can double-book; routes use the legacy Query.get() (deprecation warnings), and db.session.get() is preferred in new code.
- Run tests with the project venv, not the system Python (it has no Flask): `venv\Scripts\python.exe -m pytest tests`. Importing app in tests still runs create_app(), which calls db.create_all() on db/appointments.db (creates missing tables only, never drops or alters data).
- dob is stored as a String(20) (format YYYY-MM-DD by convention, not enforced); datetimes are naive, with created_at defaulting to the current UTC time (datetime.now(timezone.utc); SQLite stores it without a timezone).
- Run locally with `python app.py` (Flask debug server on 127.0.0.1:5000, auto-reloads on file changes). Config is hard-coded in app.py (DB path, SECRET_KEY, debug=True): python-dotenv is in requirements.txt but nothing loads .env, so editing it has no effect. Seed IDs for manual testing: doctors 1 Chen (Cardiology), 2 Okafor (Neurology), 3 Sharma (Oncology), 4 Davies (Orthopaedics), 5 Patel (General Practice); patients 1-10 (NHS-001 to NHS-010); appointments 1-20. Doctor 1 has a free 09:30-10:00 gap on 2025-07-01 for testing a successful booking.
- To test routes or check_overlap without touching db/appointments.db, build a throwaway app: `a = Flask(__name__); a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'; db.init_app(a); a.register_blueprint(appointments_bp)`, then use `a.test_client()`. Do not write through the module-level `app` from `import app` — it points at the real database.

## Lessons Learned

[TODO: Add in M10 — use the wrap-up prompt to generate this section]
