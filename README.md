# Productivity API

A Flask API for a productivity app. It provides session-based authentication, JWT login responses with a JWT-protected current-user endpoint, a user-owned notes resource, and shift clock-in/clock-out endpoints.

## Project Overview

The Productivity API is designed to support users in managing their daily productivity activities. It provides authentication, personal notes management, and employee shift tracking.

Users can register and log in, manage their own notes, and record their working hours through clock-in and clock-out operations.

The API uses session-based authentication to protect notes and shift resources, while also providing JWT authentication for the current-user endpoint.

## Project Objectives

- Provide secure user registration and login.
- Allow users to manage their personal notes.
- Support pagination when retrieving notes.
- Record employee shift start and finish times.
- Protect user data through ownership checks.
- Verify important application functionality through automated tests

## Team contributions

| Assignment | Responsibility | Contributor |
|---|---|---|
| Person A | Project setup and database foundation | |
| Person B | Authentication | |
| Person C | Shift CRUD and pagination | |
| Person D | Shift clock-in/clock-out logic and ownership security | **Lerionka Olentiki** |
| Person E | Testing, documentation, and final delivery | |

### Person D — Lerionka Olentiki

Implemented the shift clock-in and clock-out workflow in `shift_routes.py` and added the corresponding shift route tests in `tests/test_app.py`.

- Added `POST /shifts/clock-in` to create a shift for the user identified by the Flask session.
- Prevented a user from starting another shift while an active shift (one with no `clock_out`) already exists.
- Added `PATCH /shifts/<shift_id>/clock-out` to close an active shift for its owner.
- Scoped shift lookup by both shift ID and current session user ID, so a user cannot clock out another user's shift; non-owned or missing shifts return `404`.
- Rejected attempts to clock out a shift that is already closed.
- Ensured the clock-out timestamp is later than the clock-in timestamp, returning a validation error if the rule is not met.
- Added tests for authentication requirements, successful clock-in/out, duplicate clock-in prevention, ownership isolation, and rejecting an already closed shift.

## Features

The Productivity API provides the following features:

- **User registration:** Allows new users to create accounts.
- **User login:** Authenticates users using their username and password.
- **Password security:** Stores passwords as bcrypt hashes instead of plain text.
- **Session management:** Uses Flask session cookies to maintain authenticated users.
- **JWT authentication:** Returns a JSON Web Token during signup and login.
- **Current-user verification:** Provides a JWT-protected `GET /me` endpoint.
- **Notes management:** Allows authenticated users to create, view, update, and delete their own notes.
- **Notes pagination:** Supports retrieving notes in pages.
- **Shift clock-in:** Records when a user starts a work shift.
- **Shift clock-out:** Records when a user finishes a work shift.
- **Ownership protection:** Prevents users from accessing notes or shifts belonging to other users.
- **Automated testing:** Uses pytest to test authentication, notes, and shift functionality.

## Technologies Used

### Backend

- **Python:** Main programming language used for the backend.
- **Flask:** Framework used to build the REST API.
- **Flask-SQLAlchemy:** Handles database models and database operations.
- **Flask-Migrate:** Manages database schema migrations.
- **Flask-Bcrypt:** Hashes and verifies user passwords.
- **PyJWT:** Creates and verifies JSON Web Tokens.
- **SQLite:** Default database configuration.
- **pytest:** Runs automated backend tests.

### Frontend

The project contains two separate React applications:

- `client-with-jwt` — React client designed around JWT authentication.
- `client-with-sessions` — React client designed around session-based authentication.

Both frontend applications use React 17, React Router, and styled-components.

### Development tools

- **Pipenv:** Manages Python dependencies and the virtual environment.
- **npm:** Installs and manages frontend dependencies.
- **Git and GitHub:** Used for version control and team collaboration.


## Requirements

- Python 3.8 or newer
- Pipenv
- Git

## Install and run

From the repository root:

```bash
pipenv install --dev
```

Set a private secret key before running the app. Do not use the development fallback in a deployed environment.

```bash
export SECRET_KEY="replace-with-a-long-random-secret"
```

Optionally set `DATABASE_URL` to use a different SQLAlchemy database. By default, the app uses the SQLite database `shifts.db` in the instance directory.

Run the API on port `5555`:

```bash
pipenv run python app.py
```

## Database migrations

The project uses Flask-Migrate. Initialize the migration repository once, then create and apply the initial migration:

```bash
pipenv run flask --app app db init
pipenv run flask --app app db migrate -m "Create users, notes, and shifts"
pipenv run flask --app app db upgrade
```

After model changes, create and apply a new migration:

