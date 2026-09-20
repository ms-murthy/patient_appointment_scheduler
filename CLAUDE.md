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

## Best Practices

- Always write a Google-style docstring for every function or method you add, including route handlers, utils and helpers: a one-line summary, `Args` with types (for route handlers, list URL/query/JSON-body inputs and say where each comes from), `Returns` with type and status codes, and one `Example`. Add `Raises` where relevant. Update the docstring whenever you change a function's behaviour, and match the existing ones in routes/ and utils/conflict.py.
- Validate in a fixed order and return early: JSON body present -> required fields -> parse ISO 8601 -> `end_time > start_time` -> `check_overlap()` -> write. Any new endpoint that accepts a time range must follow it, so bad input (400) is reported before a conflict (409).
- Error responses are `{'data': None, 'error': '<Sentence-case message>', 'status': <code>}` where `status` equals the HTTP status; success responses use `'error': None`.
- Every model has a `to_dict()`. Routes return its output, never model objects, and datetimes go out via `.isoformat()`.
- Prefer state changes over deleting rows (cancelling sets status='cancelled'), and commit once per request, only after every check has passed.
- Confirm that referenced records exist (e.g. patient_id, doctor_id) and return 404 if not, because SQLite will not enforce the foreign keys.
- Add pytest tests under tests/ for new logic (pytest and pytest-cov are already in requirements.txt), including boundary cases such as back-to-back and zero-length slots. Run them against an in-memory database, not db/appointments.db.

## Do Not Touch

- Do not edit the /health endpoint in app.py
- Do not write raw SQL queries — use SQLAlchemy ORM
- Do not change the JSON response shape (data / error / status)
- Do not run db/seed_data.py without asking first — it calls db.drop_all() and permanently deletes every row in db/appointments.db (gitignored, so there is no backup)

## Useful Context

- The overlap check in utils/conflict.py is the core business logic
- db/seed_data.py must be re-run after schema changes in development
- All datetime values use ISO 8601 format
- check_overlap() uses strict `<` / `>` on purpose so back-to-back slots (09:00–09:30, 09:30–10:00) are allowed; changing to `<=` / `>=` rejects them, and changing only one makes results depend on booking order. tests/ is empty, so nothing guards this.
- Cancellation is a soft delete: DELETE /appointments/<id> sets status='cancelled'. check_overlap() only counts status='scheduled', so cancelled slots can be rebooked. GET /appointments does not filter by status and still returns cancelled rows.
- /doctors/<id>/slots returns a doctor's BOOKED appointments, not free slots.
- db/seed_data.py runs db.drop_all() before recreating tables, so it wipes ALL data in db/appointments.db (gitignored, so unrecoverable). It creates 5 doctors, 10 patients and 20 non-overlapping appointments dated 1–5 July 2025 (in the past). Run it from the project root.
- db.create_all() runs on every app start (app.py) but never alters existing tables, which is why schema changes need a re-seed.
- Importing app runs create_app() at module level (app = create_app()), which touches the DB as a side effect. models.py does `from app import db`, and blueprints are imported inside create_app() to avoid a circular import; keep that pattern.
- SQLite foreign keys are not enforced (no PRAGMA foreign_keys=ON), and POST /appointments never checks that patient_id/doctor_id exist, so bad IDs create orphaned rows with a 201. Validate IDs in the route.
- There are no routes to create patients or doctors; the seed script is the only way to add them.
- /health is the only route that does not use the data/error/status envelope; leave it alone.
- POST and PUT both reject end_time <= start_time with 400, so zero-length and inverted appointments cannot be created via the API. check_overlap() itself does NOT guard against them (a zero-length slot at an existing appointment's boundary would pass it), so keep that route-level check.
- PUT /appointments/<id> is still less validated than POST: a null body or non-string datetime raises an uncaught TypeError (500). Cancelled appointments can also be "rescheduled" but stay cancelled.
- dob is stored as a String(20) (format YYYY-MM-DD by convention, not enforced); datetimes are naive, with created_at defaulting to the current UTC time (datetime.now(timezone.utc); SQLite stores it without a timezone).
- Run locally with `python app.py` (Flask debug server on 127.0.0.1:5000, auto-reloads on file changes). Config is hard-coded in app.py (DB path, SECRET_KEY, debug=True): python-dotenv is in requirements.txt but nothing loads .env, so editing it has no effect. Seed IDs for manual testing: doctors 1 Chen (Cardiology), 2 Okafor (Neurology), 3 Sharma (Oncology), 4 Davies (Orthopaedics), 5 Patel (General Practice); patients 1-10 (NHS-001 to NHS-010); appointments 1-20. Doctor 1 has a free 09:30-10:00 gap on 2025-07-01 for testing a successful booking.
- To test routes or check_overlap without touching db/appointments.db, build a throwaway app: `a = Flask(__name__); a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'; db.init_app(a); a.register_blueprint(appointments_bp)`, then use `a.test_client()`. Do not write through the module-level `app` from `import app` — it points at the real database.

## Lessons Learned

[TODO: Add in M10 — use the wrap-up prompt to generate this section]
