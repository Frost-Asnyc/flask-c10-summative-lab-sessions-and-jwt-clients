from datetime import datetime

from app import create_app
from models import Shift, db


def test_shift_model_uses_the_shared_person_c_fields():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

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
