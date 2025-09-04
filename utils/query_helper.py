import re
from datetime import datetime

def convert_postgres_to_oracle(query):
    """
    Convert a PostgreSQL query to Oracle 21c compatible syntax
    """
    # Store original for reference
    original_query = query
    
    # 1. Handle JSON functions first (they might contain other functions)
    query = convert_json_functions(query)
    
    # 2. Handle data type conversions
    query = convert_data_types(query)
    
    # 3. Handle LIMIT/OFFSET (pagination)
    query = convert_pagination(query)
    
    # 4. Handle datetime functions and formats
    query = convert_datetime_functions(query)
    
    # 5. Handle string functions
    query = convert_string_functions(query)
    
    # 6. Handle aggregate functions
    query = convert_aggregate_functions(query)
    
    # 7. Handle boolean expressions
    query = convert_boolean_expressions(query)
    
    # 8. Handle other PostgreSQL-specific syntax
    query = convert_other_syntax(query)
    
    # 9. Handle JOIN syntax differences
    query = convert_join_syntax(query)
    
    # 10. Add FROM DUAL where needed
    query = add_dual_table(query)
    
    # 11. Handle date literals and formats
    query = convert_date_literals(query)
    
    # 12. Final cleanup
    query = final_cleanup(query)
    
    return query

def convert_data_types(query):
    """Convert PostgreSQL data types to Oracle equivalents"""
    type_mappings = {
        r'\bSERIAL\b': 'NUMBER GENERATED ALWAYS AS IDENTITY',
        r'\bBIGSERIAL\b': 'NUMBER GENERATED ALWAYS AS IDENTITY',
        r'\bINTEGER\b': 'NUMBER(10)',
        r'\bINT\b': 'NUMBER(10)',
        r'\bBIGINT\b': 'NUMBER(19)',
        r'\bSMALLINT\b': 'NUMBER(5)',
        r'\bBOOLEAN\b': 'NUMBER(1)',
        r'\bBOOL\b': 'NUMBER(1)',
        r'\bDOUBLE PRECISION\b': 'BINARY_DOUBLE',
        r'\bREAL\b': 'BINARY_FLOAT',
        r'\bTEXT\b': 'CLOB',
        r'\bBYTEA\b': 'BLOB',
        r'\bCHARACTER VARYING\b': 'VARCHAR2',
        r'\bVARCHAR\b': 'VARCHAR2',
        r'\bTIMESTAMP\s+WITHOUT TIME ZONE\b': 'TIMESTAMP',
        r'\bTIMESTAMP\s+WITH TIME ZONE\b': 'TIMESTAMP WITH TIME ZONE',
        r'\bTIME\s+WITHOUT TIME ZONE\b': 'TIMESTAMP',
        r'\bTIME\s+WITH TIME ZONE\b': 'TIMESTAMP WITH TIME ZONE',
    }
    
    for pattern, replacement in type_mappings.items():
        query = re.sub(pattern, replacement, query, flags=re.IGNORECASE)
    
    return query

def convert_pagination(query):
    """Convert PostgreSQL LIMIT/OFFSET to Oracle ROWNUM/FETCH FIRST"""
    # Check if LIMIT or OFFSET exists
    has_limit = re.search(r'\bLIMIT\b', query, re.IGNORECASE)
    has_offset = re.search(r'\bOFFSET\b', query, re.IGNORECASE)
    
    if has_limit or has_offset:
        # Extract limit and offset values
        limit_match = re.search(r'\bLIMIT\s+(\d+)\b', query, re.IGNORECASE)
        offset_match = re.search(r'\bOFFSET\s+(\d+)\b', query, re.IGNORECASE)
        
        limit = int(limit_match.group(1)) if limit_match else None
        offset = int(offset_match.group(1)) if offset_match else 0
        
        # Remove LIMIT and OFFSET clauses
        query = re.sub(r'\bLIMIT\s+\d+\b', '', query, flags=re.IGNORECASE)
        query = re.sub(r'\bOFFSET\s+\d+\b', '', query, flags=re.IGNORECASE)
        
        # For simple cases, use ROWNUM
        if not offset and limit:
            # Add ROWNUM condition
            query = re.sub(r'\bWHERE\b', f'WHERE ROWNUM <= {limit} AND', query, flags=re.IGNORECASE)
            if 'WHERE' not in query.upper():
                # If no WHERE clause, add ROWNUM condition at the end
                query += f" WHERE ROWNUM <= {limit}"
        elif offset or limit:
            # For more complex cases with OFFSET, use ROW_NUMBER()
            # This requires wrapping the original query
            order_by_match = re.search(r'ORDER BY(.+?)(?=LIMIT|OFFSET|$)', query, re.IGNORECASE)
            if order_by_match:
                order_clause = order_by_match.group(1)
                # Wrap the query with ROW_NUMBER()
                query = f"SELECT * FROM ({query}) WHERE ROWNUM BETWEEN {offset + 1} AND {offset + limit if limit else 'UNBOUNDED'}"
    
    return query

