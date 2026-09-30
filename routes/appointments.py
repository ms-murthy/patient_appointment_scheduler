from flask import Blueprint, request, jsonify
from app import db
from models import Appointment, Doctor, Patient
from utils.conflict import check_overlap
from datetime import datetime

appointments_bp = Blueprint('appointments', __name__)

@appointments_bp.route('/appointments', methods=['GET'])
def get_appointments():
    """List appointments, optionally filtered by patient and/or doctor.

    Cancelled appointments are included, because no status filter is applied.

    Args:
        patient_id (int, optional): Query-string filter; only this patient's
            appointments are returned. Non-integer values are ignored.
        doctor_id (int, optional): Query-string filter; only this doctor's
            appointments are returned. Non-integer values are ignored.

    Returns:
        flask.Response: HTTP 200 with the standard envelope, where ``data`` is
        a list of appointment dicts (empty if nothing matches).

    Example:
        ``GET /appointments?doctor_id=1``::

            {"data": [{"doctor_id": 1, "end_time": "2025-07-01T09:30:00", "id": 1,
                       "patient_id": 1, "reason": "Annual check-up",
                       "start_time": "2025-07-01T09:00:00", "status": "scheduled"},
                      ...],
             "error": null, "status": 200}
    """
    patient_id = request.args.get('patient_id', type=int)
    doctor_id = request.args.get('doctor_id', type=int)
    query = Appointment.query
    if patient_id:
        query = query.filter_by(patient_id=patient_id)
    if doctor_id:
        query = query.filter_by(doctor_id=doctor_id)
    appointments = query.all()
    return jsonify({'data': [a.to_dict() for a in appointments], 'error': None, 'status': 200})

@appointments_bp.route('/appointments/<int:appt_id>', methods=['GET'])
def get_appointment(appt_id):
    """Fetch a single appointment by ID.

    Args:
        appt_id (int): Appointment ID, taken from the URL path.

    Returns:
        flask.Response or tuple[flask.Response, int]: HTTP 200 with the
        appointment dict in ``data``, or HTTP 404 with ``error`` set if no
        appointment has that ID.

    Example:
        ``GET /appointments/1``::

            {"data": {"doctor_id": 1, "end_time": "2025-07-01T09:30:00", "id": 1,
                      "patient_id": 1, "reason": "Annual check-up",
                      "start_time": "2025-07-01T09:00:00", "status": "scheduled"},
             "error": null, "status": 200}
    """
    appt = Appointment.query.get(appt_id)
    if not appt:
        return jsonify({'data': None, 'error': 'Appointment not found', 'status': 404}), 404
    return jsonify({'data': appt.to_dict(), 'error': None, 'status': 200})

