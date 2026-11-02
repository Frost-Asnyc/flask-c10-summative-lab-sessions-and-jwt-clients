from datetime import datetime

import pytest

from app import create_app
from auth_routes import bcrypt
from models import Shift, User, db


def create_test_app():
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/shifts"),
        ("POST", "/shifts"),
        ("POST", "/shifts/clock-in"),
        ("GET", "/shifts/1"),
        ("PATCH", "/shifts/1"),
        ("DELETE", "/shifts/1"),
        ("PATCH", "/shifts/1/clock-out"),
    ],
)
def test_all_shift_routes_require_an_authenticated_session(method, path):
    app = create_test_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().open(path, method=method)

    assert response.status_code == 401
    assert response.json == {"errors": ["Authentication required"]}

    with app.app_context():
        db.drop_all()


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


def test_update_shift_rejects_invalid_timestamps_and_unknown_fields():
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

    invalid_timestamp = client.patch(
        f"/shifts/{shift_id}",
        json={"clock_in": "not-a-timestamp"},
    )
    assert invalid_timestamp.status_code == 400
    assert any("clock_in" in error for error in invalid_timestamp.json["errors"])

    unknown_field = client.patch(
        f"/shifts/{shift_id}",
        json={"user_id": 34},
    )
    assert unknown_field.status_code == 400
    assert any("user_id" in error for error in unknown_field.json["errors"])

    with app.app_context():
        saved_shift = db.session.get(Shift, shift_id)
        assert saved_shift.user_id == 12
        assert saved_shift.clock_in == datetime(2026, 10, 31, 8, 30)
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


def test_signup_creates_user_with_hashed_password_and_starts_session():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    response = client.post(
        "/signup",
        json={
            "username": "alex",
            "password": "safe-password",
            "password_confirmation": "safe-password",
        },
    )

    assert response.status_code == 201
    assert response.json["username"] == "alex"
    assert response.json["user"] == {
        "id": response.json["id"],
        "username": "alex",
    }
    assert response.json["token"]
    assert client.get("/check_session").json == response.json["user"]
    assert client.get(
        "/me",
        headers={"Authorization": f"Bearer {response.json['token']}"},
    ).json == response.json["user"]

    with app.app_context():
        user = db.session.get(User, response.json["id"])
        assert user.password_hash != "safe-password"
        assert bcrypt.check_password_hash(user.password_hash, "safe-password")
        db.drop_all()


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (
            {"username": "alex", "password": "safe-password"},
            "Password confirmation is required",
        ),
        (
            {
                "username": "alex",
                "password": "safe-password",
                "password_confirmation": "different-password",
            },
            "Passwords do not match",
        ),
        (
            {
                "username": 42,
                "password": "safe-password",
                "password_confirmation": "safe-password",
            },
            "Username is required",
        ),
        (
            {
                "username": "alex",
                "password": ["not", "a", "string"],
                "password_confirmation": "safe-password",
            },
            "Password is required",
        ),
        (
            {
                "username": "alex",
                "password": "safe-password",
                "password_confirmation": ["not", "a", "string"],
            },
            "Password confirmation is required",
        ),
        (
            {
                "username": "a" * 81,
                "password": "safe-password",
                "password_confirmation": "safe-password",
            },
            "Username must be 80 characters or fewer",
        ),
        (["not", "an", "object"], "Request body must be a JSON object"),
    ],
)
def test_signup_rejects_invalid_input_without_creating_a_user(payload, expected_error):
    app = create_test_app()
    with app.app_context():
        db.create_all()

    response = app.test_client().post("/signup", json=payload)

    assert response.status_code == 400
    assert expected_error in response.json["errors"]

    with app.app_context():
        assert User.query.count() == 0
        db.drop_all()


def test_signup_rejects_duplicate_usernames():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    payload = {
        "username": "alex",
        "password": "safe-password",
        "password_confirmation": "safe-password",
    }
    assert client.post("/signup", json=payload).status_code == 201

    duplicate_response = client.post("/signup", json=payload)

    assert duplicate_response.status_code == 400
    assert duplicate_response.json == {"errors": ["Username already exists"]}

    with app.app_context():
        assert User.query.count() == 1
        db.drop_all()


def test_login_validates_credentials_and_starts_session():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        user = User(
            username="alex",
            password_hash=bcrypt.generate_password_hash("safe-password").decode(
                "utf-8"
            ),
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    response = client.post(
        "/login",
        json={"username": "alex", "password": "safe-password"},
    )

    assert response.status_code == 200
    assert response.json["id"] == user_id
    assert response.json["user"] == {"id": user_id, "username": "alex"}
    assert response.json["token"]
    assert client.get("/check_session").json == response.json["user"]

    invalid_credentials = client.post(
        "/login",
        json={"username": "alex", "password": "wrong-password"},
    )
    assert invalid_credentials.status_code == 401
    assert invalid_credentials.json == {
        "errors": ["Invalid username or password"]
    }

    with app.app_context():
        db.drop_all()


def test_login_rejects_malformed_or_missing_credentials():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    non_object_response = client.post("/login", json=["invalid"])
    missing_password_response = client.post("/login", json={"username": "alex"})
    invalid_types_response = client.post(
        "/login",
        json={"username": "alex", "password": ["not", "a", "string"]},
    )

    assert non_object_response.status_code == 400
    assert non_object_response.json == {
        "errors": ["Request body must be a JSON object"]
    }
    assert missing_password_response.status_code == 400
    assert missing_password_response.json == {"errors": ["Password is required"]}
    assert invalid_types_response.status_code == 400
    assert invalid_types_response.json == {"errors": ["Password is required"]}

    with app.app_context():
        db.drop_all()


def test_logout_clears_session_and_check_session_handles_no_user():
    app = create_test_app()
    with app.app_context():
        db.create_all()
        user = User(
            username="alex",
            password_hash=bcrypt.generate_password_hash("safe-password").decode(
                "utf-8"
            ),
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    assert client.get("/check_session").status_code == 200
    assert client.get("/check_session").json == {}

    with client.session_transaction() as user_session:
        user_session["user_id"] = user_id
    assert client.get("/check_session").json == {"id": user_id, "username": "alex"}

    logout_response = client.delete("/logout")
    assert logout_response.status_code == 200
    assert logout_response.json == {}
    assert client.get("/check_session").json == {}

    with app.app_context():
        db.drop_all()


def test_me_rejects_missing_or_invalid_jwt():
    app = create_test_app()
    with app.app_context():
        db.create_all()

    client = app.test_client()
    missing_token = client.get("/me")
    invalid_token = client.get("/me", headers={"Authorization": "Bearer invalid"})

    assert missing_token.status_code == 401
    assert missing_token.json == {"errors": ["Authentication required"]}
    assert invalid_token.status_code == 401
    assert invalid_token.json == {"errors": ["Authentication required"]}

    with app.app_context():
        db.drop_all()
