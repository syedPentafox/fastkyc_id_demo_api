from fastapi.responses import JSONResponse

def error_failure_response(
    msg: str = "Something went wrong. Please try again later.",
    status_code: int = 400
):
    return JSONResponse(
        status_code=status_code,
        content={
            "error": True,
            "message": msg
        }
    )
