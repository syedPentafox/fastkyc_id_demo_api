from fastapi import Query, UploadFile, File, APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from utils.db_connection import db
import json
from fastapi.encoders import jsonable_encoder
import logging
from utils.custom_class import APIRouteWrapper, CustomRequest
from utils.authentication import get_password_hash
from sqlalchemy import text
from response_models.response_models import make_failure_response, make_success_response
import pandas as pd
import io
from utils.metrics import MAX_FILE_SIZE_MB, MAX_RECORDS
from utils.file_storage import s3_file_upload
from math import ceil
import numpy as np

import random
import string
from utils.authentication import verify_access_token

from typing import List


router = APIRouter(
    route_class=APIRouteWrapper
)
router_no_auth = APIRouter(route_class=APIRouteWrapper)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Role(BaseModel):
    role: str


class DataItem(BaseModel):
    id: int
    name: str
    role: Role


class Metadata(BaseModel):
    page: int
    per_page: int
    total_number_of_page: int
    records: int


class ExampleResponse(BaseModel):
    data: List[DataItem]
    metadata: Metadata
    status: str
    message: str


security_scheme = [{"bearerAuth": []}]


router = APIRouter(
    route_class=APIRouteWrapper
)


class EncryptedPayload(BaseModel):
    encrypted_payload: str


@router.get(
    "/api/items/{collection}", response_model=ExampleResponse, tags=["Collection"]
)
def get_items(
    collection: str,
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    download_file_type: str = None,
):
    """
    Fetches a list of items from the specified collection with advanced filtering,
    sorting, and pagination options.

    - `collection`: The name of the collection to fetch items from.
    - `page`: The page number to retrieve, default is `1`.
    - `per_page`: Number of items per page, default is `10`. Must be greater than or equal to 1.
    - `fields`: Comma-separated list of fields to return. Default is `*.*` (all fields).
        - **Parent Table**:
            - `*`: Retrieves all fields from the parent table.
            - `id,name`: Retrieves specific fields from the parent table, such as `id` and `name`.
        - **Child Table**:
            - `*.*`: Retrieves all fields from the child table.
            - `role.role`: Retrieves a specific field `role` from a nested child table (e.g., `role` table).
            - `role.*`: Retrieves all fields from the child `role` table.
    - `filters`: A JSON string specifying filters for querying items. Filters can include
                various conditions for different fields.
        - **Syntax**:
        ```text
            filters={ <field>_<opreator> : <value> }
            filters={ <parent_field>.<child_field>_<opreator> : <value> }
        ```

        ### Example Use Cases for `filters` Parameter:

        1. **Filter by a Single Field Condition**:
        - Filters items where the `role` field equals 4.
        - **Parent Table**:
        ```text
        filters={ "role_eq": 4 }
        ```
        - **Child Table**:
        ```text
        filters={ "role.id_eq": 4 }
        ```

        2. **Filter with `AND` Conditions**:
        - Filters items where `name` equals `Gnana` and `role` equals 4.
        ```text
        filters={ "name_eq": "Gnana", "role_eq": 4 }
        ```

        3. **Filter with `OR` Condition**:
        - Filters items where `age` is between 18 and 30.
        ```text
        filters={ "or": [ { "role_eq": 4, "name_eq": "Gnana" } ] }
        ```

        4. **Filter with Nested Conditions**:
        - Filters items where a nested field `role.name` equals `admin`.
        ```text
        filters={ "and": [ { "or": [ { "role_eq":4, "name_eq":"Gnana" } ],
        "work_email_eq": "example@gmail.com" } ] }
        ```
        **Note: You can refer to the available filter conditions in the `metric.py` file.**
    - `search`: A search string to filter items based on specific text. Example: `search=TEST`.
    - `sort_by`: Comma-separated list of fields to sort by, can include a negative sign (`-`)
                for descending order. Example: `sort_by=-id,emp_name`.
    - `group_by`: Field to group the results by.
    - `aggregate`: Aggregation function to apply (e.g., `count`, `sum`).
    - `download_file_type`: To export the data, you need to specify the file type. Supported
                            file types are `xlsx` and `csv`.
    """

    columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    filters_dict = json.loads(filters) if filters else {}
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    if download_file_type:
        page = -1
        data, metadata = db.get_data_from_table(
            collection,
            columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return db.export_as_file(
            data=data, file_type=download_file_type, file_name=collection
        )
    data, metadata = db.get_data_from_table(
        collection,
        columns,
        filters_dict,
        search,
        sort_by,
        page,
        per_page,
        aggregate,
        group_by,
    )
    return make_success_response(
        data=data, message=f"{collection} retrived successful", metadata=metadata
    )


@router.get(
    "/api/items/{collection}/{record_id}",
    response_model=ExampleResponse,
    tags=["Collection"],
)
def get_item(collection: str, record_id: int, fields: str = "*.*"):
    """
    Fetches a individual item from the specified collection with advanced filtering,
    sorting, and pagination options.

    - `collection`: The name of the collection to fetch items from.
    - `record_id`: Unique indentification record.
    - `fields`: Comma-separated list of fields to return. Default is `*.*` (all fields).
        - **Parent Table**:
            - `*`: Retrieves all fields from the parent table.
            - `id,name`: Retrieves specific fields from the parent table, such as `id` and `name`.
        - **Child Table**:
            - `*.*`: Retrieves all fields from the child table.
            - `role.role`: Retrieves a specific field `role` from a nested child table (e.g., `role` table).
            - `role.*`: Retrieves all fields from the child `role` table.
    """
    columns = fields.split(",") if fields else []
    data = db.get_record_by_id(collection, record_id, columns)
    return make_success_response(
        data=data, message=f"{collection} record fetched successful", metadata=[]
    )


@router.post("/api/items/{collection}", tags=["Collection"])
def create_item(collection: str, item: dict, request: CustomRequest = None):
    """
    Create a new item in the specified collection.

    This endpoint allows you to create a new record in a specific collection. The `collection` parameter
    determines where the record will be inserted. The request body should contain the item data as a dictionary.

    **Path Parameters:**
    - `collection` (str): The name of the collection where the item will be created.

    **Request Body:**
    - `item` (dict): A dictionary containing the data for the new item. The structure of the item will depend
      on the collection and its requirements.

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success of the operation (e.g., `"success"`).
    - `message`: A message providing information about the operation result, such as success confirmation.
    - `data`: A list containing the newly created record's ID.

    **Example Request:**
    ```json
    {
      "name": "Gnana",
      "role": 1
    }
    ```

    **Example Response:**
    ```json
    {
      "status": "success",
      "message": "user record created successfully",
      "data": [
        {
          "id": 12345
        }
      ]
    }
    ```

    **Notes:**
    - The item data should match the collection's schema.
    - Ensure that the `Authorization` header is included with a valid JWT token for authentication.
    """
    new_record = db.create_record(collection, item, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}], message=f"{collection} record create successfully "
    )