```bash
pipenv run flask --app app db migrate -m "Describe the schema change"
pipenv run flask --app app db upgrade
```

Do not run `db init` again after the migrations directory has been created. The repository currently does not include a seed script or predefined user data; create users through `POST /signup`.

## Authentication

The API supports session cookies and issues JWTs, but protected resource routes currently authenticate using the Flask session cookie. The JWT is currently accepted by `GET /me`; it is not yet a substitute for the session on the notes or shifts endpoints.

For browser clients, send JSON requests with `Content-Type: application/json`. Keep the session cookie between requests.

### `POST /signup`

Creates a user, hashes their password, starts a session, and returns a JWT.

Request:

```json
{
  "username": "alex",
  "password": "example-password",
  "password_confirmation": "example-password"
}
```

Success response (`201 Created`):

```json
{
  "id": 1,
  "username": "alex",
  "token": "<JWT>",
  "user": {
    "id": 1,
    "username": "alex"
  }
}
```

### `POST /login`

Authenticates an existing user and starts a session. The response has the same fields as signup; successful login returns `200 OK`. Invalid credentials return `401 Unauthorized`.

Request:

```json
{
  "username": "alex",
  "password": "example-password"
}
```

### `GET /check_session`

Returns the current session user:

```json
{
  "id": 1,
  "username": "alex"
}
```

If no valid session exists, returns `{}` with `200 OK`.

### `DELETE /logout`

Clears the current session and returns `{}` with `200 OK`.

### `GET /me`

Verifies a JWT and returns its user. Send the token in the `Authorization` header:

```http
Authorization: Bearer <JWT>
```

Returns the user object with `200 OK`, or an authentication error with `401 Unauthorized`.

## Notes

All notes endpoints require a logged-in session. Each query is scoped to the current user; a user cannot read, update, or delete another user's note.

### `GET /notes`

Returns a page of the current user's notes. `page` defaults to `1`; `per_page` defaults to `10` and is limited to a maximum of `100`.

```http
GET /notes?page=1&per_page=10
```

Response:

```json
{
  "page": 1,
  "per_page": 10,
  "total": 1,
  "notes": [
    {
      "id": 1,
      "title": "Weekly plan",
      "content": "Finish tasks before Friday.",
      "user_id": 1
    }
  ]
}
```

### `POST /notes`

Creates a note for the current user. `title` is required; `content` defaults to an empty string.

```json
{
  "title": "Weekly plan",
  "content": "Finish tasks before Friday."
}
```

Returns the created note with `201 Created`.

### `GET /notes/<note_id>`

Returns one of the current user's notes. Returns `404 Not Found` if it does not exist or belongs to another user.

### `PATCH /notes/<note_id>`

Updates the supplied `title` and/or `content` fields. The title cannot be blank.

```json
{
  "title": "Updated plan"
}
```

Returns the updated note with `200 OK`.

### `DELETE /notes/<note_id>`

Deletes one of the current user's notes and returns `{}` with `200 OK`. Returns `404 Not Found` for missing notes or notes owned by another user.

## Shifts

Shift endpoints require a logged-in session and always filter by the current session user's ID.

### `POST /shifts/clock-in`

Creates a shift with the current UTC time as `clock_in` and `clock_out` set to `null`. Returns `201 Created`. If the user already has an active shift, returns `400 Bad Request`.

Example response:

```json
{
  "id": 1,
  "clock_in": "2026-10-31T08:30:00+00:00",
  "clock_out": null
}
```

### `PATCH /shifts/<shift_id>/clock-out`

Closes the current user's active shift using the current UTC time. Returns the updated shift with `200 OK`. Returns `404 Not Found` if the shift does not exist or belongs to another user, and `400 Bad Request` if it is already closed.

## Error responses

Errors use a JSON `errors` array. For example:

```json
{
  "errors": ["Authentication required"]
}
```

Common status codes are `400` for invalid input or business-rule violations, `401` for missing/invalid authentication, and `404` when a resource is not found or is not owned by the current user.

## Tests

Run the test suite with:

```bash
pipenv run pytest
```

The existing automated tests cover the shift model and clock-in/clock-out behavior, including authentication requirements and shift ownership. Auth and notes currently have not yet been added to the automated test suite.

## Project layout

- `app.py` — Flask application factory and blueprint registration.
- `config.py` — application and database configuration.
- `models.py` — database, user, note, and shift models.
- `auth_routes.py` — signup, login, session, logout, and JWT `/me` routes.
- `note_routes.py` — protected notes CRUD and pagination.
- `shift_routes.py` — protected shift clock-in and clock-out.
- `tests/` — pytest tests.
