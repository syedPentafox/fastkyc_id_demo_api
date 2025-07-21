import sqlparse
import copy


def extract_column_names(query):
    parsed = sqlparse.parse(query)[0]
    column_names = []

    # Iterate over the tokens in the query
    for token in parsed.tokens:
        # Find the IdentifierList, which holds multiple columns
        if isinstance(token, sqlparse.sql.IdentifierList):
            for identifier in token.get_identifiers():
                # Get alias name if present (after AS), else get the real name
                alias = identifier.get_alias()
                if alias:
                    column_names.append(alias)
                else:
                    column_names.append(identifier.get_real_name())

        # Single identifiers
        elif isinstance(token, sqlparse.sql.Identifier):
            alias = token.get_alias()
            if alias:
                column_names.append(alias)
            else:
                column_names.append(token.get_real_name())

    return column_names


def generate_report_column_title_map(column_names):
    """This will take the column as key and convert that into title case by replacing the underscores with spaces"""
    column_title_cased_column_map = dict()
    for column in column_names:
        column_title_cased_column_map.update({column: column.replace("_", " ").title()})
    return column_title_cased_column_map


def kv_pair_cleaning(kv_pair, exclude_keys=[], exclusion_prefix="hidden"):
    # Create a deep copy of the original dictionary
    kv_pair_copy = copy.deepcopy(kv_pair)

    # Iterate through a list of keys instead of directly on kv_pair_copy.keys()
    # This prevents issues when deleting keys while iterating
    for key in list(kv_pair_copy.keys()):
        if key in exclude_keys or exclusion_prefix in key.lower():
            del kv_pair_copy[key]

    return kv_pair_copy


if __name__ == "__main__":
    # Your SQL query
    query = """
    SELECT
        CONCAT(depart.airport_code, '-', arrive.airport_code) AS sector,
        COUNT(jl.id) AS journey_leg_count,
        SUM(CASE WHEN LENGTH(jo.seat) > 0 THEN 1 ELSE 0 END) AS actual_buyer_count,
        SUM(jo.price) AS total_sales,
        SUM(CASE WHEN joi.product_name = 'Cookies - Pack of 4' THEN 1 ELSE 0 END) AS "Cookies - Pack of 4",
        SUM(CASE WHEN joi.product_name = 'Caramel Coconut Cashews' THEN 1 ELSE 0 END) AS "Caramel Coconut Cashews"
    """

    # Extract and print column names
    column_names = extract_column_names(query)
    print(column_names)
