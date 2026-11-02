from models import User, Note, db


def create_user_and_login(client, username="testuser"):
    client.post(
        "/signup",
        json={
            "username": username,
            "password": "password123",
            "confirm_password": "password123"
        }
    )


def test_get_notes_requires_authentication(client):
    response = client.get("/notes")

    assert response.status_code == 401


def test_create_note_requires_authentication(client):
    response = client.post(
        "/notes",
        json={"title": "My First Note", "content": "Hello"}
    )

    assert response.status_code == 401


def test_create_note_success(client):
    create_user_and_login(client)

    response = client.post(
        "/notes",
        json={
            "title": "My First Note",
            "content": "This is my note."
        }
    )

    assert response.status_code == 201
    assert response.json["title"] == "My First Note"
    assert response.json["content"] == "This is my note."


def test_create_note_without_title(client):
    create_user_and_login(client)

    response = client.post(
        "/notes",
        json={"content": "A note without a title"}
    )

    assert response.status_code == 400


def test_get_notes_success(client):
    create_user_and_login(client)

    client.post(
        "/notes",
        json={"title": "Note One", "content": "First note"}
    )

    response = client.get("/notes")

    assert response.status_code == 200
    assert response.json["total"] == 1
    assert len(response.json["notes"]) == 1


def test_get_single_note_success(client):
    create_user_and_login(client)

    create_response = client.post(
        "/notes",
        json={"title": "My Note", "content": "Note content"}
    )

    note_id = create_response.json["id"]

    response = client.get(f"/notes/{note_id}")

    assert response.status_code == 200
    assert response.json["title"] == "My Note"


def test_get_nonexistent_note(client):
    create_user_and_login(client)

    response = client.get("/notes/999")

    assert response.status_code == 404


def test_update_note_success(client):
    create_user_and_login(client)

    create_response = client.post(
        "/notes",
        json={"title": "Old Title", "content": "Old content"}
    )

    note_id = create_response.json["id"]

    response = client.patch(
        f"/notes/{note_id}",
        json={
            "title": "Updated Title",
            "content": "Updated content"
        }
    )

    assert response.status_code == 200
    assert response.json["title"] == "Updated Title"
    assert response.json["content"] == "Updated content"


def test_update_note_with_blank_title(client):
    create_user_and_login(client)

    create_response = client.post(
        "/notes",
        json={"title": "My Note", "content": "Content"}
    )

    note_id = create_response.json["id"]

    response = client.patch(
        f"/notes/{note_id}",
        json={"title": "   "}
    )

    assert response.status_code == 400


def test_delete_note_success(client):
    create_user_and_login(client)

    create_response = client.post(
        "/notes",
        json={"title": "Note to Delete", "content": "Delete me"}
    )

    note_id = create_response.json["id"]

    response = client.delete(f"/notes/{note_id}")

    assert response.status_code == 200

    get_response = client.get(f"/notes/{note_id}")
    assert get_response.status_code == 404