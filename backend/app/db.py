import os
from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "zuna.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DATABASE.as_posix()}")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_order_checkout_columns(database_engine: Engine = engine) -> None:
    tables = set(inspect(database_engine).get_table_names())
    migrations = {
        "orders": {
            "payment_method": "VARCHAR(20)",
            "delivery_name": "VARCHAR(100)",
            "delivery_phone": "VARCHAR(30)",
            "delivery_address": "TEXT",
            "size": "VARCHAR(30)",
        },
        "product_orders": {
            "size": "VARCHAR(30)",
        },
    }
    with database_engine.begin() as connection:
        inspector = inspect(connection)
        for table, new_columns in migrations.items():
            if table not in tables:
                continue
            columns = {
                column["name"]
                for column in inspector.get_columns(table)
            }
            for name, definition in new_columns.items():
                if name not in columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