@router.patch("/api/items/{collection}/{record_id}", tags=["Collection"])
def update_item(
    collection: str, record_id: int, item: dict, request: CustomRequest = None
):
    """
    Update an existing item in the specified collection.

    This endpoint allows you to update a specific record in the given collection. The `collection` parameter
    specifies the collection, and the `record_id` is the unique identifier of the record to be updated.
    The request body should contain the fields to be updated.

    **Path Parameters:**
    - `collection` (str): The name of the collection where the item will be updated.
    - `record_id` (int): The unique identifier of the record to be updated.

    **Request Body:**
    - `item` (dict): A dictionary containing the fields to be updated in the record.
      If the collection is `"users"` and the `plain_password` field is provided, it will be hashed
      and saved as `user_password`.

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success of the operation (e.g., `"success"`).
    - `message`: A message providing information about the operation result, such as the update confirmation.
    - `data`: An empty list (no data returned).
    - `metadata`: An empty list (no metadata returned).

    **Example Request:**
    ```json
    {
      "name": "Updated Item Name",
      "role": 4
    }
    ```

    **Example Response:**
    ```json
    {
      "status": "success",
      "message": "User record updated successfully",
      "data": [],
      "metadata": []
    }
    ```

    **Notes:**
    - If the collection is `"users"`, the `plain_password` field should be sent in the request body.
    - The password will be automatically hashed and stored as `user_password`.
    """
    if collection == "users" and item.get("plain_password"):
        item.update({"user_password": get_password_hash(item.get("plain_password"))})
    db.update_record(collection, record_id, item, request.logged_in_user_id)
    return make_success_response(
        data=[], message=f"{collection} record updated successfully", metadata=[]
    )


