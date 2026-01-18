from utils.db_util import DatabaseHandler
from sqlalchemy import text

db = DatabaseHandler()

def patch_db():
    print("Patching DB...")
    with db.Session() as session:
        try:
            session.execute(text("ALTER TABLE active_flows ADD COLUMN journey_state JSON NULL;"))
            session.commit()
            print("✅ Column journey_state added to active_flows")
        except Exception as e:
            print(f"⚠️ Error (maybe already exists): {e}")

if __name__ == "__main__":
    patch_db()
