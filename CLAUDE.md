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

- Language: Python 3.11
- Framework: Flask 3.0
- ORM: Flask-SQLAlchemy 3.1
- Database: SQLite (db/appointments.db)
- Entry point: app.py
- Key files: routes/appointments.py, routes/doctors.py, models.py, utils/conflict.py

## Coding Conventions

[TODO: Add at least 3 rules you discover during exploration]

- Use snake_case for all variable and function names
- All route handlers return JSON with exactly three keys: data, error, status
- No inline SQL — use SQLAlchemy ORM only
- HTTP status codes: 200 success, 201 created, 400 bad request, 404 not found, 409 conflict

## Do Not Touch

[TODO: Add files or logic you must never modify without good reason]

- Do not edit the /health endpoint in app.py
- Do not write raw SQL queries — use SQLAlchemy ORM
- Do not change the JSON response shape (data / error / status)

## Useful Context

[TODO: Add notes from your M3 codebase exploration]

- The overlap check in utils/conflict.py is the core business logic
- db/seed_data.py must be re-run after schema changes in development
- All datetime values use ISO 8601 format

## Lessons Learned

[TODO: Add in M10 — use the wrap-up prompt to generate this section]