@router.delete("/api/items/{collection}/{record_id}", tags=["Collection"])
def delete_item(collection: str, record_id: int, request: CustomRequest = None):
    """
    Delete an item from the specified collection.

    This endpoint allows you to delete a specific record from a collection. The `collection` parameter
    specifies the collection, and the `record_id` is the unique identifier of the record to be deleted.

    **Path Parameters:**
    - `collection` (str): The name of the collection where the item will be deleted.
    - `record_id` (int): The unique identifier of the record to be deleted.

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success of the operation (e.g., `"success"`).
    - `message`: A message providing information about the operation result, such as the delete confirmation.
    - `data`: An empty list (no data returned).
    - `metadata`: An empty list (no metadata returned).

    **Example Response:**
    ```json
    {
      "status": "success",
      "message": "User record deleted successfully",
      "data": [],
      "metadata": []
    }
    ```

    **Notes:**
    - Ensure that the correct `record_id` is provided for deletion.
    """
    db.delete_record(collection, record_id, request.logged_in_user_id)
    return make_success_response(
        data=[], message=f"{collection} record deleted successfully", metadata=[]
    )


@router.get("/api/fields/{collection}", tags=["Forms"])
def get_field_by_field_name(collection: str):
    """
    Retrieve the fields for a specific collection.

    This endpoint returns the list of fields for a given collection. The collection parameter
    is used to fetch the corresponding fields from the `collection_fields` table in the database.

    **Path Parameters:**
    - `collection` (str): The name of the collection whose fields need to be retrieved.

    **Response:**
    - `status`: Indicates the success of the operation (e.g., `"success"`).
    - `message`: A message providing information about the operation result.
    - `data`: The list of fields associated with the collection.
    - `metadata`: Additional metadata related to the response (empty list in this case).

    **Example Response:**
    ```json
    {
      "status": "success",
      "message": "Users fields retrieved successfully",
      "data": [
        {"field_name": "user_id", "field_type": "integer"},
        {"field_name": "name", "field_type": "string"}
      ],
      "metadata": []
    }
    ```
    """
    data, metadata = db.get_data_from_table(
        "collection_fields",
        ["*"],
        {"collection_eq": collection},
        sort_by=["sort"],
        page=-1,
    )
    return make_success_response(
        data=data,
        message=f"{collection} fields retrieved successfully",
        metadata=metadata,
    )


@router.get("/api/template/{collection}", tags=["Files"])
def get_template_by_collection_name(collection: str, file_type: str = "csv"):
    """
    Retrieve a template for the specified collection.

    This endpoint returns a template file (either CSV or Excel format) based on the collection name.
    The file type can be specified as either `xlsx` or `csv`. If no file type is provided,
    `xlsx` is the default.

    **Path Parameters:**
    - `collection` (str): The name of the collection for which to fetch the template.
    - `file_type` (str): The desired file format for the template (`xlsx` or `csv`). Default is `xlsx`.

    **Response:**
    - A file in the specified format containing the template data for the collection.

    **Example Request:**
    ```json
    {
      "collection": "users",
      "file_type": "csv"
    }
    ```

    **Example Response:**
    - Returns a file in the requested format (`xlsx` or `csv`).
    """
    return db.get_template_as_file(collection, file_type)


