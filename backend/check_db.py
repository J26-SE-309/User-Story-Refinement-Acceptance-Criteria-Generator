from sqlalchemy import text
from app.db import engine

with engine.connect() as connection:
    result = connection.execute(text("SELECT 1"))
    print("Database connection successful:", result.scalar())
    