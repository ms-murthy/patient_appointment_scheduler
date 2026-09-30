"""Tests for utils.conflict.check_overlap, run against an in-memory SQLite database."""
from datetime import datetime

import pytest
from flask import Flask

from app import db
from models import Appointment
from routes.appointments import appointments_bp
from utils.conflict import check_overlap


def t(hour, minute=0, second=0, microsecond=0):
    """Build a naive datetime on 2025-07-01.

    Args:
        hour (int): Hour of day.
        minute (int): Minute. Defaults to 0.
        second (int): Second. Defaults to 0.
        microsecond (int): Microsecond. Defaults to 0.

    Returns:
        datetime: The requested time on 2025-07-01.

    Example:
        >>> t(9, 30)
        datetime.datetime(2025, 7, 1, 9, 30)
    """
    return datetime(2025, 7, 1, hour, minute, second, microsecond)


@pytest.fixture
def app():
    """Yield a throwaway Flask app on an in-memory DB with doctor 1 pre-booked.

    Doctor 1 has a scheduled 09:00-09:30 appointment and a cancelled
    10:00-10:30 appointment.

    Returns:
        Iterator[Flask]: The app, inside an active app context.

    Example:
        Used implicitly by the tests below via the ``app`` argument.
    """
    a = Flask(__name__)
    a.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    db.init_app(a)
    a.register_blueprint(appointments_bp)
    with a.app_context():
        db.create_all()
        db.session.add_all([
            Appointment(patient_id=1, doctor_id=1, start_time=t(9), end_time=t(9, 30), status='scheduled'),
            Appointment(patient_id=1, doctor_id=1, start_time=t(10), end_time=t(10, 30), status='cancelled'),
        ])
        db.session.commit()
        yield a
        db.session.remove()
        db.drop_all()


@pytest.mark.parametrize('start, end', [
    (t(9, 30), t(10)),        # back-to-back after
    (t(8, 30), t(9)),         # back-to-back before
    (t(10), t(10, 30)),       # cancelled slot can be rebooked
    (t(11), t(12)),           # clear gap
])
def test_slot_is_free(app, start, end):
    """Back-to-back, cancelled and clear-gap slots are not reported as overlaps."""
    assert check_overlap(1, start, end) is False


@pytest.mark.parametrize('start, end', [
    (t(9), t(9, 30)),                 # identical
    (t(9, 15), t(9, 45)),             # partial overlap at the end
    (t(8, 45), t(9, 15)),             # partial overlap at the start
    (t(8), t(10)),                    # new contains existing
    (t(9, 10), t(9, 20)),             # existing contains new
    (t(8, 30), t(9, 0, 0, 1)),        # one microsecond of shared time
])
def test_slot_overlaps(app, start, end):
    """Identical, partial, containing and contained slots are reported as overlaps."""
    assert check_overlap(1, start, end) is True


@pytest.mark.parametrize('start, end', [
    (t(9, 15), t(9, 15)),     # zero-length inside an existing slot
    (t(9), t(9)),             # zero-length at an existing start boundary
    (t(9, 30), t(9, 30)),     # zero-length at an existing end boundary
    (t(9, 20), t(9, 10)),     # inverted
    (t(12), t(8)),            # inverted, spanning the whole day
])
def test_zero_length_and_inverted_raise(app, start, end):
    """Zero-length and inverted ranges raise ValueError instead of returning a result."""
    with pytest.raises(ValueError):
        check_overlap(1, start, end)


def test_exclude_id_ignores_own_slot(app):
    """An appointment does not conflict with its own slot when exclude_id is set."""
    own_id = Appointment.query.filter_by(status='scheduled').first().id
    assert check_overlap(1, t(9), t(9, 30), exclude_id=own_id) is False


def test_other_doctor_is_unaffected(app):
    """A slot taken for doctor 1 is free for doctor 2."""
    assert check_overlap(2, t(9), t(9, 30)) is False


@pytest.mark.parametrize('start, end', [
    ('2025-07-01T09:30:00', '2025-07-01T09:30:00'),
    ('2025-07-01T09:45:00', '2025-07-01T09:30:00'),
])
def test_post_rejects_zero_length_with_400_not_500(app, start, end):
    """POST /appointments still answers 400 (not 500) for zero-length and inverted slots."""
    response = app.test_client().post('/appointments', json={
        'patient_id': 1, 'doctor_id': 1, 'start_time': start, 'end_time': end})
    assert response.status_code == 400
    assert response.get_json()['error'] == 'end_time must be after start_time'
