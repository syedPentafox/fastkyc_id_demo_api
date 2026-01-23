from fastapi import APIRouter, Depends, HTTPException
from utils.db_util import DatabaseHandler
from response_models.response_models import make_success_response

router = APIRouter()
db_handler = DatabaseHandler()

@router.get("/health-check")
def health_check():
    return {"message": "Application running successfully"}

@router.get("/db-check")
def db_check():
    # Simple check using execute_query from handler
    result = db_handler.get_data_from_table("customers", ["*,*"])
    print("-----DB", result)
    if result:
        return make_success_response(result, "Db Working Function is also working")
    raise HTTPException(status_code=500, detail="Database connection Check Failed")

@router.get("/tables")
def list_tables():
    return {"tables": db_handler.tables}

@router.get("/data/{table_name}")
def get_table_data(table_name: str, page: int = 1, per_page: int = 10):
    return db_handler.get_data_from_table(table_name, page=page, per_page=per_page)

@router.post("/mock/provider")
def mock_provider(payload: dict = None):
    # Simulate Success Response expected by FastKYCConnector
    return {
        "status": "SUCCESS",
        "success": True,
        "message": "Mock Success",
        "data": {
            "client_id": "mock_client_123", # For polling logic
            "url": "http://example.com/redirect" # For redirect logic
        }
    }
