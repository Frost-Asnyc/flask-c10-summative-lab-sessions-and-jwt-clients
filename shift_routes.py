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


@shift_routes.patch("/shifts/<int:shift_id>/clock-out")
def clock_out(shift_id):
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(id=shift_id, user_id=user_id).first()
    if shift is None:
        return jsonify({"errors": ["Shift not found"]}), 404

    if shift.clock_out is not None:
        return jsonify({"errors": ["This shift is already clocked out"]}), 400

    clock_out_time = datetime.now(timezone.utc)
    clock_in_time = shift.clock_in
    if clock_in_time.tzinfo is None:
        clock_in_time = clock_in_time.replace(tzinfo=timezone.utc)

    if clock_out_time <= clock_in_time:
        return jsonify({"errors": ["Clock-out must be after clock-in"]}), 400

    shift.clock_out = clock_out_time
    db.session.commit()

    return (
        jsonify(
            {
                "id": shift.id,
                "clock_in": clock_in_time.isoformat(),
                "clock_out": shift.clock_out.isoformat(),
            }
        ),
        200,
    )
