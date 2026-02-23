# services/db.py
from flask_sqlalchemy import SQLAlchemy

# Keep ORM instances usable after commit in common request/test flows.
db = SQLAlchemy(session_options={"expire_on_commit": False})