def convert_datetime_functions(query):
    """Convert PostgreSQL datetime functions to Oracle equivalents"""
    # NOW() -> SYSDATE
    query = re.sub(r'\bNOW\(\)', 'SYSDATE', query, flags=re.IGNORECASE)
    
    # CURRENT_TIMESTAMP -> SYSTIMESTAMP
    query = re.sub(r'\bCURRENT_TIMESTAMP\b', 'SYSTIMESTAMP', query, flags=re.IGNORECASE)
    
    # CURRENT_DATE remains the same in Oracle
    
    # AGE() function - complex conversion
    age_pattern = r'\bAGE\(([^)]+)\)'
    age_matches = re.finditer(age_pattern, query, re.IGNORECASE)
    for match in age_matches:
        params = match.group(1).split(',')
        if len(params) == 1:
            # AGE(timestamp) - time elapsed since timestamp
            original = match.group(0)
            replacement = f"NUMTODSINTERVAL(SYSDATE - {params[0].strip()}, 'DAY')"
            query = query.replace(original, replacement)
        elif len(params) == 2:
            # AGE(timestamp, timestamp) - difference between two timestamps
            original = match.group(0)
            replacement = f"NUMTODSINTERVAL({params[1].strip()} - {params[0].strip()}, 'DAY')"
            query = query.replace(original, replacement)
    
    # EXTRACT() - mostly the same but some part names differ
    query = re.sub(r'\bEXTRACT\((\w+)\s+FROM', r'EXTRACT(\1 FROM', query, flags=re.IGNORECASE)
    
    # DATE_PART() -> EXTRACT()
    query = re.sub(r'\bDATE_PART\(([^)]+)\)', r'EXTRACT(\1)', query, flags=re.IGNORECASE)
    
    # DATE_TRUNC() -> TRUNC()
    query = re.sub(r'\bDATE_TRUNC\(([^)]+)\)', r'TRUNC(\1)', query, flags=re.IGNORECASE)
    
    # TO_CHAR/TO_DATE format strings may need adjustment
    # PostgreSQL uses YYYY-MM-DD HH24:MI:SS, Oracle uses similar but with slight differences
    
    # Interval arithmetic
    query = re.sub(r"INTERVAL\s+'([^']+)'", r"NUMTODSINTERVAL(\1)", query, flags=re.IGNORECASE)
    
    return query

def convert_string_functions(query):
    """Convert PostgreSQL string functions to Oracle equivalents"""
    # ILIKE -> UPPER() comparison
    ilike_pattern = r'([^\s]+)\s+ILIKE\s+([^\s]+)'
    ilike_matches = re.finditer(ilike_pattern, query, re.IGNORECASE)
    for match in ilike_matches:
        original = match.group(0)
        column = match.group(1)
        pattern = match.group(2)
        replacement = f"UPPER({column}) LIKE UPPER({pattern})"
        query = query.replace(original, replacement)
    
    # CONCAT_WS() - not directly available in Oracle
    concat_ws_pattern = r"CONCAT_WS\(([^)]+)\)"
    concat_ws_matches = re.finditer(concat_ws_pattern, query, re.IGNORECASE)
    for match in concat_ws_matches:
        params = [p.strip() for p in match.group(1).split(',')]
        if len(params) > 1:
            separator = params[0]
            fields = params[1:]
            # Build NVL2 chain to handle NULLs
            replacement = f"{fields[0]}"
            for i in range(1, len(fields)):
                replacement = f"NVL2({replacement}, {replacement} || {separator} || {fields[i]}, {fields[i]})"
            query = query.replace(match.group(0), replacement)
    
    # Other string functions that are the same or similar
    # PostgreSQL: LENGTH() -> Oracle: LENGTH() (same)
    # PostgreSQL: SUBSTRING() -> Oracle: SUBSTR()
    query = re.sub(r'\bSUBSTRING\(', 'SUBSTR(', query, flags=re.IGNORECASE)
    
    return query

