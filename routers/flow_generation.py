from fastapi import APIRouter, Depends, HTTPException, Request
from utils.authentication import verify_access_token
from utils.custom_class import APIRouteWrapper
from utils.db_util import DatabaseHandler
from response_models.response_models import make_success_response

router = APIRouter(dependencies=[Depends(verify_access_token)])
db = DatabaseHandler()



@router.post("/flow/initiate",tags=["flow"])
def initiate_id_flow():
    return make_success_response()


@router.get("/flow/features", tags=['flow'])
def get_all_features_flows(request: Request):
    print("user ID from the route",request.state.user_id)
    
    return make_success_response()