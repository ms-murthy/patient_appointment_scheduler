"""Tests for request-body validation on POST and PUT /appointments (in-memory DB)."""
from datetime import datetime

import pytest
from flask import Flask

from app import db
from models import Appointment, Doctor, Patient
from routes.appointments import appointments_bp

VALID = {'patient_id': 1, 'doctor_id': 1,
         'start_time': '2025-07-01T09:30:00', 'end_time': '2025-07-01T10:00:00'}


@pytest.fixture
def client():
    """Yield a test client on a throwaway in-memory DB holding appointment 1.

    Doctor 1, patient 1 and appointment 1 (09:00-09:30 on 2025-07-01) exist.

    Returns:
        Iterator[flask.testing.FlaskClient]: Client for the throwaway app.

    Example:
        Used implicitly by the tests below via the ``client`` argument.
    """
    a = Flask(__name__)
    a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db.init_app(a)
    a.register_blueprint(appointments_bp)
    with a.app_context():
        db.create_all()
        db.session.add_all([Doctor(name='Dr. Sarah Chen', department='Cardiology'),
                            Patient(name='Alice Thompson', dob='1985-03-12', nhs_number='NHS-001')])
        db.session.commit()
        db.session.add(Appointment(patient_id=1, doctor_id=1, status='scheduled',
                                   start_time=datetime(2025, 7, 1, 9), end_time=datetime(2025, 7, 1, 9, 30)))
        db.session.commit()
        yield a.test_client()
        db.session.remove()
        db.drop_all()


def assert_envelope_400(response):
    """Assert a 400 response that uses the data/error/status envelope."""
    body = response.get_json()
    assert response.status_code == 400
    assert body['data'] is None and body['status'] == 400 and body['error']


@pytest.mark.parametrize('method, url', [('post', '/appointments'), ('put', '/appointments/1')])
@pytest.mark.parametrize('kwargs', [
    {},                                           # no body, no content type
    {'data': 'not json', 'content_type': 'application/json'},
    {'json': None},                               # JSON null
    {'json': [1, 2]},                             # not an object
    {'json': True},
    {'json': 5},
])
def test_bad_body_is_400(client, method, url, kwargs):
    """Missing, malformed and non-object bodies return 400 in the envelope, not 500."""
    assert_envelope_400(getattr(client, method)(url, **kwargs))


@pytest.mark.parametrize('bad', [123, None, ['2025-07-01T09:30:00'], {'a': 1}, True])
@pytest.mark.parametrize('field', ['start_time', 'end_time'])
def test_post_non_string_datetime_is_400(client, field, bad):
    """POST with a non-string datetime returns 400 instead of an uncaught TypeError."""
    assert_envelope_400(client.post('/appointments', json={**VALID, field: bad}))


@pytest.mark.parametrize('bad', [123, None, ['2025-07-01T09:30:00'], 'nope'])
@pytest.mark.parametrize('field', ['start_time', 'end_time'])
def test_put_bad_datetime_is_400(client, field, bad):
    """PUT with a non-string or unparsable datetime returns 400 instead of a 500."""
    body = {'start_time': '2025-07-01T10:00:00', 'end_time': '2025-07-01T10:30:00', field: bad}
    assert_envelope_400(client.put('/appointments/1', json=body))


def test_put_missing_field_is_400(client):
    """PUT without end_time returns 400."""
    assert_envelope_400(client.put('/appointments/1', json={'start_time': '2025-07-01T10:00:00'}))


def test_put_unknown_id_is_404_before_body_check(client):
    """PUT on an unknown ID is still 404, even with a bad body."""
    assert client.put('/appointments/999', json=None).status_code == 404


@pytest.mark.parametrize('field, error', [('patient_id', 'Patient not found'),
                                          ('doctor_id', 'Doctor not found')])
def test_post_unknown_id_is_404_and_creates_nothing(client, field, error):
    """POST with a nonexistent patient or doctor returns 404 and inserts no row."""
    response = client.post('/appointments', json={**VALID, field: 999})
    body = response.get_json()
    assert response.status_code == 404
    assert body['data'] is None and body['status'] == 404 and body['error'] == error
    assert Appointment.query.count() == 1


@pytest.mark.parametrize('bad', ['1', 1.5, None, True, [1]])
@pytest.mark.parametrize('field', ['patient_id', 'doctor_id'])
def test_post_non_integer_id_is_400(client, field, bad):
    """POST with a non-integer patient_id or doctor_id returns 400 (bool is rejected too)."""
    assert_envelope_400(client.post('/appointments', json={**VALID, field: bad}))


def test_post_bad_input_beats_unknown_id(client):
    """A bad time range is reported as 400 even when the IDs are also unknown."""
    body = {**VALID, 'patient_id': 999, 'doctor_id': 999, 'end_time': VALID['start_time']}
    assert_envelope_400(client.post('/appointments', json=body))


def test_post_unknown_id_beats_conflict(client):
    """An unknown doctor is 404, not a 409 or a silent success, for an otherwise free slot."""
    body = {**VALID, 'doctor_id': 999, 'start_time': '2025-07-01T09:00:00', 'end_time': '2025-07-01T09:30:00'}
    assert client.post('/appointments', json=body).status_code == 404


def test_put_cancelled_appointment_is_409_and_unchanged(client):
    """PUT on a cancelled appointment returns 409 and leaves its times and status alone."""
    client.delete('/appointments/1')
    response = client.put('/appointments/1', json={'start_time': '2025-07-01T11:00:00',
                                                   'end_time': '2025-07-01T11:30:00'})
    body = response.get_json()
    assert response.status_code == 409
    assert body['data'] is None and body['status'] == 409
    assert body['error'] == 'Cancelled appointments cannot be rescheduled'
    appt = db.session.get(Appointment, 1)
    assert appt.status == 'cancelled'
    assert appt.start_time == datetime(2025, 7, 1, 9)


def test_put_cancelled_bad_input_is_still_400(client):
    """A bad time range on a cancelled appointment is 400, since bad input beats a conflict."""
    client.delete('/appointments/1')
    response = client.put('/appointments/1', json={'start_time': '2025-07-01T11:30:00',
                                                   'end_time': '2025-07-01T11:00:00'})
    assert_envelope_400(response)


def test_valid_requests_still_succeed(client):
    """A valid POST (back-to-back slot) is 201 and a valid PUT is 200."""
    assert client.post('/appointments', json=VALID).status_code == 201
    response = client.put('/appointments/1', json={'start_time': '2025-07-01T11:00:00',
                                                   'end_time': '2025-07-01T11:30:00'})
    assert response.status_code == 200