def convert_aggregate_functions(query):
    """Convert PostgreSQL aggregate functions to Oracle equivalents"""
    # COUNT(*) remains the same
    
    # BOOL_AND() -> MIN() with CASE (since Oracle doesn't have BOOL_AND)
    query = re.sub(r'\bBOOL_AND\(([^)]+)\)', r'MIN(CASE WHEN \1 THEN 1 ELSE 0 END)', query, flags=re.IGNORECASE)
    
    # BOOL_OR() -> MAX() with CASE
    query = re.sub(r'\bBOOL_OR\(([^)]+)\)', r'MAX(CASE WHEN \1 THEN 1 ELSE 0 END)', query, flags=re.IGNORECASE)
    
    # STRING_AGG() -> LISTAGG()
    query = re.sub(r'\bSTRING_AGG\(([^)]+)\)', r'LISTAGG(\1)', query, flags=re.IGNORECASE)
    
    # Handle FILTER clause (PostgreSQL specific)
    filter_pattern = r'(\w+)\(([^)]+)\)\s+FILTER\s*\(\s*WHERE\s+([^)]+)\s*\)'
    filter_matches = re.finditer(filter_pattern, query, re.IGNORECASE)
    for match in filter_matches:
        agg_func = match.group(1)
        agg_expr = match.group(2)
        filter_cond = match.group(3)
        replacement = f"{agg_func}(CASE WHEN {filter_cond} THEN {agg_expr} ELSE NULL END)"
        query = query.replace(match.group(0), replacement)
    
    return query

def convert_boolean_expressions(query):
    """Convert PostgreSQL boolean expressions to Oracle equivalents"""
    # true -> 1
    query = re.sub(r'\btrue\b', '1', query, flags=re.IGNORECASE)
    
    # false -> 0
    query = re.sub(r'\bfalse\b', '0', query, flags=re.IGNORECASE)
    
    # IS TRUE -> = 1
    query = re.sub(r'\bIS TRUE\b', '= 1', query, flags=re.IGNORECASE)
    
    # IS FALSE -> = 0
    query = re.sub(r'\bIS FALSE\b', '= 0', query, flags=re.IGNORECASE)
    
    # IS NOT TRUE -> != 1
    query = re.sub(r'\bIS NOT TRUE\b', '!= 1', query, flags=re.IGNORECASE)
    
    # IS NOT FALSE -> != 0
    query = re.sub(r'\bIS NOT FALSE\b', '!= 0', query, flags=re.IGNORECASE)
    
    return query

def convert_json_functions(query):
    """Convert PostgreSQL JSON functions to Oracle equivalents"""
    # Convert JSON_OBJECT
    query = convert_json_object(query)
    
    return query

def convert_json_object(query):
    """Convert PostgreSQL JSON_OBJECT to Oracle JSON_OBJECT with VALUE keyword"""
    # Pattern to match JSON_OBJECT function calls
    json_object_pattern = r'json_object\(((?:[^()]|\((?:(?:[^()]|\([^()]*\))*)\))*)\)'
    
    # Find all JSON_OBJECT calls
    json_object_matches = re.finditer(json_object_pattern, query, re.IGNORECASE)
    
    for match in json_object_matches:
        original = match.group(0)
        params = match.group(1)
        
        # Split parameters while handling nested functions
        param_list = []
        current_param = ""
        paren_count = 0
        in_quotes = False
        quote_char = None
        
        for char in params:
            if char in ('"', "'") and not in_quotes:
                in_quotes = True
                quote_char = char
                current_param += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_param += char
            elif char == '(' and not in_quotes:
                paren_count += 1
                current_param += char
            elif char == ')' and not in_quotes:
                paren_count -= 1
                current_param += char
            elif char == ',' and not in_quotes and paren_count == 0:
                param_list.append(current_param.strip())
                current_param = ""
            else:
                current_param += char
        
        if current_param:
            param_list.append(current_param.strip())
        
        # Check if it's already in Oracle format (has VALUE keyword)
        has_value_keyword = any('VALUE' in param.upper() for param in param_list)
        
        if not has_value_keyword and len(param_list) % 2 == 0:
            # Convert to Oracle format
            oracle_params = []
            for i in range(0, len(param_list), 2):
                key = param_list[i]
                value = param_list[i + 1]
                oracle_params.append(f"{key} VALUE {value}")
            
            # Rebuild the JSON_OBJECT call
            oracle_json_object = f"JSON_OBJECT({', '.join(oracle_params)})"
            query = query.replace(original, oracle_json_object)
    
    return query