@appointments_bp.route('/appointments', methods=['POST'])
def create_appointment():
    """Book a new appointment for a doctor and patient.

    Rejects the booking if the doctor already has a scheduled appointment that
    overlaps the requested slot (see ``utils.conflict.check_overlap``).
    Back-to-back slots are allowed. The patient and doctor IDs are not checked
    for existence.

    Args:
        patient_id (int): JSON body field; ID of the patient.
        doctor_id (int): JSON body field; ID of the doctor.
        start_time (str): JSON body field; ISO 8601 start, e.g.
            ``2025-07-01T09:30:00``.
        end_time (str): JSON body field; ISO 8601 end, must be after
            ``start_time``.
        reason (str, optional): JSON body field; free-text reason. Defaults to
            an empty string.

    Returns:
        tuple[flask.Response, int]: HTTP 201 with the new appointment in
        ``data``. HTTP 400 for a missing, malformed or non-object body, a
        missing field, a datetime that is not an ISO 8601 string, or
        ``end_time <= start_time``. HTTP 409 if the slot conflicts with an
        existing appointment.

    Example:
        ``POST /appointments`` with body ``{"patient_id": 1, "doctor_id": 1,
        "start_time": "2025-07-01T09:30:00", "end_time": "2025-07-01T10:00:00",
        "reason": "Annual check-up"}``::

            {"data": {"doctor_id": 1, "end_time": "2025-07-01T10:00:00", "id": 21,
                      "patient_id": 1, "reason": "Annual check-up",
                      "start_time": "2025-07-01T09:30:00", "status": "scheduled"},
             "error": null, "status": 201}
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'data': None, 'error': 'No data provided', 'status': 400}), 400
    required = ['patient_id', 'doctor_id', 'start_time', 'end_time']
    for field in required:
        if field not in data:
            return jsonify({'data': None, 'error': f'Missing field: {field}', 'status': 400}), 400
    try:
        start = datetime.fromisoformat(data['start_time'])
        end = datetime.fromisoformat(data['end_time'])
    except (ValueError, TypeError):
        return jsonify({'data': None, 'error': 'Invalid datetime format. Use ISO 8601.', 'status': 400}), 400
    if end <= start:
        return jsonify({'data': None, 'error': 'end_time must be after start_time', 'status': 400}), 400
    if check_overlap(data['doctor_id'], start, end):
        return jsonify({'data': None, 'error': 'Time slot conflicts with existing appointment', 'status': 409}), 409
    appt = Appointment(
        patient_id=data['patient_id'],
        doctor_id=data['doctor_id'],
        start_time=start,
        end_time=end,
        reason=data.get('reason', ''),
        status='scheduled'
    )
    db.session.add(appt)
    db.session.commit()
    return jsonify({'data': appt.to_dict(), 'error': None, 'status': 201}), 201

@appointments_bp.route('/appointments/<int:appt_id>', methods=['PUT'])
def reschedule_appointment(appt_id):
    """Move an existing appointment to a new time slot.

    Only ``start_time`` and ``end_time`` change; the doctor, patient, reason
    and status are left as they are (a cancelled appointment stays cancelled).
    The appointment is excluded from the overlap check, so it may overlap its
    own old slot.

    Args:
        appt_id (int): Appointment ID, taken from the URL path.
        start_time (str): JSON body field; new ISO 8601 start.
        end_time (str): JSON body field; new ISO 8601 end, must be after
            ``start_time``.

    Returns:
        flask.Response or tuple[flask.Response, int]: HTTP 200 with the updated
        appointment in ``data``. HTTP 400 for a missing, malformed or
        non-object body, missing or invalid datetimes (including non-string
        values) or ``end_time <= start_time``. HTTP 404 if the ID is unknown.
        HTTP 409 if
        the new slot conflicts with another appointment for the same doctor.

    Example:
        ``PUT /appointments/2`` with body ``{"start_time": "2025-07-02T14:00:00",
        "end_time": "2025-07-02T14:30:00"}``::

            {"data": {"doctor_id": 1, "end_time": "2025-07-02T14:30:00", "id": 2,
                      "patient_id": 2, "reason": "Follow-up consultation",
                      "start_time": "2025-07-02T14:00:00", "status": "scheduled"},
             "error": null, "status": 200}
    """
    appt = Appointment.query.get(appt_id)
    if not appt:
        return jsonify({'data': None, 'error': 'Appointment not found', 'status': 404}), 404
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'data': None, 'error': 'No data provided', 'status': 400}), 400
    try:
        new_start = datetime.fromisoformat(data['start_time'])
        new_end = datetime.fromisoformat(data['end_time'])
    except (ValueError, KeyError, TypeError):
        return jsonify({'data': None, 'error': 'Invalid or missing datetime fields', 'status': 400}), 400
    if new_end <= new_start:
        return jsonify({'data': None, 'error': 'end_time must be after start_time', 'status': 400}), 400
    if check_overlap(appt.doctor_id, new_start, new_end, exclude_id=appt_id):
        return jsonify({'data': None, 'error': 'New time slot conflicts with existing appointment', 'status': 409}), 409
    appt.start_time = new_start
    appt.end_time = new_end
    db.session.commit()
    return jsonify({'data': appt.to_dict(), 'error': None, 'status': 200})

@appointments_bp.route('/appointments/<int:appt_id>', methods=['DELETE'])
def cancel_appointment(appt_id):
    """Cancel an appointment (soft delete).

    Sets ``status`` to ``'cancelled'`` instead of removing the row, which frees
    the slot for rebooking. Cancelling an already-cancelled appointment
    succeeds again with the same response.

    Args:
        appt_id (int): Appointment ID, taken from the URL path.

    Returns:
        flask.Response or tuple[flask.Response, int]: HTTP 200 with the ID and
        new status in ``data``, or HTTP 404 if the ID is unknown.

    Example:
        ``DELETE /appointments/5``::

            {"data": {"id": 5, "status": "cancelled"}, "error": null, "status": 200}
    """
    appt = Appointment.query.get(appt_id)
    if not appt:
        return jsonify({'data': None, 'error': 'Appointment not found', 'status': 404}), 404
    appt.status = 'cancelled'
    db.session.commit()
    return jsonify({'data': {'id': appt_id, 'status': 'cancelled'}, 'error': None, 'status': 200})
