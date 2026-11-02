
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, session

from models import Shift, db


shift_routes = Blueprint("shift_routes", __name__)


def get_user_id():
    """Get the currently logged-in user's ID."""
    return session.get("user_id")


def serialize_shift(shift):
    """Convert a shift object into a dictionary."""
    return {
        "id": shift.id,
        "user_id": shift.user_id,
        "clock_in": shift.clock_in.isoformat(),
        "clock_out": shift.clock_out.isoformat() if shift.clock_out else None
    }


# ==========================================
# PERSON C: SHIFT CRUD AND PAGINATION
# ==========================================

# GET /shifts - View shifts with pagination
@shift_routes.get("/shifts")
def get_shifts():
    user_id = get_user_id()

    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    if page < 1 or per_page < 1:
        return jsonify({"errors": ["Invalid pagination values"]}), 400

    per_page = min(per_page, 100)

    pagination = Shift.query.filter_by(
        user_id=user_id
    ).order_by(
        Shift.id.desc()
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return jsonify({
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "shifts": [serialize_shift(shift) for shift in pagination.items]
    }), 200


# POST /shifts - Create a shift
@shift_routes.post("/shifts")
def create_shift():
    user_id = get_user_id()

    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift(
        user_id=user_id,
        clock_in=datetime.now(timezone.utc),
        clock_out=None
    )

    db.session.add(shift)
    db.session.commit()

    return jsonify(serialize_shift(shift)), 201


# PATCH /shifts/<id> - Update a shift
@shift_routes.patch("/shifts/<int:shift_id>")
def update_shift(shift_id):
    user_id = get_user_id()

    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(
        id=shift_id,
        user_id=user_id
    ).first()

    if shift is None:
        return jsonify({"errors": ["Shift not found"]}), 404

    data = request.get_json(silent=True) or {}

    if "clock_out" not in data:
        return jsonify({"errors": ["clock_out is required"]}), 400

    try:
        clock_out = datetime.fromisoformat(
            data["clock_out"].replace("Z", "+00:00")
        )

        if clock_out.tzinfo is None:
            clock_out = clock_out.replace(tzinfo=timezone.utc)

        clock_in = shift.clock_in

        if clock_in.tzinfo is None:
            clock_in = clock_in.replace(tzinfo=timezone.utc)

        if clock_out <= clock_in:
            return jsonify({
                "errors": ["Clock-out must be after clock-in"]
            }), 400

        shift.clock_out = clock_out

    except (ValueError, AttributeError):
        return jsonify({
            "errors": ["Invalid clock-out date format"]
        }), 400

    db.session.commit()

    return jsonify(serialize_shift(shift)), 200


# DELETE /shifts/<id> - Delete a shift
@shift_routes.delete("/shifts/<int:shift_id>")
def delete_shift(shift_id):
    user_id = get_user_id()

    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(
        id=shift_id,
        user_id=user_id
    ).first()

    if shift is None:
        return jsonify({"errors": ["Shift not found"]}), 404

    db.session.delete(shift)
    db.session.commit()

    return jsonify({
        "message": "Shift deleted successfully"
    }), 200


# ==========================================
# PERSON D: CLOCK-IN AND CLOCK-OUT
# ==========================================

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

    shift = Shift(
        user_id=user_id,
        clock_in=datetime.now(timezone.utc)
    )

    db.session.add(shift)
    db.session.commit()

    return (
        jsonify({
            "id": shift.id,
            "clock_in": shift.clock_in.isoformat(),
            "clock_out": None,
        }),
        201,
    )


@shift_routes.patch("/shifts/<int:shift_id>/clock-out")
def clock_out(shift_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify({"errors": ["Authentication required"]}), 401

    shift = Shift.query.filter_by(
        id=shift_id,
        user_id=user_id
    ).first()

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
        jsonify({
            "id": shift.id,
            "clock_in": clock_in_time.isoformat(),
            "clock_out": shift.clock_out.isoformat(),
        }),
        200,
    )