def convert_other_syntax(query):
    """Convert other PostgreSQL-specific syntax to Oracle"""
    # :: casting to CAST function
    query = re.sub(r'([^:]+)::([^\s]+)', r'CAST(\1 AS \2)', query)
    
    # Dollar quoting ($$) to standard quoting
    query = re.sub(r'\$\$(.*?)\$\$', r"'\1'", query)
    
    # GENERATED ALWAYS AS IDENTITY
    query = re.sub(r'GENERATED\s+ALWAYS\s+AS\s+IDENTITY', 'GENERATED ALWAYS AS IDENTITY', query, flags=re.IGNORECASE)
    
    # RETURNING clause (handled differently in Oracle DML)
    if 'RETURNING' in query.upper():
        # This is complex and might need manual adjustment
        # For now, just comment it out
        query = re.sub(r'\bRETURNING\b', '-- RETURNING (Oracle uses RETURNING INTO for DML)', query, flags=re.IGNORECASE)
    
    return query

def convert_join_syntax(query):
    """Convert JOIN syntax differences"""
    # FULL OUTER JOIN -> FULL JOIN (Oracle syntax)
    query = re.sub(r'\bFULL OUTER JOIN\b', 'FULL JOIN', query, flags=re.IGNORECASE)
    
    # PostgreSQL: USING (column) -> Oracle: ON table1.column = table2.column
    using_pattern = r'\bJOIN\s+(\w+)\s+USING\s*\((\w+)\)'
    using_matches = re.finditer(using_pattern, query, re.IGNORECASE)
    for match in using_matches:
        table = match.group(1)
        column = match.group(2)
        # Find the previous table in the JOIN
        prev_table = find_previous_table(query, match.start())
        if prev_table:
            replacement = f"JOIN {table} ON {prev_table}.{column} = {table}.{column}"
            query = query[:match.start()] + replacement + query[match.end():]
    
    return query

def find_previous_table(query, position):
    """Helper function to find the previous table in a JOIN clause"""
    # Look backward for the previous table reference
    # This is a simplified approach
    prev_part = query[:position]
    tables = re.findall(r'\b(FROM|JOIN)\s+(\w+)', prev_part, re.IGNORECASE)
    if tables:
        return tables[-1][1]  # Return the last table found
    return None

def add_dual_table(query):
    """Add FROM DUAL where needed for Oracle"""
    # Fixed the regex pattern that was causing the error
    # Check if it's a SELECT without FROM
    if re.match(r'^\s*SELECT\s', query, re.IGNORECASE) and not re.search(r'\bFROM\b', query, re.IGNORECASE):
        # Simple SELECT without FROM
        query += ' FROM DUAL'
    
    return query

def convert_date_literals(query):
    """Convert date literals to Oracle format"""
    # Convert PostgreSQL date format (YYYY-MM-DD) to Oracle TO_DATE format
    # Pattern to match date comparisons
    date_pattern = r"(\w+\.?\w*\s*(?:>=|<=|=|>|<)\s*)'(\d{4}-\d{2}-\d{2})'"
    
    def replace_date(match):
        column_op = match.group(1)
        date_str = match.group(2)
        return f"{column_op}TO_DATE('{date_str}', 'YYYY-MM-DD')"
    
    query = re.sub(date_pattern, replace_date, query, flags=re.IGNORECASE)
    
    # Convert timestamp format if needed
    timestamp_pattern = r"(\w+\.?\w*\s*(?:>=|<=|=|>|<)\s*)'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'"
    
    def replace_timestamp(match):
        column_op = match.group(1)
        timestamp_str = match.group(2)
        return f"{column_op}TO_TIMESTAMP('{timestamp_str}', 'YYYY-MM-DD HH24:MI:SS')"
    
    query = re.sub(timestamp_pattern, replace_timestamp, query, flags=re.IGNORECASE)
    
    return query

def final_cleanup(query):
    """Final cleanup and formatting"""
    # Remove extra whitespace
    query = re.sub(r'\s+', ' ', query)
    query = query.strip()
    
    # Ensure semicolon at the end
    if not query.endswith(';'):
        query += ';'
    
    return query