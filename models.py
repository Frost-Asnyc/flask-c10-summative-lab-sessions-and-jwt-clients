from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Shift(db.Model):
    """A single work shift owned by one user."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    clock_in = db.Column(db.DateTime, nullable=False)
    clock_out = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Shift {self.id} user={self.user_id}>"
