from fastapi.responses import ORJSONResponse
from fastapi.encoders import jsonable_encoder


def make_success_response(data=[], message="success", metadata=[], **kwargs):
    return ORJSONResponse(
        {
            "data": jsonable_encoder(data),
            "metadata": metadata,
            "status": "success",
            "message": message,
            **kwargs,
        }
    )


def make_failure_response(message, data=[], **kwargs):
    return ORJSONResponse(
        {"data": data, "metadata": [], "status": "error", "message": message, **kwargs}
    )
