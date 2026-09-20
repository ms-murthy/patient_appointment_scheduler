from models import Appointment

def check_overlap(doctor_id, start_time, end_time, exclude_id=None):
    """Check whether a proposed slot overlaps a doctor's scheduled appointments.

    Two appointments overlap when one starts before the other ends AND ends
    after the other starts. This uses strict less-than comparisons so that
    back-to-back appointments (e.g. 09:00-09:30 followed by 09:30-10:00)
    are correctly allowed. Only appointments with status 'scheduled' count,
    so cancelled slots can be rebooked.

    Args:
        doctor_id (int): ID of the doctor whose schedule to check.
        start_time (datetime): Proposed appointment start.
        end_time (datetime): Proposed appointment end. Callers must ensure it
            is after start_time; zero-length or inverted ranges are not
            reliably handled here.
        exclude_id (int, optional): ID of an appointment to ignore, used when
            rescheduling so an appointment does not clash with its own old
            slot. Defaults to None.

    Returns:
        bool: True if an overlap exists, False if the slot is free.

    Example:
        Doctor 1 already has a scheduled 09:00-09:30 appointment on
        2025-07-01 and another at 10:00-10:30::

            >>> check_overlap(1, datetime(2025, 7, 1, 9, 15), datetime(2025, 7, 1, 9, 45))
            True
            >>> check_overlap(1, datetime(2025, 7, 1, 9, 30), datetime(2025, 7, 1, 10, 0))
            False
    """
    query = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status == 'scheduled',
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )
    if exclude_id:
        query = query.filter(Appointment.id != exclude_id)
    return query.first() is not None

