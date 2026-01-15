

from utils.error_handler import error_failure_response


def validate_feature_flow_apis(apis, db):
    if not apis:
        return error_failure_response("At least one API must be provided", 422)

    # Load valid API ids
    feature_ids, _ = db.get_data_from_table("features_master", ["id"], {}, page = -1)
    valid_ids = {row["id"] for row in feature_ids}

    orders = []
    seen_ids = set()

    for index, api in enumerate(apis):

        # ID must be unique in this flow
        if api.id in seen_ids:
            return error_failure_response(
                f"Duplicate API id {api.id} found in flow", 422
            )
        seen_ids.add(api.id)
  
        # ID must exist in DB
        if api.id not in valid_ids:
            return error_failure_response(
                f"Invalid API id {api.id} at position {index}", 400
            )

        # Order must be integer
        if not isinstance(api.order, int):
            return error_failure_response(
                f"Order must be integer for API id {api.id}", 422
            )

        orders.append(api.order)

    # Order must start from 1
    if orders[0] != 1:
        return error_failure_response("Order must start from 1", 422)

    # Order must not skip
    for i in range(1, len(orders)):
        if orders[i] != orders[i - 1] and orders[i] != orders[i - 1] + 1:
            return error_failure_response(
                f"Invalid order at index {i}: {orders[i]} after {orders[i - 1]}",
                422
            )

    return None
