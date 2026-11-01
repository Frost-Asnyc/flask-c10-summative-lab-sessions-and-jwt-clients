import random
from datetime import datetime, timedelta, timezone

from faker import Faker
from flask_bcrypt import Bcrypt

from app import create_app
from models import Note, Shift, User, db

fake = Faker()
bcrypt = Bcrypt()
PASSWORD= "password123"

app = create_app()

with app.app_context():
    Shift.query.delete()
    Note.query.delete()
    User.query.delete()
    db.session.commit()

    users = [
        User(
            username=name,
            password_hash=bcrypt.generate_password_hash(PASSWORD).decode("utf-8"),
        )
        for name in ["alice", "bob", "carol"]
    ]

    db.session.add_all(users)
    db.session.commit()

    now = datetime.now(timezone.utc)

    for user in users:
        # 15 completed shifts so pagination has something to page through
        for days_ago in range(1, 16):
            start = (now - timedelta(days=days_ago)).replace(
                hour=random.randint(6, 10), minute=random.choice([0, 15, 30, 45]),
                second=0, microsecond=0,
            )
            end = start + timedelta(hours=random.randint(4, 9))
            db.session.add(Shift(user_id=user.id, clock_in=start, clock_out=end))

        for _ in range(3):
            db.session.add(Note(
                title=fake.sentence(nb_words=4).rstrip("."),
                content=fake.paragraph(nb_sentences=2),
                user_id=user.id,
            ))

    # bob is currently clocked in, so Person D can test "no double clock-in"
    bob = users[1]
    db.session.add(Shift(user_id=bob.id, clock_in=now - timedelta(hours=2)))

    db.session.commit()
    print(f"Seeded users: {[u.username for u in users]} (password: {PASSWORD})")