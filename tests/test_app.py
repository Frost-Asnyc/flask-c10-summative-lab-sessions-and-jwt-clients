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


def test_clock_out_requires_a_logged_in_user():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().patch("/shifts/1/clock-out")

    assert response.status_code == 401
    assert response.json == {"errors": ["Authentication required"]}

    with app.app_context():
        db.drop_all()


def test_clock_out_updates_the_current_users_active_shift():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.patch(f"/shifts/{shift_id}/clock-out")

    assert response.status_code == 200
    assert response.json["id"] == shift_id
    assert response.json["clock_in"] == "2026-10-31T08:30:00+00:00"
    assert response.json["clock_out"]

    with app.app_context():
        saved_shift = db.session.get(Shift, shift_id)
        assert saved_shift.clock_out is not None
        assert saved_shift.clock_out > saved_shift.clock_in
        db.drop_all()


def test_clock_out_does_not_find_another_users_shift():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 34

    response = client.patch(f"/shifts/{shift_id}/clock-out")

    assert response.status_code == 404
    assert response.json == {"errors": ["Shift not found"]}

    with app.app_context():
        shift = db.session.get(Shift, shift_id)
        assert shift.clock_out is None
        db.drop_all()


def test_clock_out_rejects_a_shift_that_is_already_closed():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(
            user_id=12,
            clock_in=datetime(2026, 10, 31, 8, 30),
            clock_out=datetime(2026, 10, 31, 16, 30),
        )
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.patch(f"/shifts/{shift_id}/clock-out")

    assert response.status_code == 400
    assert response.json == {"errors": ["This shift is already clocked out"]}

    with app.app_context():
        assert Shift.query.count() == 1
        db.drop_all()


def test_list_shifts_returns_only_the_session_users_shifts_with_pagination():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                Shift(user_id=12, clock_in=datetime(2026, 10, 30, 8, 30)),
                Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30)),
                Shift(user_id=34, clock_in=datetime(2026, 10, 31, 9, 30)),
            ]
        )
        db.session.commit()

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.get("/shifts?page=1&per_page=1")

    assert response.status_code == 200
    assert response.json["page"] == 1
    assert response.json["per_page"] == 1
    assert response.json["total"] == 2
    assert len(response.json["shifts"]) == 1
    assert response.json["shifts"][0]["clock_in"] == "2026-10-31T08:30:00+00:00"

    with app.app_context():
        db.drop_all()


def test_get_shift_does_not_expose_another_users_shift():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 34

    response = client.get(f"/shifts/{shift_id}")

    assert response.status_code == 404
    assert response.json == {"errors": ["Shift not found"]}

    with app.app_context():
        db.drop_all()


def test_post_shifts_creates_an_active_shift_for_the_session_user():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.post("/shifts")

    assert response.status_code == 201
    assert response.json["id"] == 1
    assert response.json["clock_in"]
    assert response.json["clock_out"] is None

    with app.app_context():
        shift = Shift.query.one()
        assert shift.user_id == 12
        assert shift.clock_out is None
        db.drop_all()


def test_update_shift_validates_timestamps_and_updates_owned_shift():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.patch(
        f"/shifts/{shift_id}",
        json={
            "clock_in": "2026-10-31T09:00:00Z",
            "clock_out": "2026-10-31T17:00:00Z",
        },
    )

    assert response.status_code == 200
    assert response.json["clock_in"] == "2026-10-31T09:00:00+00:00"
    assert response.json["clock_out"] == "2026-10-31T17:00:00+00:00"

    invalid_response = client.patch(
        f"/shifts/{shift_id}",
        json={"clock_out": "2026-10-31T08:00:00Z"},
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json == {"errors": ["Clock-out must be after clock-in"]}

    with app.app_context():
        saved_shift = db.session.get(Shift, shift_id)
        assert saved_shift.clock_out == datetime(2026, 10, 31, 17, 0)
        db.drop_all()


def test_update_shift_cannot_modify_another_users_shift():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 34

    response = client.patch(
        f"/shifts/{shift_id}",
        json={"clock_out": "2026-10-31T17:00:00Z"},
    )

    assert response.status_code == 404
    assert response.json == {"errors": ["Shift not found"]}

    with app.app_context():
        shift = db.session.get(Shift, shift_id)
        assert shift.clock_out is None
        db.drop_all()


def test_delete_shift_is_owner_scoped():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        shift = Shift(user_id=12, clock_in=datetime(2026, 10, 31, 8, 30))
        db.session.add(shift)
        db.session.commit()
        shift_id = shift.id

    client = app.test_client()
    with client.session_transaction() as user_session:
        user_session["user_id"] = 34

    response = client.delete(f"/shifts/{shift_id}")
    assert response.status_code == 404
    assert response.json == {"errors": ["Shift not found"]}

    with client.session_transaction() as user_session:
        user_session["user_id"] = 12

    response = client.delete(f"/shifts/{shift_id}")
    assert response.status_code == 200
    assert response.json == {}

    with app.app_context():
        assert Shift.query.count() == 0
        db.drop_all()
