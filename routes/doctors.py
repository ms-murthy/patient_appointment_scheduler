from flask import Blueprint, request, jsonify
from app import db
from models import Doctor, Appointment
from datetime import datetime

doctors_bp = Blueprint('doctors', __name__)

@doctors_bp.route('/doctors', methods=['GET'])
def get_doctors():
    """List all doctors.

    Returns:
        flask.Response: HTTP 200 with the standard envelope, where ``data`` is
        a list of doctor dicts (``id``, ``name``, ``department``).

    Example:
        ``GET /doctors``::

            {"data": [{"department": "Cardiology", "id": 1, "name": "Dr. Sarah Chen"},
                      ...],
             "error": null, "status": 200}
    """
    doctors = Doctor.query.all()
    return jsonify({'data': [d.to_dict() for d in doctors], 'error': None, 'status': 200})

@doctors_bp.route('/doctors/<int:doctor_id>', methods=['GET'])
def get_doctor(doctor_id):
    """Fetch a single doctor by ID.

    Args:
        doctor_id (int): Doctor ID, taken from the URL path.

    Returns:
        flask.Response or tuple[flask.Response, int]: HTTP 200 with the doctor
        dict in ``data``, or HTTP 404 with ``error`` set if the ID is unknown.

    Example:
        ``GET /doctors/2``::

            {"data": {"department": "Neurology", "id": 2, "name": "Dr. James Okafor"},
             "error": null, "status": 200}
    """
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'data': None, 'error': 'Doctor not found', 'status': 404}), 404
    return jsonify({'data': doctor.to_dict(), 'error': None, 'status': 200})

@doctors_bp.route('/doctors/<int:doctor_id>/slots', methods=['GET'])
def get_doctor_slots(doctor_id):
    """List a doctor's booked slots, optionally for a single day.

    Despite the name, this returns the times that are already taken (appointments
    with status 'scheduled'), not the free ones. Cancelled appointments are
    excluded.

    Args:
        doctor_id (int): Doctor ID, taken from the URL path.
        date (str, optional): Query-string filter in ``YYYY-MM-DD`` format; only
            appointments starting on that day are returned. If omitted, all
            of the doctor's scheduled appointments are returned.

    Returns:
        flask.Response or tuple[flask.Response, int]: HTTP 200 with ``data``
        holding the ``doctor`` dict and a ``booked_slots`` list of appointment
        dicts. HTTP 404 if the doctor is unknown. HTTP 400 if ``date`` is not
        in ``YYYY-MM-DD`` format.

    Example:
        ``GET /doctors/2/slots?date=2025-07-01``::

            {"data": {"booked_slots": [{"doctor_id": 2, "end_time": "2025-07-01T11:30:00",
                                        "id": 3, "patient_id": 1,
                                        "reason": "Blood pressure review",
                                        "start_time": "2025-07-01T11:00:00",
                                        "status": "scheduled"},
                                       ...],
                      "doctor": {"department": "Neurology", "id": 2,
                                 "name": "Dr. James Okafor"}},
             "error": null, "status": 200}
    """
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'data': None, 'error': 'Doctor not found', 'status': 404}), 404
    date_str = request.args.get('date')
    query = Appointment.query.filter_by(doctor_id=doctor_id, status='scheduled')
    if date_str:
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            query = query.filter(db.func.date(Appointment.start_time) == date.date())
        except ValueError:
            return jsonify({'data': None, 'error': 'Invalid date format. Use YYYY-MM-DD.', 'status': 400}), 400
    appointments = query.all()
    return jsonify({
        'data': {'doctor': doctor.to_dict(), 'booked_slots': [a.to_dict() for a in appointments]},
        'error': None, 'status': 200
    })
