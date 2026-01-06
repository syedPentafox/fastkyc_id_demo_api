from orm_model.core_models import get_db, engine, SessionLocal, Base
from utils.db_util import DatabaseHandler

db = DatabaseHandler()

# Re-exporting for backward compatibility or convenience
__all__ = ["get_db", "engine", "SessionLocal", "Base"]
