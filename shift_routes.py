from datetime import datetime, timezone

from flask import Blueprint, jsonify, session

from models import Shift, db


shift_routes = Blueprint("shift_routes", __name__)


@shift_routes.post("/shifts/clock-in")
def clock_in():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    active_shift = Shift.query.filter_by(
        user_id=user_id,
        clock_out=None,
    ).first()
    if active_shift is not None:
        return jsonify({"errors": ["You are already clocked in"]}), 400

    shift = Shift(user_id=user_id, clock_in=datetime.now(timezone.utc))
    db.session.add(shift)
    db.session.commit()

    return (
        jsonify(
            {
                "id": shift.id,
                "clock_in": shift.clock_in.isoformat(),
                "clock_out": None,
            }
        ),
        201,
    )
