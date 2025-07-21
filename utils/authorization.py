import logging
import os

import requests

from sqlalchemy import text

from utils.db_util import session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")


def get_external_api_details(type=None):
    _result = session.execute(
        text(
            f"""SELECT id, type, base_url_uat, base_url_prod, payload, api_path, uat_header,prod_header,
            mode FROM m_external_api WHERE type = '{type}' AND is_current=1"""
        )
    )
    if _result:
        _result = _result[0]
        data = {
            "url": _result.get("base_url_{}".format(ENVIRONMENT.lower())),
            "mode": _result.get("mode"),
            "api_path": _result.get("api_path"),
            "payload": _result.get("payload"),
            "header": _result.get("{}_header".format(ENVIRONMENT.lower())),
        }
        return data


def check_access(user_id, roles, resources):
    """
    This function construct the payload to CERBOS and hit the check resource API
    Args:
        user_id (int): UserID
        roles (list): RoleName
        resources (list): Resources that the user trying to access.

    Returns:
        dict: Return the response from cerbos
    """
    _request_details = get_external_api_details("CERBOS")
    _url = _request_details.get("url") + "/api/check/resources"
    payload = {
        "principal": {"id": str(user_id), "roles": roles},
        "resources": resources,
    }
    return requests.post(url=_url, json=payload).json()
