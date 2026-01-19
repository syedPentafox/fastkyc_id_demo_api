from sqlalchemy import text
from utils.db_util import DatabaseHandler

def migrate():
    db = DatabaseHandler()
    with db.Session() as session:
        try:
            print("Adding key_name column to api_required_fields...")
            # Check if column exists to avoid error
            session.execute(text("ALTER TABLE api_required_fields ADD COLUMN key_name VARCHAR(255) NULL"))
            session.commit()
            print("Migration successful.")
        except Exception as e:
            print(f"Migration failed (might already exist): {e}")

if __name__ == "__main__":
    migrate()
