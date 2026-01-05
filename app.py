import os
from fastapi import FastAPI
import uvicorn
from routers import (
    # auth,
    # dashboard,
    main,
    masters,
    login,
    rbac,
    reports,
    # i4c_request
)
from fastapi.middleware.cors import CORSMiddleware
from brotli_asgi import BrotliMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from utils.custom_class import models

from fastapi.openapi.utils import get_openapi
from copy import deepcopy
from dotenv import load_dotenv
from utils.db_connection import db
from orm_model.core_models import Base, engine, AbstractBase, bulk_insert_from_json_file
import requests
import time
# from fastapi_utils.tasks import repeat_every
load_dotenv()

app = FastAPI()

# scheduler = AsyncIOScheduler()

"""CORS policies reject the api requests from unknown origin(the place where the api call is originated).
In our architecture, the front-end server and this back-end server resides in same domain or sub-domain.
For architecture like this, the CORS policy will accept the origin. However, when you run this in LOCAL
environment, such CORS policy violations happen. To make it work only in local, the CORS policy should
allow any origin and the below code facilitates that."""
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
"""
BrotliMiddleware - compresses the response payload if the size is more than the configured (minimum_size) value.
For this to work, the client that calls the apis must send (Accept-Encoding : br) as the header
"""
app.add_middleware(
    BrotliMiddleware,
    quality=4,
    mode="text",
    lgwin=22,
    lgblock=0,
    minimum_size=1000,
    gzip_fallback=False,
)

"""adding routers to the app"""
# app.include_router(auth.router)
# app.include_router(main.router)
# app.include_router(main.router)
# app.include_router(masters.router)
# app.include_router(login.router)
# app.include_router(rbac.router)
# app.include_router(reports.router)
# app.include_router(i4c_request.router)
# app.include_router(dashboard.router)


@app.on_event("startup")
async def start_scheduling():
    """This creates all tables stored in the Base.metadata(example:models_user,models_product).
    Conditional by default, will not attempt to recreate tables already present in the target database.
    """
    # COMMENTED OUT: Template table creation (not needed for existing database)
    Base.metadata.create_all(bind=engine)
    AbstractBase.metadata.create_all(bind=engine)
    bulk_insert_from_json_file()

    # Refresh metadata to load existing tables from your database
    db.refresh_metadata()


def resolve_reference(ref, definitions):
    ref_parts = ref.split("/")
    enum_name = ref_parts[-1]
    return definitions.get(enum_name, {})

def call_fastapi_endpoint():
    try:
        response = requests.get("http://127.0.0.1:8000/api/i4c-request")
        print(f"API call successful: {response.status_code}")
        print(response.json())
    except requests.exceptions.RequestException as e:
        print(f"Error calling API: {e}")

# scheduler = BackgroundScheduler()

@app.on_event("startup")
# def start_scheduler():
#     scheduler.add_job(call_fastapi_endpoint, "interval", minutes=1)
#     scheduler.start()
#     print("Scheduler started")

@app.on_event("shutdown")
# def shutdown_scheduler():
#     scheduler.shutdown()
#     print("Scheduler stopped")

@app.get("/")
def home():
    return {"msg": "FastAPI running with APScheduler"}

def flatten_schema(schema):
    flat_schema = deepcopy(schema)
    flat_schema["properties"] = {}

    properties = schema.get("properties", {})
    definitions = schema.get("$defs") or schema.get("definitions", {})

    for key, value in properties.items():
        if "$ref" in value:
            resolved = resolve_reference(value["$ref"], definitions)
            if "enum" in resolved:
                flat_schema["properties"][key] = {
                    "type": "string",
                    "enum": resolved["enum"],
                }
            else:
                flat_schema["properties"][key] = resolved
        else:
            flat_schema["properties"][key] = value

    flat_schema.pop("$defs", None)
    flat_schema.pop("definitions", None)

    return flat_schema


def custom_openapi():
    tags_metadata = [
        {
            "name": "Admin",
            "description": """This module provides administrative functions, including user and system management,
            configuration settings, and access controls for system administrators.""",
        },
        {
            "name": "Collection",
            "description": """This module handles the creation, updating, deletion, and retrieval of collection details.
            It allows managing collections of data and items effectively.""",
        },
        {
            "name": "Forms",
            "description": """This module handles form-related operations, including the creation and management of
            dynamic forms for data input and user interaction.""",
        },
        {
            "name": "User Management",
            "description": """This module deals with the management of user accounts, roles, permissions, and profiles,
            including registration, login, and user-specific settings.""",
        },
        {
            "name": "Dynamic Inserts",
            "description": """This module allows the dynamic insertion of records into various collections or
            databases, supporting flexible data entry through API endpoints.""",
        },
        {
            "name": "Bulk Upserts",
            "description": """This module provides functionality for bulk insert or update operations, allowing
            multiple records to be added or updated in a single request.""",
        },
        {
            "name": "Using SQL",
            "description": """This module facilitates the usage of SQL queries for advanced data manipulation,
            including filtering, sorting, and aggregating records in the database.""",
        },
        {
            "name": "Files",
            "description": """This module manages file uploads, downloads, and storage, allowing users to interact with
            files (e.g., images, documents) through the API.""",
        },
        {
            "name": "Reports",
            "description": """This module generates reports based on various data sources, enabling users to obtain
            insights and data visualizations from the system.""",
        },
        {
            "name": "Notifications",
            "description": """This module handles the delivery of notifications (e.g., email, SMS) to users about
            system events or updates.""",
        },
        {
            "name": "Auditor",
            "description": """This module is responsible for managing and tracking system audits, including user
            actions and system events.""",
        },
        # {"name": "RBAC", "description": """This module implements Role-Based Access Control (RBAC), managing user
        # permissions and roles to restrict access to specific resources based on user roles."""},
    ]

    openapi_schema = get_openapi(
        title="PNC",
        description="Pentafox No Code",
        version="0.0.1",
        terms_of_service="https://pentafox.in/",
        contact={
            "name": "Gnanaprakasam Duraipandiyan",
            "email": "gnanaprakasam@pentafox.in",
        },
        routes=app.routes,
        tags=tags_metadata,
    )
    api_path = []
    for key, model in models.items():
        _, method, path = key.split("#")
        model_schema = model.schema()
        flat_model_schema = flatten_schema(model_schema)
        print("flat_model_schema", flat_model_schema)

        if f"{method}_{path}" not in api_path and path in openapi_schema["paths"]:
            if method.lower() == "post":
                openapi_schema["paths"][path][method.lower()]["requestBody"] = {
                    "content": {"application/json": {"schema": flat_model_schema}},
                    "required": True,
                }
            elif method.lower() == "get":
                openapi_schema["paths"][path][method.lower()]["responses"]["200"][
                    "content"
                ] = {"application/json": {"schema": flat_model_schema}}
            api_path.append(f"{method}_{path}")

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/api/health-check")
def health_check():
    return {"message": "Application running sucessfully"}


# app.include_router(auth.router)
# app.include_router(main.router)
# app.include_router(main.router)
# app.include_router(masters.router)
# app.include_router(login.router)
# app.include_router(rbac.router)
# app.include_router(reports.router)
# app.include_router(i4c_request.router)
# app.include_router(dashboard.router)

# Start the FastAPI application
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)
    # uvicorn app:app --reload --host 127.0.0.1 --port 5000
