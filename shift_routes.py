from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session

from models import Shift, db


shift_routes = Blueprint("shift_routes", __name__)


def serialize_shift(shift):
    clock_in = shift.clock_in
    if clock_in.tzinfo is None:
        clock_in = clock_in.replace(tzinfo=timezone.utc)

    clock_out = shift.clock_out
    if clock_out is not None and clock_out.tzinfo is None:
        clock_out = clock_out.replace(tzinfo=timezone.utc)

    return {
        "id": shift.id,
        "clock_in": clock_in.isoformat(),
        "clock_out": clock_out.isoformat() if clock_out is not None else None,
    }


def parse_timestamp(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field_name} must be an ISO 8601 timestamp") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def get_session_user_id():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return user_id


@shift_routes.get("/shifts")
def list_shifts():
    user_id = get_session_user_id()
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    page = max(1, request.args.get("page", default=1, type=int))
    per_page = min(max(1, request.args.get("per_page", default=10, type=int)), 100)
    pagination = (
        Shift.query.filter_by(user_id=user_id)
        .order_by(Shift.id.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return (
        jsonify(
            {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "shifts": [serialize_shift(shift) for shift in pagination.items],
            }
        ),
        200,
    )


@shift_routes.post("/shifts")
@shift_routes.post("/shifts/clock-in")
def clock_in():
    user_id = get_session_user_id()
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    data = request.get_json(silent=True)
    if request.get_data(cache=True) and data != {}:
        return jsonify({"errors": ["Clock-in timestamps are set by the server"]}), 400

    active_shift = Shift.query.filter_by(user_id=user_id, clock_out=None).first()
    if active_shift is not None:
        return jsonify({"errors": ["You are already clocked in"]}), 400

    shift = Shift(user_id=user_id, clock_in=datetime.now(timezone.utc))
    db.session.add(shift)
    db.session.commit()

    return jsonify(serialize_shift(shift)), 201


@shift_routes.get("/shifts/<int:shift_id>")
def show_shift(shift_id):
    user_id = get_session_user_id()
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(id=shift_id, user_id=user_id).first()
    if shift is None:
        return jsonify({"errors": ["Shift not found"]}), 404

    return jsonify(serialize_shift(shift)), 200


@shift_routes.patch("/shifts/<int:shift_id>")
def update_shift(shift_id):
    user_id = get_session_user_id()
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(id=shift_id, user_id=user_id).first()
    if shift is None:
        return jsonify({"errors": ["Shift not found"]}), 404

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({"errors": ["A JSON object with shift fields is required"]}), 400

    unsupported_fields = set(data) - {"clock_in", "clock_out"}
    if unsupported_fields:
        return jsonify({"errors": ["Only clock_in and clock_out can be updated"]}), 400

    clock_in = shift.clock_in
    clock_out = shift.clock_out
    try:
        if "clock_in" in data:
            clock_in = parse_timestamp(data["clock_in"], "clock_in")
        if "clock_out" in data:
            clock_out = (
                parse_timestamp(data["clock_out"], "clock_out")
                if data["clock_out"] is not None
                else None
            )
    except ValueError as error:
        return jsonify({"errors": [str(error)]}), 400

    if clock_in.tzinfo is None:
        clock_in = clock_in.replace(tzinfo=timezone.utc)
    if clock_out is not None and clock_out.tzinfo is None:
        clock_out = clock_out.replace(tzinfo=timezone.utc)

    if clock_out is not None and clock_out <= clock_in:
        return jsonify({"errors": ["Clock-out must be after clock-in"]}), 400

    if clock_out is None:
        active_shift = Shift.query.filter(
            Shift.user_id == user_id,
            Shift.clock_out.is_(None),
            Shift.id != shift.id,
        ).first()
        if active_shift is not None:
            return jsonify({"errors": ["You are already clocked in"]}), 400

    shift.clock_in = clock_in
    shift.clock_out = clock_out
    db.session.commit()

    return jsonify(serialize_shift(shift)), 200


@shift_routes.delete("/shifts/<int:shift_id>")
def delete_shift(shift_id):
    user_id = get_session_user_id()
    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(id=shift_id, user_id=user_id).first()
    if shift is None:
        return jsonify({"errors": ["Shift not found"]}), 404

    db.session.delete(shift)
    db.session.commit()
    return jsonify({}), 200


@shift_routes.patch("/shifts/<int:shift_id>/clock-out")
def clock_out(shift_id):
    user_id = get_session_user_id()
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

    return jsonify(serialize_shift(shift)), 200
