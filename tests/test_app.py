from datetime import datetime

from app import create_app
from models import Shift, db


def create_test_app():
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )


def test_shift_model_uses_the_shared_person_c_fields():
    app = create_test_app()

    with app.app_context():
        db.create_all()

        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()

        saved_shift = db.session.get(Shift, shift.id)
        assert saved_shift.user_id == 12
        assert saved_shift.clock_in == datetime(2026, 10, 31, 8, 30)
        assert saved_shift.clock_out is None

        db.drop_all()


def test_clock_in_requires_a_logged_in_user():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().post("/shifts/clock-in")

    assert response.status_code == 401
    assert response.json == {"errors": ["Authentication required"]}

    with app.app_context():
        db.drop_all()


def test_clock_in_creates_a_shift_for_the_session_user():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.post("/shifts/clock-in")

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["clock_in"]
    assert response.json["clock_out"] is None

    with app.app_context():
        shift = Shift.query.one()
        assert shift.user_id == 12
        assert shift.clock_out is None
        db.drop_all()


def test_clock_in_rejects_a_second_active_shift_for_the_same_user():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        db.session.add(Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30)))
        db.session.commit()

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.post("/shifts/clock-in")

    assert response.status_code == 400
    assert response.json == {"errors": ["You are already clocked in"]}

    with app.app_context():
        assert Shift.query.count() == 1
        db.drop_all()
