from orm_model.core_models import engine, SessionLocal, Base
from utils.db_util import DatabaseHandler

db = DatabaseHandler()

# Re-exporting for backward compatibility or convenience
__all__ = ["engine", "SessionLocal", "Base"]