@router.post("/api/upload/{collection}", tags=["Files"])
async def upload_file_and_import(
    collection: str,
    file: UploadFile = File(...),
    request: CustomRequest = None,
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a file and import data into the specified collection.

    This endpoint allows the user to upload a file (`csv` or `xlsx`) and import the data into a
    specified collection. The file content is read, processed, and validated. If there are any issues
    with the file (e.g., incorrect format, size, or records), an error message is returned.

    **Path Parameters:**
    - `collection` (str): The name of the collection to import the data into.

    **Request Body:**
    - `file` (UploadFile): The file to be uploaded (supports `.csv` and `.xlsx` formats).

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success or failure of the operation.
    - `message`: A message providing information about the operation result.
    - `data`: Contains the URL for downloading the validation file if there are errors.
    - `metadata`: Additional metadata related to the response (empty list if no extra data is provided).

    **Example Request:**
    ```json
    {
      "collection": "users",
      "file": "<CSV or XLSX file>"
    }
    ```

    **Example Response:**
    ```json
    {
      "status": "success",
      "message": "Data imported successfully",
      "data": [{"validation_file_url": "http://example.com/validation-file"}],
      "metadata": []
    }
    ```

    **Notes:**
    - The file is validated based on format and size (must be under `MAX_FILE_SIZE_MB` and not exceed `MAX_RECORDS`).
    - For the `users` collection, the password is hashed during the import process.
    - The response includes a URL to download a validation file if any issues are found in the uploaded file.
    """
    print("Inside function")
    if not db.is_allowed_file(file.filename):
        return make_failure_response(message="We can accept .csv and .xlsx format only")

    if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        return make_failure_response(
            message="File size exceeds the maximum allowed limit."
        )

    if file.filename.endswith(".csv"):
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
    elif file.filename.endswith(".xlsx"):
        print("Reading Excel files data")
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))

    df = df.replace({np.nan: None})
    if df.shape[0] > MAX_RECORDS:
        return make_failure_response(
            message=f"Number of records exceeds the maximum allowed limit of {MAX_RECORDS}."
        )
    if not df.shape[0]:
        return make_failure_response(message="No records to import.")
    print(" df.to_dict()", df.to_dict(orient="records"))

    # Handle users' password encryption here
    if collection == "users":
        df["user_password"] = None
        df["plain_password"] = None
        for index, row in df.iterrows():
            if row.get("Employee Code"):
                df.at[index, "Employee Code"] = str(row["Employee Code"]).upper()
            generated_password = "".join(
                random.choice(string.ascii_letters.lower()) for i in range(8)
            )
            df.at[index, "user_password"] = get_password_hash(generated_password)
            df.at[index, "plain_password"] = generated_password

    df["created_by"] = request.logged_in_user_id
    df["updated_by"] = request.logged_in_user_id
    uploaded_url, unuploaded_records = db.file_upload_validation(
        collection, df.to_dict(orient="records"), request.logged_in_user_id
    )

    if unuploaded_records:
        return make_failure_response(
            message="There are some errors in the uploaded file. Please refer to the file",
            data=[{"validation_file_url": uploaded_url}],
        )

    return make_success_response(
        message="Data imported successfully",
        data=[{"validation_file_url": uploaded_url}],
    )


@router.post("/api/hierarchical-insert", tags=["Dynamic Inserts"])
def hierarchical_insert(item: dict, request: CustomRequest = None):
    """
    Perform hierarchical dynamic inserts for complex data structures.

    This endpoint allows for dynamic hierarchical data insertion into the database.
    It processes a complex dictionary structure and inserts the data into multiple
    related tables while maintaining relationships.

    **Request Body:**
    - `item` (dict): The hierarchical data structure to be inserted. The dictionary
      contains nested key-value pairs representing parent-child relationships in the database.

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success or failure of the operation.
    - `message`: Provides information about the operation's result. Includes success or failure message.
    - `data`: Empty in this response since the focus is on the success message.
    - `metadata`: Empty list for this response.

    **Example Request:**
    ```json
    {
      "parent_table": {
        "field1": "value1",
        "child_table": {
          "field2": "value2",
          "field3": "value3"
        }
      }
    }
    ```

    **Example Response (Success):**
    ```json
    {
      "status": "success",
      "message": "parent_table created successfully",
      "data": [],
      "metadata": []
    }
    ```

    **Example Response (Failure):**
    ```json
    {
      "status": "failure",
      "message": "Error inserting data into child_table due to constraint violation",
      "data": [],
      "metadata": []
    }
    ```

    **Notes:**
    - The method leverages the `dynamic_inserts` function to handle the logic of inserting the hierarchical data.
    - If an error occurs during the insertion, the response includes a failure message with details about the error.
    """
    failure_message = db.dynamic_inserts(item, request.logged_in_user_id)
    if failure_message:
        return make_failure_response(failure_message)
    return make_success_response(message=f"{next(iter(item))} created successfully")


@router.post("/api/bulk-upsert", tags=["Bulk Upserts"])
def bulk_upserts(item: dict, request: CustomRequest = None):
    """
    Perform bulk upsert operations for multiple records in a single request.

    This endpoint allows for updating or inserting multiple records efficiently
    into the database. If a record exists based on unique identifiers, it will be
    updated. Otherwise, it will be inserted as a new record.

    **Request Body:**
    - `item` (dict): A dictionary containing the data to be upserted. Each key
      represents a table, and the value is a list of records to be processed.

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success or failure of the operation.
    - `message`: Provides information about the operation's result. Includes success or failure message.
    - `data`: Empty in this response since the focus is on the success message.
    - `metadata`: Empty list for this response.

    **Example Request:**
    ```json
    {
      "users": [
        {"id": 1, "name": "John Doe", "email": "john.doe@example.com"},
        {"id": 2, "name": "Jane Smith", "email": "jane.smith@example.com"}
      ],
      "orders": [
        {"order_id": 101, "amount": 250.5},
        {"order_id": 102, "amount": 300.0}
      ]
    }
    ```

    **Example Response (Success):**
    ```json
    {
      "status": "success",
      "message": "Bulk upsert successful",
      "data": [],
      "metadata": []
    }
    ```

    **Example Response (Failure):**
    ```json
    {
      "status": "failure",
      "message": "Error processing bulk upserts for users table due to constraint violation",
      "data": [],
      "metadata": []
    }
    ```

    **Notes:**
    - The method uses the `bulk_upserts` function to process the provided data.
    - Handles records for multiple tables simultaneously, ensuring efficient database operations.
    - Any errors during the process will return a failure message with details about the issue.
    - Supports upsert logic based on unique constraints or primary keys.
    """
    failure_message = db.bulk_upserts(item, request.logged_in_user_id)
    if failure_message:
        return make_failure_response(failure_message)
    return make_success_response(message="Bulk upsert successful")


@router.post("/api/document-upload/{s3_folder_name}", tags=["Files"])
def upload_document(
    s3_folder_name: str, file: UploadFile = File(...), request: CustomRequest = None
):
    """
    Upload a document to an S3 bucket and log the upload details.

    This endpoint facilitates the uploading of documents to a specified folder in an S3 bucket.
    It also logs the details of the uploaded document in the `document_upload_log` table for audit purposes.

    **Path Parameters:**
    - `s3_folder_name` (str): The name of the folder in the S3 bucket where the file will be uploaded.
      Defaults to "others" if not provided.

    **Request Body:**
    - `file` (UploadFile): The file to be uploaded. Accepted file formats and size limits should
      be handled by the client.

    **Request Headers:**
    - `Authorization`: Bearer token for authenticating the user (JWT).

    **Response:**
    - `status`: Indicates the success or failure of the operation.
    - `message`: Provides information about the operation's result. Includes success or failure message.
    - `data`: Contains the URL of the uploaded file.
    - `metadata`: Empty list for this response.

    **Example Request:**
    ```bash
    curl --request POST \
         --url http://127.0.0.1:8000/api/document-upload/my-folder \
         --header 'Authorization: Bearer <JWT_TOKEN>' \
         --header 'Content-Type: multipart/form-data' \
         --form 'file=@example.pdf'
    ```

    **Example Response (Success):**
    ```json
    {
      "status": "success",
      "message": "file upload successful",
      "data": [
        {
          "uploaded_url": "https://s3.amazonaws.com/my-bucket/my-folder/example.pdf"
        }
      ],
      "metadata": []
    }
    ```

    **Example Response (Failure):**
    ```json
    {
      "status": "failure",
      "message": "The file upload failed",
      "data": [],
      "metadata": []
    }
    ```

    **Audit Log:**
    - After a successful upload, the following details are logged:
      - `file_name`: The name of the uploaded file.
      - `entity`: The folder name where the file was uploaded.
      - `doc_url`: The S3 URL of the uploaded document.

    **Notes:**
    - The file is uploaded to the specified S3 folder using the `s3_file_upload` utility.
    - If the upload fails, a failure response is returned with an appropriate message.
    - Details of the uploaded document are logged in the `document_upload_log` table for tracking.
    """
    s3_folder_name = s3_folder_name if s3_folder_name else "others"
    uploaded_url = s3_file_upload(file.filename, file, folder_name=s3_folder_name)
    if not uploaded_url:
        return make_failure_response("The file upload failed")
    audit_data = {
        "file_name": file.filename,
        "entity": s3_folder_name,
        "doc_url": uploaded_url,
    }
    db.create_record("document_upload_log", audit_data, request.logged_in_user_id)
    return make_success_response(
        data=[{"uploaded_url": uploaded_url}],
        message="file upload successful",
        metadata=[],
    )


@router.get("/api/query/{collection_name}", tags=["Using SQL"])
def query_collections(
    collection_name: str,
    page: int = 1,
    per_page: int = Query(10, ge=1),
    filters: str = None,
    search: str = None,
    sort_by: str = None,
    summary: str = None,
    export_as_file: bool = False,
    request: CustomRequest = None,
):
    """
    Query a collection with advanced filtering, sorting, and pagination options.

    This endpoint retrieves data from a specified collection based on various
    query parameters, allowing for flexible filtering, sorting, searching, and exporting.

    **Path Parameters:**
    - `collection_name` (str): The name of the collection to query.

    **Query Parameters:**
    - `page` (int, default=1): The page number for paginated results. Must be greater than or equal to 1.
    - `per_page` (int, default=10): The number of records per page. Must be greater than or equal to 1.
    - `filters` (str, optional): A JSON string specifying the filter conditions for the query.
    - `search` (str, optional): A search term to filter results based on matching fields.
    - `sort_by` (str, optional): A comma-separated string specifying sorting fields (e.g., `-id,name`).
      Use `-` for descending order and omit it for ascending.
    - `summary` (str, optional): A field or group of fields to summarize data.
    - `export_as_file` (bool, default=False): If `True`, exports the results as a file.

    """

    base_query = ""
    where_clause = []
    if filters:
        where_clause.append(f"({filters})")
    if search:
        flat_search = []
        searchable_columns = [
            col["name"] for col in db.get_columns_by_table(collection_name)
        ]
        for column in searchable_columns:
            flat_search.append(f"""(CAST("{column}" AS TEXT) LIKE '%{search}%')""")
        flat_search_phrase = " OR ".join(flat_search)
        where_clause.append(flat_search_phrase)
    if where_clause:
        base_query = base_query + " where " + " and ".join(where_clause)
    """summary comes as csv and I am making it as sum, in case no summary I am taking count(1)
    alone in the select clause for getting total"""
    if summary:
        summary = "count(1) as total_rows," + ",".join(
            [f"sum({field}) as {field}" for field in summary.split(",")]
        )
    else:
        summary = "count(1) as total_rows"
    query = text(f"""select {summary}  from {collection_name} {base_query}""")

    """Count total records before pagination"""
    query_result = db.execute_query(query)
    total_records = query_result[0]._asdict()["total_rows"]
    report_summary = {
        key: value
        for key, value in query_result[0]._asdict().items()
        if key != "total_rows"
    }
    """sort by has to happen after getting the total since it will result in error when you use
    order by in a grouping or aggregating i.e, count(1)"""
    if sort_by:
        base_query = base_query + " order by " + sort_by

    """Calculate pagination"""
    if export_as_file:
        """exporting should get all the data into the file so keeping it to -1
        which will not enable the pagination"""
        page = -1
    total_pages = ceil(total_records / per_page)
    offset = (page - 1) * per_page
    result = (
        db.execute_query(
            text(
                f"select * from {collection_name} {base_query} LIMIT {per_page} OFFSET {offset}"
            )
        )
        if page > 0
        else db.execute_query(text(f"select * from {collection_name} {base_query}"))
    )
    result_as_json = [row._asdict() for row in result] if result else []
    if export_as_file:
        return db.export_as_file(
            data=result_as_json,
            file_type="xlsx",
            file_name=collection_name,
            summary=report_summary,
        )
    metadata = {
        "page": page,
        "per_page": per_page,
        "total_number_of_page": total_pages,
        "records": total_records,
        "summary": jsonable_encoder(report_summary),
    }
    return make_success_response(
        data=result_as_json,
        message=f"{collection_name} retrived successful",
        metadata=metadata,
    )


@router.get("/api/collection/tables/{table_name}", tags=["Collection"])
def generate_tbale_collection_filed(table_name: str, request: CustomRequest):
    """
    Retrieve details about a specific database table and construct a JSON response
    with additional metadata and display properties.
    """
    # Retrieve the table model
    data = db.get_model(tbl_name=table_name)

    if not data:
        return make_success_response(message="Table not found", data=[])
    # Mapping for type -> interface -> data_type
    type_mapping = {
        "enum": {"interface": "DROPDOWN", "data_type": "STRING"},
        "boolean": {"interface": "CHECKBOX", "data_type": "BOOLEAN"},
        "date": {"interface": "DATE", "data_type": "DATE"},
        "float": {"interface": "NUMERIC", "data_type": "FLOAT"},
        "integer": {"interface": "NUMERIC", "data_type": "INT"},
        "bigint": {"interface": "NUMERIC", "data_type": "INT"},
        "varchar": {"interface": "STRING", "data_type": "STRING"},
        "datetime": {"interface": "DATETIME", "data_type": "DATETIME"},
        "timestamp": {"interface": "TIMESTAMP", "data_type": "TIMESTAMP"},
        "text": {"interface": "TEXT", "data_type": "TEXT"},
        "json": {"interface": "TEXT", "data_type": "JSON"},
    }

    # Constructing the JSON structure
    columns = []
    for column in data.__table__.columns:
        col_type = str(column.type).lower().split("(")[0]

        type_info = type_mapping.get(
            col_type, {"interface": "TEXT", "data_type": "TEXT"}
        )

        # Construct label by removing underscores and formatting in sentence case
        label = " ".join(word.capitalize() for word in column.name.split("_"))

        # Handle foreign key relationships
        foreign_key_column = None
        foreign_key_table = None
        return_value = None
        display_options = None

        template_eligible = True
        export_eligible = True

        if str(column.name).lower() in [
            "id",
            "created_date",
            "modified_date",
            "created_by",
            "modified_by",
        ]:
            template_eligible = False
            export_eligible = False

        if column.foreign_keys and len(column.foreign_keys):
            print("column.name", column.name)
            print("inside foreign key")
            foreign_key = next(
                iter(column.foreign_keys)
            )  # Get the first foreign key relationship
            foreign_key_column = foreign_key.column.name
            foreign_key_table = foreign_key.column.table.name
            return_value = foreign_key_column
            display_options = [foreign_key_column]

            data_type = type_mapping.get(
                col_type, {"interface": "TEXT", "data_type": "TEXT"}
            )["data_type"]
            # Update interface and data_type based on foreign key child field
            type_info = {"interface": "FORM_SEARCH", "data_type": data_type}

        column_data = {
            "collection": table_name,
            "field": column.name,
            "label": label,
            "special": None,
            "is_required": not column.nullable,
            "options": None,
            "display": None,
            "readonly": column.primary_key or column.default is not None,
            "hidden": True
            if column.name
            in ["id", "created_date", "modified_date", "created_by", "modified_by"]
            else False,
            "sort": None,
            "width": None,
            "default_value": column.default.arg if column.default else None,
            "max_length": getattr(column.type, "length", None),
            "numeric_precision": getattr(column.type, "precision", None),
            "numeric_scale": getattr(column.type, "scale", None),
            "is_nullable": column.nullable,
            "is_primary_key": column.primary_key,
            "has_auto_increment": getattr(column, "autoincrement", False),
            "filters": None,
            "comment": column.comment if hasattr(column, "comment") else None,
            "api": None,
            "regex": None,
            "type": col_type,
            "interface": type_info["interface"],
            "display_options": json.dumps(display_options) if display_options else None,
            "data_type": type_info["data_type"],
            "foreign_key_column": foreign_key_column,
            "foreign_key_table": foreign_key_table,
            "return_value": return_value,
            "template_eligible": template_eligible,
            "export_eligible": export_eligible,
        }

        columns.append(column_data)
        db.upsert_record(
            "collection_fields",
            column_data,
            ["field", "collection"],
            # user_id=request.logged_in_user_id,
        )

    return make_success_response(data=columns)
