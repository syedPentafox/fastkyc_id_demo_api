import os
from dotenv import load_dotenv
from fastapi import HTTPException, Response
from sqlalchemy import (
    create_engine,
    inspect,
    or_,
    and_,
    func,
    String,
    text,
    desc,
    asc,
    Date,
    cast,
    distinct,
)
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import sessionmaker, aliased
from math import ceil
import logging

import json
import io
import csv
from openpyxl import Workbook
import base64
import pandas as pd

from sqlalchemy import event, update
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from utils.query_profiler import SqlProfiler
import boto3
from datetime import datetime, timedelta
from sqlalchemy.exc import DBAPIError
import traceback
from sqlalchemy.orm import Session as orm_session
import uuid

from validation_models.models import (
    StringValidator,
    IntValidator,
    FloatValidator,
)

from io import StringIO
from typing import Any
import re
from response_models.response_models import make_success_response, make_failure_response
from utils.metrics import lead_location_mismatch
import numpy as np
import ast
from dateutil import parser

from utils.new_tables import import_table_metadata

logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

load_dotenv()

ALLOWED_EXTENSIONS = {"csv", "xlsx"}
MAX_FILE_SIZE_MB = 10
MAX_RECORDS = 5000

docs_url = os.getenv("AMAZON_S3_BASE_URL")
locally_save_file = False
if os.getenv("LOCALLY_SAVE_FILE", "NO").upper() == "YES":
    locally_save_file = True


SqlProfiler()


class DatabaseHandler:
    def __init__(self):
        print(">>>>>Connecting to the database")
        DB_URL = os.getenv("DATABASE_URL")
        self.engine = create_engine(DB_URL, pool_size=20, max_overflow=40)
        self.Base = automap_base()
        self.Base.prepare(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.inspector = inspect(self.engine)
        table_metadata = {}
        tables = self.inspector.get_table_names()
        for table in tables:
            columns = [col["name"] for col in self.inspector.get_columns(table)]
            table_metadata[table] = columns
        
        self.tables = tables
        self.session = self.Session()
        self.table_metadata = table_metadata
        # # Manually add i4c_request table metadata (Oracle filters out SYSTEM tablespace tables)
        # import_table_metadata(self.table_metadata, self.tables)
        self.FILTER_OPERATORS = {
            "eq": lambda column, value: column == value,
            "neq": lambda column, value: column != value,
            "lt": lambda column, value: column < value,
            "lte": lambda column, value: column <= value,
            "gt": lambda column, value: column > value,
            "gte": lambda column, value: column >= value,
            "in": lambda column, value: column.in_(value),
            "nin": lambda column, value: ~column.in_(value),
            "null": lambda column, _: column.is_(None),
            "nnull": lambda column, _: column.isnot(None),
            "contains": lambda column, value: column.contains(value),
            "icontains": lambda column, value: column.ilike(f"%{value}%"),
            "ncontains": lambda column, value: ~column.contains(value),
            "starts_with": lambda column, value: column.startswith(value),
            "istarts_with": lambda column, value: column.ilike(f"{value}%"),
            "nstarts_with": lambda column, value: ~column.startswith(value),
            "nistarts_with": lambda column, value: ~column.ilike(f"{value}%"),
            "ends_with": lambda column, value: column.endswith(value),
            "iends_with": lambda column, value: column.ilike(f"%{value}"),
            "nends_with": lambda column, value: ~column.endswith(value),
            "niends_with": lambda column, value: ~column.ilike(f"%{value}%"),
            "between": lambda column, value: column.between(value[0], value[1]),
            "nbetween": lambda column, value: ~column.between(value[0], value[1]),

        }
        self.FUNCTIONS = {
            "NOW": lambda column, value: datetime.now(),
            "YEAR": lambda column, value: column.year,
            "DATE": lambda column, value: cast(column, Date),
            "MONTH": lambda column, value: column.month,
            "WEEK": lambda column, value: column.isocalendar()[1],
            "DAY": lambda column, value: column.day,
            "WEEKDAY": lambda column, value: column.weekday(),
            "HOUR": lambda column, value: column.hour,
            "MINUTE": lambda column, value: column.minute,
            "SECOND": lambda column, value: column.second,
        }
        self.datetime_patterns = [
            r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",  # yyyy-mm-dd hh:mm:ss
            r"\d{4}-\d{2}-\d{2}",  # yyyy-mm-dd
            r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",  # dd/mm/yyyy hh:mm:ss
            r"\d{2}/\d{2}/\d{4}",  # dd/mm/yyyy
            r"\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}",  # dd-mm-yyyy hh:mm:ss
            r"\d{2}-\d{2}-\d{4}",  # dd-mm-yyyy
        ]
        self.delete_columns = [
            "id",
            "created_by",
            "modified_by",
            "created_date",
            "modified_date",
        ]
        self.users_model = self.get_model("users")
        self.roles_model = self.get_model("roles")
        self.collection_fields_model = self.get_model("collection_fields")
        self.s3_client = boto3.client("s3")
        self.s3_bucket = os.getenv("S3_BUCKET_NAME")

    def refresh_metadata(self):
        """Refresh metadata after schema changes."""
        self.inspector = inspect(self.engine)
        self.table_metadata = {
            table: [col["name"] for col in self.inspector.get_columns(table)]
            for table in self.inspector.get_table_names()
        }
        
        # # Manually add i4c_request table metadata (Oracle filters out SYSTEM tablespace tables)
        # import_table_metadata(self.table_metadata, self.tables)

        self.tables = list(self.table_metadata.keys())

        # Dispose the engine to clear cached metadata
        self.engine.dispose()
        # Reinitialize Base and prepare mappings again
        self.Base = automap_base()  # Reinitialize globally
        self.Base.prepare(self.engine, reflect=True)

    def get_db_session(self):
        return self.session

    def get_table_metadata(self):
        return self.table_metadata

    def setup_event_listeners(self):
        processed_classes = set()

        for mapper_class in self.Base.classes.values():
            if mapper_class in processed_classes:
                continue

            @event.listens_for(mapper_class, "before_insert")
            def my_before_insert_listener(mapper, connection, target):
                orm_ses = orm_session.object_session(target)
                user_id = orm_ses.info.get("user_id", None)
                # Check if the target has a `created_by` attribute
                # Set created_by and created_date
                if hasattr(target, "created_by") and user_id is not None:
                    setattr(target, "created_by", user_id)
                if hasattr(target, "created_date"):
                    setattr(target, "created_date", datetime.utcnow())
                self.handle_event(mapper, target, "before_insert", user_id)

            @event.listens_for(mapper_class, "after_insert")
            def my_after_insert_listener(mapper, connection, target):
                orm_ses = orm_session.object_session(target)
                user_id = orm_ses.info.get("user_id", None)
                self.handle_event(mapper, target, "after_insert", user_id)

            @event.listens_for(mapper_class, "before_update")
            def my_before_update_listener(mapper, connection, target):
                orm_ses = orm_session.object_session(target)
                user_id = orm_ses.info.get("user_id", None)

                # Update modified_by and modified_date
                if hasattr(target, "modified_by") and user_id is not None:
                    setattr(target, "modified_by", user_id)
                if hasattr(target, "modified_date"):
                    setattr(target, "modified_date", datetime.utcnow())

                self.handle_event(mapper, target, "before_update", user_id)

            @event.listens_for(mapper_class, "after_update")
            def my_after_update_listener(mapper, connection, target):
                orm_ses = orm_session.object_session(target)
                user_id = orm_ses.info.get("user_id", None)
                self.handle_event(mapper, target, "after_update", user_id)

            @event.listens_for(mapper_class, "after_delete")
            def my_after_delete_listener(mapper, connection, target):
                orm_ses = orm_session.object_session(target)
                user_id = orm_ses.info.get("user_id", None)
                self.handle_event(mapper, target, "after_delete", user_id)

            # Mark this mapper class as processed
            processed_classes.add(mapper_class)

    def handle_event(self, mapper, target, event_type, user_id):
        table_name = mapper.mapped_table.name
        self.call_workflow(table_name, target, event_type, user_id)

    def workflow_execute_query(self, query):
        with self.workflow_session as s:
            try:
                result = s.execute(query)
                return result.fetchall()
            except Exception as e:
                logging.error("Error executing query: %s", e)
                return None

    def call_workflow(
        self, table_name: str, record: Any, event_type: str, user_id: str
    ):
        model = self.get_model("workflows")
        if not model:
            return

        try:
            results = self._get_workflow_results(model, table_name, event_type)
            if results:
                for row in results:
                    self._validate_mandatory_fields(row, record)
                    self._execute_script(row, record, user_id)
                    self._execute_queries(row, record)
        except HTTPException as e:
            raise HTTPException(status_code=200, detail=e.detail)
        except Exception as e:
            traceback_message = "".join(
                traceback.format_exception(None, e, e.__traceback__)
            )
            print("traceback_message>>>>>>", traceback_message)
            raise HTTPException(status_code=500, detail="Internal server error")

    def _get_workflow_results(self, model, table_name: str, event_type: str):
        with self.workflow_session as s:
            results = (
                s.query(model)
                .filter_by(collection_name=table_name, events=event_type)
                .all()
            )
            print("Workflow results", results)
            return results

    def _validate_mandatory_fields(self, row, record):
        if row.mandatory_fields:
            mandatory_fields = json.loads(row.mandatory_fields)
            for key in mandatory_fields:
                if key not in record.__dict__:
                    raise HTTPException(
                        status_code=400, detail="Record Deletion Failed"
                    )

    def _execute_script(self, row, record, user_id):
        if row.script:
            exec(row.script, globals())
            try:
                with self.workflow_session as s:
                    self.workflow_handler(self, record, s, int(user_id))
                    s.commit()
            except Exception as e:
                raise e

    def _execute_queries(self, row, record):
        if row.queries:
            queries = json.loads(row.queries)
            for query in queries:
                try:
                    formatted_query = query.format(**record.__dict__)
                    self.workflow_execute_query(formatted_query)
                except SQLAlchemyError as e:
                    print(f"Query execution error: {e}")
                    raise HTTPException(status_code=500, detail="Internal server error")

    def check_table_exists(self, tbl_name):
        if tbl_name in self.tables:
            return True
        return None

    def get_model(self, tbl_name):
        if self.check_table_exists(tbl_name):
            # # Special case for i4c_request table - use the manually defined model
            # if tbl_name == 'i4c_request':
            #     from orm_model.core_models import I4CRequest
            #     return I4CRequest
            # if tbl_name == 'upi_fraud_transactions':
            #     from orm_model.core_models import UpiFraudTransactions
            #     return UpiFraudTransactions
            # if tbl_name == 'upi_fraud_incidents':
            #     from orm_model.core_models import UpiFraudIncidents
            #     return UpiFraudIncidents
            # if tbl_name == 'roles':
            #     from orm_model.core_models import Role
            #     return Role
            return getattr(self.Base.classes, tbl_name)

    def get_columns_by_table(self, tbl_name):
        return self.inspector.get_columns(tbl_name)

    def get_foreign_keys_by_table(self, tbl_name):
        return self.inspector.get_foreign_keys(tbl_name)

    def relation_table_name_by_column(self, tbl_name, column):
        foreign_keys = self.inspector.get_foreign_keys(tbl_name)
        for fk in foreign_keys:
            primary_column_name = fk["constrained_columns"][0]
            related_table_name = fk["referred_table"]
            if primary_column_name == column:
                return related_table_name
        return None

    def send_notification_using_template(self, template_name, tokens, data):
        template_details, _ = self.get_data_from_table(
            "notification_templates",
            ["title", "message"],
            {"templates_name_eq": template_name},
        )
        if template_details:
            template_detail = template_details[0]
            for user_id, token in tokens.items():
                message_id = str(uuid.uuid4())
                data.update({"message_id": message_id})
                response = self.push_notification(
                    title=template_detail.get("title"),
                    msg=template_detail.get("message"),
                    registration_token=[token],
                    data=data,
                )
                message_details = {**template_detail, **data}
                print("Message Details", message_details)
                status = "SENT" if response else "FAILED"
                notification_details = {
                    "user_id": user_id,
                    "message_id": message_id,
                    "message_details": message_details,
                    "status": status,
                }
                self.create_record("user_notifications", notification_details, user_id)
        return False

    def send_notification_raw_message(self, tokens, title, message, data):
        for user_id, token in tokens.items():
            message_id = str(uuid.uuid4())
            data.update({"message_id": message_id})
            response = self.push_notification(
                title=title, msg=message, registration_token=[token], data=data
            )
            message_details = {**{"title": title, "message": message}, **data}
            print("Message Details", message_details)
            status = "SENT" if response else "FAILED"
            notification_details = {
                "user_id": user_id,
                "message_id": message_id,
                "message_details": message_details,
                "status": status,
            }
            self.create_record("user_notifications", notification_details, user_id)
        return False

    def get_filter_query(self, tbl_name, filters):
        ((filter_name, filter_value),) = filters.items()
        model = self.get_model(tbl_name)
        if "_" in filter_name:
            column_name, operator_name = filter_name.rsplit("_", 1)
            filter_operator = self.FILTER_OPERATORS.get(operator_name)
            if "." in column_name:
                primary, secondary = column_name.split(".")
                relation_table = self.relation_table_name_by_column(tbl_name, primary)
                relation_model = self.get_model(relation_table)
                column = getattr(relation_model, secondary)
            else:
                column = getattr(model, column_name)
            if filter_operator:
                result = filter_operator(column, filter_value)
                return result
            else:
                logging.warning("Invalid filter operator: %s", operator_name)
                return None  # Handle invalid operator gracefully
        else:
            logging.warning("Invalid filter name: %s", filter_name)
            return None  # Handle invalid filter name gracefully

    def apply_filters(
        self,
        query,
        tbl_name,
        filters,
        and_conditions=None,
        or_conditions=None,
        operator="and",
    ):
        if not isinstance(filters, dict):
            logging.warning("Invalid filter format: %s", filters)
            return query, and_conditions, or_conditions

        if and_conditions is None:
            and_conditions = []
        if or_conditions is None:
            or_conditions = []

        for key, value in filters.items():
            if key in ["and", "or"]:
                self._apply_logical_operator(
                    query, tbl_name, key, value, and_conditions, or_conditions
                )
            else:
                self._apply_filter(
                    tbl_name, key, value, and_conditions, or_conditions, operator
                )
        return query, and_conditions, or_conditions

    def _apply_logical_operator(
        self, query, tbl_name, operator, filters, and_conditions, or_conditions
    ):
        for subfilter in filters:
            self.apply_filters(
                query, tbl_name, subfilter, and_conditions, or_conditions, operator
            )

    def _apply_filter(
        self, tbl_name, key, value, and_conditions, or_conditions, operator
    ):
        sub_query = self.get_filter_query(tbl_name, {key: value})
        if sub_query is not None:
            if operator == "and":
                and_conditions.append(sub_query)
            elif operator == "or":
                or_conditions.append(sub_query)

    def generate_filters(self, query, tbl_name, filters):
        query, and_conditions, or_conditions = self.apply_filters(
            query, tbl_name, filters
        )
        if and_conditions:
            query = query.filter(and_(*and_conditions))
        if or_conditions:
            query = query.filter(or_(*or_conditions))
        return query

    # // if anything facing datetime query doesn't work please comment this below  lines
    
    # def execute_query(self, query):
    #     try:
    #         with self.Session() as session:
    #             result = session.execute(query)
    #             # Oracle returns rows differently - need to convert to dict
    #             rows = result.fetchall()
    #             if not rows:
    #                 return []
                
    #             # Convert Oracle result to list of dictionaries
    #             columns = result.keys()
    #             return [dict(zip(columns, row)) for row in rows]
                
    #     except Exception as e:
    #         logging.error("Error executing query: %s", e)
    #         return []

    def execute_query(self, query):
        try:
            with self.Session() as session:
                result = session.execute(query)
                print("result>>>>", result)
                # print("result.fetchall()>>>>", result.fetchall())
                return result.fetchall()
        except Exception as e:
            logging.error("Error executing query: %s", e)
            return [[None]]

    def generate_query_attributes(self, table_name, columns=None, json_object=True):
        """
        Generate query attributes for a given table, including handling foreign key relationships.

        :param table_name: Name of the table for which query attributes are generated
        :param columns: List of columns to include in the query. Defaults to None, which includes all columns
        :param json_object: Flag to determine if the result should be a JSON object. Defaults to True
        :return: Tuple containing query attributes and base columns
        """
        if columns is None or columns == ["*.*"]:
            columns = ["*.*"]

        model = self.get_model(table_name)
        base_columns = self._get_base_columns(table_name, columns)
        query_attributes = self._generate_base_query_attributes(model, base_columns)
        attribute_table_count = {}

        foreign_keys = inspect(self.engine).get_foreign_keys(table_name)
        for fk in foreign_keys:
            self._handle_foreign_key(
                fk, columns, json_object, query_attributes, attribute_table_count
            )

        return query_attributes, base_columns

    def _generate_base_query_attributes(self, model, base_columns):
        """
        Generate base query attributes for the given model and columns.

        :param model: SQLAlchemy model for the table
        :param base_columns: List of base columns to include in the query
        :return: List of query attributes
        """
        return [getattr(model, column) for column in base_columns]

    def _handle_foreign_key(
        self, fk, columns, json_object, query_attributes, attribute_table_count
    ):
        """
        Handle foreign key relationships and generate appropriate query attributes.

        :param fk: Foreign key dictionary
        :param columns: List of columns to include in the query
        :param json_object: Flag to determine if the result should be a JSON object
        :param query_attributes: List of query attributes to update
        :param attribute_table_count: Dictionary to track the count of attribute tables
        """
        primary_column_name = fk["constrained_columns"][0]
        related_table_name = fk["referred_table"]

        # Increment the count for the referred table
        attribute_table_count[related_table_name] = (
            attribute_table_count.get(related_table_name, 0) + 1
        )

        # Create an alias only if the table is joined more than once
        alias_name = (
            f"{related_table_name}_{attribute_table_count[related_table_name]}"
            if attribute_table_count[related_table_name] > 1
            else related_table_name
        )
        referred_table_model = (
            aliased(self.get_model(related_table_name), name=alias_name)
            if attribute_table_count[related_table_name] > 1
            else self.get_model(related_table_name)
        )

        related_columns_list = [
            item.split(".")[-1]
            for item in columns
            if primary_column_name in item.split(".") and len(item.split(".")) > 1
        ]
        if related_columns_list or columns == ["*.*"]:
            (
                related_query_attributes,
                related_base_columns,
            ) = self.generate_query_attributes(
                related_table_name, related_columns_list, json_object=json_object
            )

            if related_base_columns:
                if json_object:
                    self._append_json_attributes(
                        query_attributes,
                        referred_table_model,
                        related_base_columns,
                        primary_column_name,
                    )
                else:
                    query_attributes.extend(related_query_attributes)

    def _append_json_attributes(
        self,
        query_attributes,
        related_table_model,
        related_base_columns,
        primary_column_name,
    ):
        """
        Append JSON attributes to the query attributes list.

        :param query_attributes: List of query attributes to update
        :param related_table_model: SQLAlchemy model for the related table
        :param related_base_columns: List of base columns for the related table
        :param primary_column_name: Name of the primary column
        """
        json_pairs = []
        for related_column in related_base_columns:
            json_pairs.extend(
                [related_column, getattr(related_table_model, related_column)]
            )
        concat_expr = func.json_object(*json_pairs)
        query_attributes.append(concat_expr.label(f"{primary_column_name}"))

    def _get_base_columns(self, table_name, columns):
        if columns == ["*.*"] or "*" in columns:
            return self.table_metadata[table_name]
        elif columns:
            return [col for col in self.table_metadata[table_name] if col in columns]
        else:
            return self.table_metadata[table_name]

    def handle_sqlalchemy_error(self, e: SQLAlchemyError):
        traceback_message = "".join(
            traceback.format_exception(None, e, e.__traceback__)
        )
        print(f"Database error: {str(e)}")
        print(f"traceback_message: {traceback_message}")

        if isinstance(e, IntegrityError):
            error_message = str(e.orig)

            if "duplicate key value violates unique constraint" in error_message:
                conflicting_values = (
                    error_message.split("=")[-1].split("(")[1].split(")")[0]
                )
                detail_message = f"Duplicate entry for values: {conflicting_values}"
                return detail_message

            elif (
                "insert or update on table" in error_message
                and "violates foreign key constraint" in error_message
            ):
                missing_key_detail = error_message.split("DETAIL:  ")[1]
                foreign_key = missing_key_detail.split("(")[1].split(")")[0]
                detail_message = f"""The value '{foreign_key}' does not exist in the reference table.
                Please check and try again."""
                return detail_message

            elif (
                "null value in column" in error_message
                and "violates not-null constraint" in error_message
            ):
                column_name = error_message.split('column "')[1].split('"')[0]
                detail_message = f"""The '{column_name}' field cannot be left blank. Please provide a
                value and try again."""
                return detail_message

            else:
                return "A data error occurred. Please check that your file data is entered correctly."

        return "An unexpected database error occurred."

    def is_allowed_file(self, filename: str) -> bool:
        """
        Check if the given filename has an allowed file extension.
        """
        return (
            "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
        )

    def file_upload_validation(
        self, collection, records, user_id, resource=None, module=None
    ):
        start_time = datetime.now()
        upload_data = records.copy()

        records, field_header = self.change_header(data=records, collection=collection)

        allowed_columns, _ = self.get_data_from_table(
            "collection_fields",
            ["*.*"],
            {"collection_eq": collection},
            sort_by=["sort"],
            page=-1,
        )
        columns_collection = self.collect_column_details(allowed_columns)
        columns = columns_collection

        uploaded_record = 0
        unuploaded_record = 0

        row_errors = []
        row_upload_status = []
        for data in records:
            errors = self.process_data(data, columns, field_header)

            if errors:
                unuploaded_record += 1
                row_errors.append("    ".join(errors))
                row_upload_status.append("FAILED")
            else:
                is_uploaded, row_errors, row_upload_status = self.save_data(
                    data, collection, user_id, row_errors, row_upload_status
                )
                if is_uploaded:
                    uploaded_record += 1
                else:
                    unuploaded_record += 1

        template_eligible_columns, _ = self.get_data_from_table(
            "collection_fields",
            ["label"],
            {"collection_eq": collection, "template_eligible_eq": True},
            sort_by=["sort"],
            page=-1,
        )
        upload_data_df = pd.DataFrame(upload_data)
        upload_data_df = upload_data_df[
            [item.get("label") for item in template_eligible_columns]
        ]
        csv_url = ""
        if locally_save_file:
            self.create_error_file(
                collection, upload_data_df, field_header, row_errors, row_upload_status
            )
            csv_url = collection
        else:
            csv_url = self.upload_csv_to_s3(
                collection, upload_data_df, field_header, row_errors, row_upload_status
            )

        end_time = datetime.now()
        elapsed_time = end_time - start_time

        self.create_upload_report(
            collection,
            csv_url,
            elapsed_time,
            len(records),
            uploaded_record,
            unuploaded_record,
            user_id,
        )

        return csv_url, unuploaded_record

    async def file_upload_pre_validation(self, file, collection, user_id):
        if not self.is_allowed_file(file.filename):
            return make_failure_response(
                message="We can accept .csv and .xlsx format only"
            )

        if file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            return False, "File size exceeds the maximum allowed limit."

        if file.filename.endswith(".csv"):
            content = await file.read()
            df = pd.read_csv(io.BytesIO(content))
        elif file.filename.endswith(".xlsx"):
            print("Reading Excel files data")
            content = await file.read()
            df = pd.read_excel(io.BytesIO(content))

        df = df.replace({np.nan: None})
        if df.shape[0] > MAX_RECORDS:
            return (
                False,
                f"Number of records exceeds the maximum allowed limit of {MAX_RECORDS}",
            )
        if not df.shape[0]:
            return make_failure_response(message="No records to import.")
        print(" df.to_dict()", df.to_dict(orient="records"))

        if "created_by" in self.table_metadata[collection]:
            df["created_by"] = user_id
        if "modified_by" in self.table_metadata[collection]:
            df["modified_by"] = user_id

        if "created_date" in self.table_metadata[collection]:
            df["created_date"] = datetime.now().date()
        if "modified_date" in self.table_metadata[collection]:
            df["modified_date"] = datetime.now().date()

        return True, df

    def change_header(self, data, collection):
        df = pd.DataFrame(data)
        headers = df.columns.tolist()
        table_data = self.get_data_from_table(
            "collection_fields",
            ["label", "field"],
            {"collection_eq": collection, "template_eligible_eq": True},
            page=-1,
        )[0]
        [item["label"] for item in table_data if item["label"] not in headers]

        """validating the columns present in the upload file"""
        for item in table_data:
            if item["label"] not in headers:
                raise HTTPException(
                    status_code=400,
                    detail="The uploaded file has wrong column names or missing essential columns",
                )

        custom_header = {item["label"]: item["field"] for item in table_data}
        field_header = {item["field"]: item["label"] for item in table_data}

        df = df.rename(columns=custom_header)

        return df.to_dict(orient="records"), field_header

    def collect_column_details(self, allowed_columns):
        columns_collection = {}

        for column in allowed_columns:
            column_name = column.get("field")
            column_attributes = {
                "data_type": column.get("data_type"),
                "regex": column.get("regex"),
                "is_required": column.get("is_required"),
                "is_nullable": column.get("is_nullable"),
                "interface": column.get("interface"),
                "foreign_key_table": column.get("foreign_key_table"),
                "upload_field": column.get("upload_field"),
                "return_value": column.get("return_value"),
                "options": column.get("options"),
            }
            columns_collection[column_name] = column_attributes

        return columns_collection

    def convert_to_ddmmyyyy(self, column_data):
        if isinstance(column_data, str):
            for pattern in self.datetime_patterns:
                if re.match(pattern, column_data):
                    print("MAtchregex:", pattern, "value:", column_data)
                    column_data = pd.to_datetime(column_data).strftime("%Y-%m-%d")
                    break
        return column_data

    def convert_column_data(self, column_data):
        # Regex pattern for integer (including integers like '456.0')
        int_pattern = r"^-?\d+(\.0+)?$"
        # Regex pattern for float
        float_pattern = r"^-?\d+\.\d+$"

        column_data = self.convert_to_ddmmyyyy(column_data)

        if str(str(column_data)[0]) == "0":
            return column_data

        if re.match(int_pattern, str(column_data)):
            column_data = int(float(column_data))  # Convert '456.0' to 456 as int
        elif re.match(float_pattern, str(column_data)):
            column_data = float(column_data)  # Convert '456.9' to 456.9 as float
        else:
            column_data = str(column_data)  # Convert anything else to string
        return column_data

    def convert_to_psql_datetime(self, column_data, data_type="TIMESTAMP"):
        """
        Converts various datetime string formats into Python datetime/date/time objects.

        Args:
            column_data (str): The input string representing a date/time.
            data_type (str): 'DATE', 'DATETIME', 'TIME', or 'TIMESTAMP'.

        Returns:
            datetime/date/time object or original input if parsing fails.
        """
        data_type = data_type.upper()
        if isinstance(column_data, str):
            try:
                parsed = parser.parse(column_data)

                if data_type == "DATE":
                    return parsed.date()
                elif data_type == "DATETIME" or data_type == "TIMESTAMP":
                    return parsed
                elif data_type == "TIME":
                    return parsed.time()
                else:
                    raise ValueError(f"Unsupported data_type: {data_type}")

            except Exception as e:
                print(f"[Date Parse Error] value: '{column_data}', error: {e}")
                return column_data  # return as-is if parse fails

        return column_data  # unchanged if not a string

    def process_data(self, data, columns, field_header):
        error_container = []

        for column_name, column_data in data.items():
            if columns.get(column_name):
                if columns.get(column_name).get("is_required") and pd.isna(column_data):
                    error_container.append(
                        f"{field_header.get(column_name)} : This field is mandatory, please provide data"
                    )
                    continue
                if not pd.isna(column_data):
                    regex = columns.get(column_name).get("regex")
                    column_type = columns.get(column_name).get("data_type")
                    if column_type in ["DATE", "TIMESTAMP", "DATETIME", "TIME"]:
                        column_data = self.convert_to_psql_datetime(
                            column_data, column_type
                        )
                        data[column_name] = column_data
                    if columns.get(column_name).get("regex"):
                        column_data = str(self.convert_column_data(str(column_data)))
                        data[column_name] = column_data
                        regex_match = re.fullmatch(
                            str(regex).replace("\\\\", "\\"), str(column_data)
                        )
                        if not regex_match:
                            error_container.append(
                                f"{field_header.get(column_name)} : {column_data} value is mismatch with regex {regex}"
                            )
                            continue

                    if columns.get(column_name).get("interface") == "FORM_SEARCH":
                        display_column = columns.get(column_name).get("upload_field")
                        relation_column_data_type, _ = self.get_data_from_table(
                            "collection_fields",
                            ["data_type"],
                            {
                                "collection_eq": columns.get(column_name).get(
                                    "foreign_key_table"
                                ),
                                "field_eq": display_column,
                            },
                        )
                        if relation_column_data_type:
                            is_datatype_valid, error_container = self.is_data_valid(
                                relation_column_data_type[0].get("data_type"),
                                column_data,
                                column_name,
                                error_container,
                            )
                            if is_datatype_valid:
                                column_data = (
                                    str(self.convert_column_data(column_data))
                                    if str(str(column_data)[0]) != "0"
                                    else str(column_data)
                                )

                                relation_data, _ = self.get_data_from_table(
                                    columns.get(column_name).get("foreign_key_table"),
                                    [columns.get(column_name).get("return_value")],
                                    {f"{display_column}_eq": column_data},
                                )
                                if relation_data:
                                    data[column_name] = relation_data[0].get(
                                        columns.get(column_name).get("return_value")
                                    )
                                else:
                                    error_container.append(
                                        f"""{field_header.get(column_name)} : Couldnot found the `{column_data}`
                                        in the {(columns.get(column_name).get('foreign_key_table'))} master table"""
                                    )
                    elif columns.get(column_name).get("interface") == "DROPDOWN":
                        options_list = json.loads(
                            columns.get(column_name).get("options")
                        )
                        if str(column_data) not in options_list:
                            error_container.append(
                                f"{field_header.get(column_name)} : Please provide any on option "
                                + ",".join(options_list)
                            )

                    elif (
                        columns.get(column_name).get("data_type") == "STRING"
                        or columns.get(column_name).get("data_type") == "TEXT"
                    ):
                        result = StringValidator.is_valid(string=str(column_data))
                        if not result:
                            error_container.append(
                                f"{field_header.get(column_name)} : Please provide valid string"
                            )

                    elif columns.get(column_name).get("data_type") == "FLOAT":
                        result = FloatValidator.is_valid(number=column_data)
                        if result:
                            data[column_name] = float(column_data)
                        else:
                            error_container.append(
                                f"{field_header.get(column_name)} : Please provide valid numbers"
                            )

                    elif columns.get(column_name).get("data_type") == "BOOL":
                        if str(column_data).lower() in ["yes", "no"]:
                            data[column_name] = (
                                True if column_data.lower() == "yes" else False
                            )
                        else:
                            error_container.append(
                                f"{field_header.get(column_name)} : Please provide Yes/No"
                            )
                    elif columns.get(column_name).get("data_type") == "INT":
                        result = IntValidator.is_valid(number=column_data)
                        if result:
                            data[column_name] = int(column_data)
                        else:
                            error_container.append(
                                f"{field_header.get(column_name)} : Please provide valid integer"
                            )

        return error_container

    def is_data_valid(self, data_type, column_data, column_name, errors):
        if data_type in ["STRING", "TEXT"]:
            result = StringValidator.is_valid(string=str(column_data))
            if not result:
                errors.append(f"{column_name} : Please provide valid string")
                return False, errors
        if data_type == "NUMERIC":
            result = FloatValidator.is_valid(number=column_data)
            if not result:
                errors.append(f"{column_name} : Please provide valid Number")
                return False, errors

        if data_type == "INT":
            result = IntValidator.is_valid(number=column_data)
            if not result:
                errors.append(f"{column_name} : Please provide valid integer")
                return False, errors
        return True, errors

    def save_data(self, data, collection, user_id, row_errors, row_upload_status):
        model = self.get_model(tbl_name=collection)

        # Filter allowed columns
        data = self.remove_unwanted_column(
            {
                col: data[col]
                for col in data.keys()
                if col in self.table_metadata[collection]
            }
        )

        # Add audit fields if present
        for user_column in ["created_by", "modified_by"]:
            if user_column in self.table_metadata[collection]:
                data[user_column] = user_id

        if "created_date" in self.table_metadata[collection]:
            data["created_date"] = datetime.utcnow()
        if "modified_date" in self.table_metadata[collection]:
            data["modified_date"] = datetime.utcnow()

        with self.Session() as s:
            s.info["user_id"] = user_id

            # Handle ID with Oracle sequence if required
            if "id" in self.table_metadata[collection] and "id" not in data:
                seq_name = f"{collection.lower()}_seq"
                try:
                    result = s.execute(text(f"SELECT {seq_name}.NEXTVAL FROM dual"))
                    next_id = result.scalar()
                except DBAPIError as e:
                    if "ORA-02289" in str(e):  # Sequence does not exist
                        s.execute(
                            text(
                                f"CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE"
                            )
                        )
                        s.commit()

                        # Retry fetching the value
                        result = s.execute(text(f"SELECT {seq_name}.NEXTVAL FROM dual"))
                        next_id = result.scalar()
                    else:
                        row_errors.append(str(e))
                        row_upload_status.append("FAILED")
                        return 0, row_errors, row_upload_status

                data["id"] = next_id

            user_to_db = model(**data)
            s.add(user_to_db)

            try:
                s.commit()
                row_errors.append("-")
                row_upload_status.append("UPLOAD")
                return 1, row_errors, row_upload_status
            except SQLAlchemyError as e:
                s.rollback()
                db_error = self.handle_sqlalchemy_error(e)
                row_errors.append(db_error)
                row_upload_status.append("FAILED")
                return 0, row_errors, row_upload_status

    def create_error_file(
        self, collection, collection_data, custom_header, error, status
    ):
        if error:
            collection_data["error"] = error
            collection_data["record_upload_status"] = status
        collection_data = collection_data.rename(columns=custom_header)
        # unuploaded_data = collection_data[collection_data["record_upload_status"] == "FAILED"]
        collection_data.to_excel(f"{collection}.xlsx", index=False)

    def upload_csv_to_s3(
        self, collection, collection_data, custom_header, error, status
    ):
        csv_buffer = StringIO()
        if error:
            collection_data["error"] = error
            collection_data["record_upload_status"] = status
        collection_data = collection_data.rename(columns=custom_header)
        collection_data = collection_data.drop(
            columns=["Created By", "Updated By"], errors="ignore"
        )
        # unuploaded_data = collection_data[collection_data["record_upload_status"] == "FAILED"]
        collection_data.to_csv(csv_buffer, index=False)
        csv_content = csv_buffer.getvalue()

        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename_base = f"{collection}_{current_timestamp}"
        s3_key = f"uploads/{filename_base}.csv"

        # Upload CSV to S3
        self.s3_client.put_object(Bucket=self.s3_bucket, Key=s3_key, Body=csv_content)
        print(f"Upload Successful: {s3_key} to bucket {self.s3_bucket}")
        upload_url = f"{docs_url}/{s3_key}"
        return upload_url

    def create_upload_report(
        self,
        collection,
        s3_url,
        elapsed_time,
        total_records,
        uploaded_record,
        unuploaded_record,
        user_id,
    ):
        report_payload = {
            "table_name": collection,
            "file_name": s3_url,
            "elapsed_time": elapsed_time,
            "status": "FAILED" if unuploaded_record else "SUCCESS",
            "total_records": total_records,
            "uploaded_records": uploaded_record,
            "failed_records": unuploaded_record,
            "uploaded_by": user_id,
        }
        self.create_record("file_upload_reports", report_payload, user_id)

    def check_date_is_valid(self, current_user_id, target_receiver_id, data):
        target_receiver_role = self.get_role_by_user_id(target_receiver_id)
        if target_receiver_role != "RM":
            return False, "Target user not RM"

        current_user_location = self.get_user_location(current_user_id)
        rm_location = self.get_user_location(target_receiver_id)

        if rm_location[0] not in current_user_location:
            return False, lead_location_mismatch
        date_time_obj = data.get("start_date", None)
        if isinstance(date_time_obj, str):
            date_time_obj = datetime.strptime(date_time_obj, "%Y-%m-%d")

        current_date = datetime.today().date()
        current_date - timedelta(days=current_date.weekday())

        if date_time_obj.date() <= current_date:
            return (
                False,
                f"You can't set {data.get('start_date')} as it is in the past or current week.",
            )

        if date_time_obj.weekday() not in [0, 6]:  # Monday is 0 and Sunday is 6
            return (
                False,
                f"You can only set {data.get('start_date')} weekly targets for either Monday or Sunday.",
            )

        return True, "The date is valid for setting a weekly target."

    async def upload_file_data(self, table_name, data):
        try:
            if table_name == "leads":
                data["status"] = 1
            # Write the filtered DataFrame to the SQL table
            data.to_sql(table_name, self.engine, if_exists="append", index=False)
            self.session.commit()
            return make_success_response(
                message="File uploaded and data imported successfully"
            )

        except SQLAlchemyError as e:
            self.handle_sqlalchemy_error(e)

        except Exception as e:
            traceback_message = "".join(
                traceback.format_exception(None, e, e.__traceback__)
            )
            print("traceback_message>>>>>>", traceback_message)
            self.session.rollback()
            raise HTTPException(
                status_code=500,
                detail="File couldn't import data. Please try again later.",
            )

    def related_tables(
        self,
        query,
        table_name: str,
        columns: list[str],
        already_joined: set[tuple[str, object]] = None,
        attribute_table_count: dict[str, int] = None,
    ):
        """
        Join related tables based on foreign key relationships in the database schema.

        :param query: The initial SQLAlchemy query object.
        :param table_name: The name of the primary table to join from.
        :param columns: The list of columns to select. Use ["*.*"] to join all related tables.
        :param already_joined: A set to keep track of already joined tables and conditions.
        :param attribute_table_count: A dictionary to keep count of how many times a table is joined.
        :return: The modified query with the necessary joins.
        """

        already_joined = already_joined or set()
        attribute_table_count = attribute_table_count or {}

        join_all = columns == ["*.*"]

        foreign_keys = self.inspector.get_foreign_keys(table_name)
        primary_table_model = self.get_model(table_name)

        query = self._join_foreign_tables(
            query,
            primary_table_model,
            foreign_keys,
            columns,
            already_joined,
            attribute_table_count,
            join_all,
        )

        return query

    def _join_foreign_tables(
        self,
        query,
        primary_table_model,
        foreign_keys: list[dict],
        columns: list[str],
        already_joined: set[tuple[str, object]],
        attribute_table_count: dict[str, int],
        join_all: bool,
    ):
        """
        Join related tables based on foreign key relationships.

        :param query: The initial SQLAlchemy query object.
        :param primary_table_model: The model of the primary table.
        :param foreign_keys: The list of foreign key relationships.
        :param columns: The list of columns to select.
        :param already_joined: A set to keep track of already joined tables and conditions.
        :param attribute_table_count: A dictionary to keep count of how many times a table is joined.
        :param join_all: A flag to determine if all related tables should be joined.
        :return: The modified query with the necessary joins.
        """
        for fk in foreign_keys:
            referred_table_name = fk["referred_table"]
            primary_column = getattr(primary_table_model, fk["constrained_columns"][0])

            attribute_table_count[referred_table_name] = (
                attribute_table_count.get(referred_table_name, 0) + 1
            )

            referred_table_model, alias_name = self._get_referred_table_model(
                referred_table_name, attribute_table_count[referred_table_name]
            )

            referred_column = getattr(referred_table_model, fk["referred_columns"][0])
            join_condition = primary_column == referred_column

            if self._should_join(
                alias_name, join_condition, already_joined, join_all, columns, fk
            ):
                query = query.outerjoin(referred_table_model, join_condition)
                already_joined.add((alias_name, join_condition))

        return query

    def _get_referred_table_model(self, referred_table_name: str, count: int):
        """
        Get the model of the referred table, with alias if needed.

        :param referred_table_name: The name of the referred table.
        :param count: The count of how many times the table is joined.
        :return: A tuple containing the referred table model and its alias name.
        """
        if count > 1:
            alias_name = f"{referred_table_name}_{count}"
            referred_table_model = aliased(
                self.get_model(referred_table_name), name=alias_name
            )
        else:
            alias_name = referred_table_name
            referred_table_model = self.get_model(referred_table_name)

        return referred_table_model, alias_name

    def _should_join(
        self,
        alias_name: str,
        join_condition: object,
        already_joined: set[tuple[str, object]],
        join_all: bool,
        columns: list[str],
        fk: dict,
    ) -> bool:
        """
        Determine if a table should be joined.

        :param alias_name: The alias name of the table.
        :param join_condition: The join condition.
        :param already_joined: A set to keep track of already joined tables and conditions.
        :param join_all: A flag to determine if all related tables should be joined.
        :param columns: The list of columns to select.
        :param fk: The foreign key relationship.
        :return: A boolean indicating if the table should be joined.
        """
        return (alias_name, join_condition) not in already_joined and (
            join_all or any(fk["constrained_columns"][0] in col for col in columns)
        )

    def clean_json(self, data, keys):
        for d in data:
            for key, value in d.items():
                if key in keys:
                    # Check if the value is already a dictionary
                    if not isinstance(value, dict):
                        # If it's not a dictionary, parse it as JSON
                        d[key] = json.loads(value)
        return data

    def get_template_as_file(self, tbl_name, file_type):
        items, _ = self.get_data_from_table(
            "collection_fields",
            ["label"],
            {"collection_eq": tbl_name, "template_eligible_eq": True},
            sort_by=["sort"],
            page=-1,
        )
        headers = [item["label"] for item in items if item["label"]]

        if file_type == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            output.seek(0)
            csv_content = output.getvalue()
            output.close()
            base64_content = base64.b64encode(csv_content.encode()).decode()
            filename = f"{tbl_name}.csv"
            headers = {"Content-Disposition": f"attachment; filename={filename}"}
            return Response(
                content=base64_content,
                media_type="application/octet-stream",
                headers=headers,
            )

        elif file_type == "xlsx":
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = tbl_name
            for idx, header in enumerate(headers, start=1):
                sheet.cell(row=1, column=idx, value=header)
            output = io.BytesIO()
            workbook.save(output)
            output.seek(0)
            xlsx_content = output.getvalue()
            output.close()
            base64_content = base64.b64encode(xlsx_content).decode()
            filename = f"{tbl_name}.xlsx"
            headers = {"Content-Disposition": f"attachment; filename={filename}"}
            return Response(
                content=base64_content,
                media_type="application/octet-stream",
                headers=headers,
            )

    # def generate_search_attributes(
    #     self,
    #     table_name,
    #     columns=None,
    #     or_conditions=None,
    #     json_object=True,
    #     search=None,
    # ):
    #     if or_conditions is None:
    #         or_conditions = []
    #     model = self.get_model(table_name)
    #     base_columns, _ = self.get_data_from_table(
    #         "collection_fields", ["*.*"], {"collection_eq": table_name}, page=-1
    #     )

    #     foreign_keys = self.inspector.get_foreign_keys(table_name)
    #     relation_column_name = {}
    #     foreign_key_table = {}
    #     for fk in foreign_keys:
    #         referred_table_name = fk["referred_table"]
    #         foreign_key_table[referred_table_name] = (
    #             foreign_key_table.get(referred_table_name, 0) + 1
    #         )
    #         relation_column_name[fk["constrained_columns"][0]] = foreign_key_table[
    #             referred_table_name
    #         ]

    #     attribute_table_count = {}
    #     for column in base_columns:
    #         field = column.get("field")
    #         foreign_table_name = column.get("foreign_key_table")
    #         if foreign_table_name:
    #             attribute_table_count[foreign_table_name] = (
    #                 attribute_table_count.get(foreign_table_name, 0) + 1
    #             )
    #         if not column.get("hidden"):
    #             if (
    #                 column.get("interface") == "FORM_SEARCH"
    #                 and field in relation_column_name
    #             ):
    #                 alias_name = (
    #                     f"{foreign_table_name}_{relation_column_name[field]}"
    #                     if relation_column_name[field] > 1
    #                     else foreign_table_name
    #                 )
    #                 relation_model = (
    #                     aliased(self.get_model(foreign_table_name), name=alias_name)
    #                     if relation_column_name[field] > 1
    #                     else self.get_model(foreign_table_name)
    #                 )

    #                 relation_columns = [json.loads(column.get("display_options"))[0]]
    #                 relation_columns.append(column.get("return_value"))
    #                 for relation_column in relation_columns:
    #                     or_conditions.append(
    #                         func.lower(
    #                             func.to_char(
    #                                 getattr(relation_model, relation_column)
    #                             )
    #                         ).like(f"%{search.lower()}%")
    #                     )
    #             else:
    #                 or_conditions.append(
    #                     func.lower(func.to_char(getattr(model, field))).like(
    #                         f"%{search.lower()}%"
    #                     )
    #                 )
    #     return or_conditions


    def remove_order_by(self, query: str) -> str:
    # More robust ORDER BY removal for Oracle
        return re.sub(r"ORDER BY.*?(?=OFFSET|\Z)", "", query, flags=re.IGNORECASE | re.DOTALL).strip()

    def generate_search_attributes(
    self,
    table_name,
    columns=None,
    or_conditions=None,
    json_object=True,
    search=None,
    ):
        if or_conditions is None:
            or_conditions = []

        model = self.get_model(table_name)

        # Get all columns metadata for search
        base_columns, _ = self.get_data_from_table(
            "collection_fields", ["*.*"], {"collection_eq": table_name}, page=-1
        )

        # Get foreign key relationships
        foreign_keys = self.inspector.get_foreign_keys(table_name)
        relation_column_name = {}
        foreign_key_table = {}
        for fk in foreign_keys:
            referred_table_name = fk["referred_table"]
            foreign_key_table[referred_table_name] = (
                foreign_key_table.get(referred_table_name, 0) + 1
            )
            relation_column_name[fk["constrained_columns"][0]] = foreign_key_table[
                referred_table_name
            ]

        # Build search conditions
        for column in base_columns:
            field = column.get("field")
            foreign_table_name = column.get("foreign_key_table")
            if foreign_table_name:
                relation_count = (
                    relation_column_name.get(field, 1)
                )
                alias_name = (
                    f"{foreign_table_name}_{relation_count}"
                    if relation_count > 1
                    else foreign_table_name
                )
                relation_model = (
                    aliased(self.get_model(foreign_table_name), name=alias_name)
                    if relation_count > 1
                    else self.get_model(foreign_table_name)
                )

            if not column.get("hidden") and column.get("interface") == "FORM_SEARCH":
                # If foreign table, search in related columns
                if foreign_table_name:
                    relation_columns = [json.loads(column.get("display_options"))[0]]
                    relation_columns.append(column.get("return_value"))
                    for relation_column in relation_columns:
                        or_conditions.append(
                            func.lower(
                                func.to_char(getattr(relation_model, relation_column))
                            ).like(f"%{search.lower()}%")
                        )
                else:
                    # Local table column search
                    # or_conditions.append(
                    #     func.lower(func.to_char(getattr(model, field))).like(
                    #         f"%{search.lower()}%"
                    #     )
                    # )

                    or_conditions.append(
                        func.lower(func.to_char(getattr(model, field))).like(
                            f"%{search.lower()}%"
                        )
                        )
            elif not column.get("hidden"):
                # Local column search for non-FORM_SEARCH fields
                # or_conditions.append(
                #     func.lower(func.to_char(getattr(model, field))).like(
                #         f"%{search.lower()}%"
                #     )
                # )

                or_conditions.append(
                    func.lower(func.to_char(getattr(model, field))).like(
                        f"%{search.lower()}%"
                    )
                )
        return or_conditions


    # def remove_duplicate_aliases(self, query_str):
    #     # Regular expression to find alias definitions like 'users AS users_2'
    #     alias_pattern = r"\b(\w+)\s+AS\s+(\w+)\b"

    #     # Find all alias definitions in the query string
    #     aliases = re.findall(alias_pattern, query_str)

    #     # Track seen aliases to identify duplicates
    #     seen_aliases = set()
    #     duplicates = []

    #     for base_name, alias_name in aliases:
    #         if alias_name in seen_aliases:
    #             duplicates.append((base_name, alias_name))
    #         else:
    #             seen_aliases.add(alias_name)

    #     # Remove duplicate alias definitions from the query string
    #     for base_name, alias_name in duplicates:
    #         pattern = rf"\b, {base_name}\s+AS\s+{alias_name}\b"
    #         query_str = re.sub(pattern, "", query_str)

    #     # Remove trailing commas after removal of duplicates
    #     # query_str = re.sub(r',(\s*\n|\s*)+', '', query_str)

    #     return query_str.strip()

    def remove_duplicate_aliases(self, query_str: str) -> str:
        # Step 1: Extract all alias declarations in JOINs like "users users_2"
        join_alias_pattern = r"(?:LEFT\s+OUTER\s+JOIN|JOIN|FROM)\s+(\w+)\s+(\w+)"
        declared_aliases = set(re.findall(join_alias_pattern, query_str))

        # Step 2: Match trailing table aliases like ", users users_2"
        trailing_alias_pattern = r",\s*(\w+)\s+(\w+)"
        trailing_aliases = re.findall(trailing_alias_pattern, query_str)

        for base_name, alias_name in trailing_aliases:
            if (base_name, alias_name) in declared_aliases:
                pattern = rf",\s*{base_name}\s+{alias_name}"
                query_str = re.sub(pattern, "", query_str)

        return query_str.strip()

    # def remove_order_by(self, query: str) -> str:
    #     return re.sub(r"ORDER BY[\s\S]*$", "", query, flags=re.IGNORECASE)

    def get_data_from_table(
        self,
        tbl_name,
        columns=["*.*"],
        filters=None,
        search=None,
        sort_by=["-id"],
        page=1,
        per_page=10,
        aggregate=None,
        group_by=None,
        request=None,
    ):
        # if request:
        #     columns=self.filter_user_read_accessible_columns(api=request.path,user_id=request.logged_in_user_id,requested_columns=columns)
        print("read_access_column", columns)
        model = self.get_model(tbl_name)
        query_attributes, _ = self.generate_query_attributes(tbl_name, columns)
        with self.Session() as s:
            # Start query with the base model
            query = s.query(*query_attributes).select_from(model)
            # Join related tables
            query = self.related_tables(query, tbl_name, columns)

            if filters:
                query = self.generate_filters(query, tbl_name, filters)
            if search and search.strip():
                or_conditions = self.generate_search_attributes(
                    tbl_name, columns, search=search
                )
                query = query.filter(or_(*or_conditions))
            order_by_details = []
            sort_by = sort_by or ["-id"]
            for column in sort_by:
                if "." in column:
                    relation_column_name = (
                        column[1:] if column.startswith("-") else column
                    )
                    primary, secondary = relation_column_name.split(".")
                    relation_table = self.relation_table_name_by_column(
                        tbl_name, primary
                    )
                    relation_model = self.get_model(relation_table)
                    relation_column = getattr(relation_model, secondary)
                    order_column = (
                        desc(relation_column)
                        if column.startswith("-")
                        else asc(relation_column)
                    )
                    order_by_details.append(order_column)
                elif column.startswith("-"):
                    order_by_details.append(desc(getattr(model, column[1:])))
                else:
                    order_by_details.append(asc(getattr(model, column)))
            query = query.order_by(*order_by_details)

            if aggregate:
                for agg_func, agg_column in aggregate.items():
                    query_attributes.append(
                        getattr(func, agg_func)((getattr(model, agg_column))).label(
                            f"{agg_func}_{agg_column}"
                        )
                    )
                query = s.query(*query_attributes).select_from(model)
                query = self.related_tables(query, tbl_name, columns)
                if filters:
                    query = self.generate_filters(query, tbl_name, filters)
            if group_by:
                query_attributes, _ = self.generate_query_attributes(
                    tbl_name, group_by, json_object=False
                )
                query = query.group_by(*query_attributes)

            # Compile the query statement
            compiled_query = query.statement.compile(
                dialect=self.engine.dialect, compile_kwargs={"literal_binds": True}
            )
            # Modify the query string to remove duplicate aliases dynamically

            query_str = self.remove_duplicate_aliases(compiled_query.string)

            # // if anything facing datetime query doesn't work please comment this below two lines

            if not "TO_DATE" in query_str:
                query_str = query_str.replace("', ", "' VALUE ")
            print("final query>>>>", query_str)

            # Step 1: Remove ORDER BY for count
            countable_query = self.remove_order_by(query_str.strip().rstrip(";"))

            # Count total records before pagination
            count_query = text(
                f"SELECT COUNT(*) AS total_count FROM ({countable_query})"
            )
            print("count query ->>>> ",count_query)

            print("count query result ->>>> ", self.execute_query(count_query))
            total_records = self.execute_query(count_query)[0][0]
            total_pages = ceil(total_records / per_page)
            offset = (page - 1) * per_page

            # Oracle-specific pagination
            if page > 0:
                # Using ROWNUM for Oracle pagination
                query_str = f"""
                SELECT * FROM (
                    SELECT a.*, ROWNUM rnum FROM (
                        {query_str}
                    ) a WHERE ROWNUM <= {offset + per_page}
                ) WHERE rnum > {offset}
                """
                result = self.execute_query(text(query_str))
            else:
                result = self.execute_query(text(query_str))


            # # Calculate pagination
            # total_pages = ceil(total_records / per_page)
            # offset = (page - 1) * per_page

            # result = (
            #     self.execute_query(
            #         text(
            #             f"{query_str} OFFSET {offset} ROWS FETCH NEXT {per_page} ROWS ONLY"
            #         )
            #     )
            #     if page > 0
            #     else self.execute_query(text(query_str))
            # )
            # Convert the result to JSON format
            result_as_json = (
                [
                    {
                        key: json.loads(value)
                        if isinstance(value, str)
                        and value.startswith("{")
                        and value.endswith("}")
                        else value
                        for key, value in row._asdict().items()
                    }
                    for row in result
                ]
                if result
                else []
            )
            # Prepare metadata
            metadata = {
                "page": page,
                "per_page": per_page,
                "total_number_of_page": total_pages,
                "records": total_records,
            }
            return result_as_json, metadata

    def get_record_by_id(self, tbl_name, record_id, columns=[], filters=None):
        model = self.get_model(tbl_name)
        query_attributes, _ = self.generate_query_attributes(tbl_name, columns)
        query = self.Session().query(*query_attributes).select_from(model)
        query = self.related_tables(query, tbl_name, columns)
        if filters:
            query = self.generate_filters(query, tbl_name, filters)

        result = self.execute_query(query.filter(getattr(model, "id") == record_id))
        if not result:
            return []
        result_as_json = [row._asdict() for row in result]
        return result_as_json

    def get_user_details(self, tbl_name, record_id, columns=None):
        model = self.get_model(tbl_name)
        columns = columns if columns else self.table_metadata[tbl_name]
        query_attributes = [getattr(model, col) for col in columns]
        query = self.session.query(*query_attributes).filter_by(email=record_id)
        result = self.execute_query(query)
        if not result:
            raise HTTPException(status_code=204, detail=f"User  {record_id} not found")
        result_as_json = [{key: getattr(row, key) for key in columns} for row in result]
        return result_as_json

    def get_fields_dummy(self, tbl_name, column_name=None):
        model = self.get_model("collection_fields")
        columns = self.table_metadata["collection_fields"]
        query_attributes = [getattr(model, col) for col in columns]
        query = self.session.query(*query_attributes).filter_by(collection=tbl_name)
        result = self.execute_query(query)
        if not result:
            raise HTTPException(status_code=204, detail="No fields found")
        result_as_json = [{col: getattr(row, col) for col in columns} for row in result]
        if column_name:
            result = []
            for fields_meta in result_as_json:
                for fields in fields_meta.get("fields"):
                    if fields.get("field") == column_name:
                        result.append(fields)
            result_as_json = result
        return result_as_json

    def remove_unwanted_column(self, data):
        for col in self.delete_columns:
            if col in data.keys():
                del data[col]
        return data

    def create_record(self, tbl_name, data, user_id=None):
        model = self.get_model(tbl_name)
        # Filter allowed columns
        data = self.remove_unwanted_column(
            {
                col: data[col]
                for col in data.keys()
                if col in self.table_metadata[tbl_name]
            }
        )

        # Audit fields
        for user_column in ["created_by", "modified_by"]:
            if user_column in self.table_metadata[tbl_name]:
                data[user_column] = user_id

        if "created_date" in self.table_metadata[tbl_name]:
            data["created_date"] = datetime.utcnow()
        if "modified_date" in self.table_metadata[tbl_name]:
            data["modified_date"] = datetime.utcnow()

        with self.Session() as s:
            s.info["user_id"] = user_id

            # Handle ID with Oracle sequence
            if "id" in self.table_metadata[tbl_name] and "id" not in data:
                seq_name = f"{tbl_name.lower()}_seq"  # Assumes naming like: working_program_seq
                try:
                    result = s.execute(text(f"SELECT {seq_name}.NEXTVAL FROM dual"))
                    next_id = result.scalar()
                except DBAPIError as e:
                    if "ORA-02289" in str(e):  # Sequence does not exist
                        # Create the sequence
                        s.execute(
                            text(
                                f"CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE"
                            )
                        )
                        s.commit()

                        # Retry fetching the value
                        result = s.execute(text(f"SELECT {seq_name}.NEXTVAL FROM dual"))
                        next_id = result.scalar()
                    else:
                        raise  # Re-raise other errors

                data["id"] = next_id

            new_record = model(**data)
            s.add(new_record)
            s.commit()
            #return new_record.id
            return True

    def create_record_(self, tbl_name, data, user_id=None):
        model = self.get_model(tbl_name)
        # Filter allowed columns
        data = self.remove_unwanted_column(
            {
                col: data[col]
                for col in data.keys()
                if col in self.table_metadata[tbl_name]
            }
        )

        # # Audit fields
        # for user_column in ["created_by", "modified_by"]:
        #     if user_column in self.table_metadata[tbl_name]:
        #         data[user_column] = user_id

        # if "created_date" in self.table_metadata[tbl_name]:
        #     data["created_date"] = datetime.utcnow()
        # if "modified_date" in self.table_metadata[tbl_name]:
        #     data["modified_date"] = datetime.utcnow()

        with self.Session() as s:
            s.info["user_id"] = user_id

            # # Handle ID with Oracle sequence
            # if "id" in self.table_metadata[tbl_name] and "id" not in data:
            #     seq_name = f"{tbl_name.lower()}_seq"  # Assumes naming like: working_program_seq
            #     try:
            #         result = s.execute(text(f"SELECT {seq_name}.NEXTVAL FROM dual"))
            #         next_id = result.scalar()
            #     except DBAPIError as e:
            #         if "ORA-02289" in str(e):  # Sequence does not exist
            #             # Create the sequence
            #             s.execute(
            #                 text(
            #                     f"CREATE SEQUENCE {seq_name} START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE"
            #                 )
            #             )
            #             s.commit()

            #             # Retry fetching the value
            #             result = s.execute(text(f"SELECT {seq_name}.NEXTVAL FROM dual"))
            #             next_id = result.scalar()
            #         else:
            #             raise  # Re-raise other errors

            #     data["id"] = next_id

            new_record = model(**data)
            s.add(new_record)
            s.commit()
            #return new_record.id
            return True

    def insert_record(
        self, session, table, data, parent_id=None, parent_table=None, default_fields={}
    ):
        children = {k: v for k, v in data.items() if isinstance(v, list)}
        record_data = {k: v for k, v in data.items() if not isinstance(v, list)}
        record_data.update(default_fields)

        if parent_id and parent_table:
            record_data[f"{parent_table}_id"] = parent_id

        record = table(**record_data)
        session.add(record)
        session.flush()  # This will assign an id to the record without committing

        for child_table, child_records in children.items():
            for child_record in child_records:
                self.insert_record(
                    session,
                    self.get_model(child_table),
                    child_record,
                    record.id,
                    table.__table__.fullname,
                    default_fields=default_fields,
                )

        return record.id

    def dynamic_inserts(self, payload, user_id=None):
        try:
            with self.Session() as s:
                for parent_table, parent_data in payload.items():
                    parent_model = self.get_model(parent_table)
                    self.insert_record(
                        s,
                        parent_model,
                        parent_data,
                        default_fields={"created_by": user_id, "updated_by": user_id},
                    )
                s.commit()  # Commit the transaction after all records have been added
        except Exception as e:
            s.rollback()  # Rollback in case of any error
            # raise HTTPException(status_code=500, detail=str(e))
            logging.error(f"Error doing dynamic inserts {str(e)}")
            return "Could not save the record. Please check the administrator"
        else:
            return None

    def bulk_upserts(self, table_rows_map, user_id=FileNotFoundError):
        try:
            with self.Session() as s:
                for table_name, table_rows in table_rows_map.items():
                    model = self.get_model(table_name)
                    for each_row in table_rows:
                        if each_row.get("id"):
                            record = s.query(model).filter_by(id=each_row["id"]).first()
                            if not record:
                                raise HTTPException(
                                    status_code=204,
                                    detail=f"Record with ID {each_row['id']} not found",
                                )
                            for key, value in each_row.items():
                                if (
                                    key in self.table_metadata[table_name]
                                    or key not in self.delete_columns
                                ):
                                    setattr(record, key, value)
                            # setattr(record, "updated_by", user_id)
                        else:
                            self.insert_record(s, model, each_row)
                s.commit()  # Commit the transaction after all records have been added
        except Exception as e:
            s.rollback()  # Rollback in case of any error
            logging.error(f"Error doing dynamic inserts {str(e)}")
            return "Could not upsert the records. Please check the administrator"
        else:
            return None

    def upsert_record(self, tbl_name, data, unique_keys, user_id=None):
        model = self.get_model(tbl_name)
        data = {
            col: data[col]
            for col in data.keys()
            if col in self.table_metadata[tbl_name]
        }
        if "created_by" in self.table_metadata[tbl_name]:
            data["created_by"] = user_id
        if "modified_by" in self.table_metadata[tbl_name]:
            data["modified_by"] = user_id

        data["modified_date"] = datetime.utcnow()

        print(">>>>", data)
        with self.Session() as session:
            print("calling insert")
            session.info["user_id"] = user_id
            filters = {key: data[key] for key in unique_keys}
            instance = session.query(model).filter_by(**filters).first()

            if instance:
                for key, value in data.items():
                    setattr(instance, key, value)
            else:
                data["created_date"] = datetime.utcnow()
                instance = model(**data)
                session.add(instance)

            try:
                session.commit()
            except IntegrityError:
                print("dvdvfdsv")
                session.rollback()
                raise

            return instance.id

    def update_record(self, tbl_name, record_id, data, user_id=None):
        try:
            model = self.get_model(tbl_name)
            with self.Session() as session:
                session.info["user_id"] = user_id
                record = session.query(model).filter_by(id=record_id).first()
                if not record:
                    raise HTTPException(
                        status_code=204, detail=f"Record with ID {record_id} not found"
                    )
                for key, value in data.items():
                    if (
                        key in self.table_metadata[tbl_name]
                        or key not in self.delete_columns
                    ):
                        setattr(record, key, value)
                session.commit()
                return {
                    key: getattr(record, key) for key in self.table_metadata[tbl_name]
                }
        except SQLAlchemyError as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    def bulk_update_record(self, tbl_name, filters, data, user_id=None):
        model = self.get_model(tbl_name)
        for key in data.keys():
            if key not in self.table_metadata[tbl_name] or key in self.delete_columns:
                raise HTTPException(status_code=400, detail=f"Invalid column: {key}")

        try:
            with self.Session() as session:
                session.info["user_id"] = user_id
                filter_criteria = []
                for key, values in filters.items():
                    if isinstance(values, list):
                        filter_criteria.append(getattr(model, key).in_(values))
                    else:
                        filter_criteria.append(getattr(model, key) == values)

                stmt = update(model).where(*filter_criteria).values(**data)
                result = session.execute(stmt)
                session.commit()
                return {"updated": result.rowcount}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            session.close()

    def delete_record(self, tbl_name, record_id, user_id=None):
        model = self.get_model(tbl_name)
        with self.Session() as session:
            session.info["user_id"] = user_id
            record = session.query(model).filter_by(id=record_id).first()
            if not record:
                raise HTTPException(
                    status_code=204, detail=f"Record with ID {record_id} not found"
                )
            session.delete(record)
            session.commit()

    def get_fields(self, field_ids, is_required):
        columns = (
            self.Session()
            .query(self.collection_fields_model)
            .filter(self.collection_fields_model.id.in_(field_ids))
            .order_by(self.collection_fields_model.sort.asc())
            .all()
        )
        processed_columns = []
        for column in columns:
            column_dict = column.__dict__.copy()
            column_dict.update({"is_required": is_required})
            processed_columns.append(column_dict)
        return processed_columns

    def get_allowed_columns(self, api, action, user_id, collection=None, resource=None):
        with self.Session() as session:
            user = session.query(self.users_model).filter_by(id=user_id).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            role_id = user.role

            if api:
                filters = {"api": api, "method": action, "role": role_id}
            elif resource:
                filters = {"resource": resource, "role": role_id}
            else:
                filters = {"collection": collection, "method": action, "role": role_id}
            resource_permissions_validations = self.get_model(
                "resource_permissions_validations"
            )
            permissions = (
                session.query(resource_permissions_validations)
                .filter_by(**filters)
                .first()
            )
            if not permissions:
                return []
            allowed_columns = []
            if action == "GET":
                allowed_columns.extend(
                    self.get_fields(permissions.__dict__.get("fields", []), False)
                )
            else:
                # Retrieve required and optional fields from permissions
                required_fields = permissions.__dict__.get("required_fields", [])
                optional_fields = permissions.__dict__.get("optional_fields", [])

                # Process required fields
                if required_fields:
                    allowed_columns.extend(self.get_fields(required_fields, True))

                # Process optional fields
                if optional_fields:
                    allowed_columns.extend(self.get_fields(optional_fields, False))

            return allowed_columns

    def get_accessible_columns(self, api, user_id, access_columns=None):
        if access_columns is None:
            access_columns = []

        allowed_columns = self.get_allowed_columns(api, "GET", user_id)
        print("allowed_columns###", allowed_columns)
        if allowed_columns:
            for column in allowed_columns:
                field_name = column.get("field")
                relation_table = column.get("api")
                if relation_table:
                    relation_allowed_fields = self.get_allowed_columns(
                        "/api/" + relation_table, "GET", user_id
                    )
                    access_columns.extend(
                        [
                            f"{field_name}.{rel_col.get('field')}"
                            for rel_col in relation_allowed_fields
                        ]
                    )
                access_columns.append(field_name)
        return access_columns

    def filter_user_read_accessible_columns(self, api, user_id, requested_columns):
        accessible_columns = self.get_accessible_columns(api, user_id)
        print("accessible_columns", accessible_columns)
        filtered_columns = set()
        for column in requested_columns:
            if column == "*":
                filtered_columns.update(
                    col for col in accessible_columns if "." not in col
                )
            elif column == "*.*":
                filtered_columns.update(accessible_columns)
            elif column.endswith(".*"):
                table_name = column[:-2]
                filtered_columns.update(
                    col
                    for col in accessible_columns
                    if col.startswith(f"{table_name}.")
                )
            elif "." in column:
                filtered_columns.update(
                    col for col in accessible_columns if column == col
                )
            else:
                filtered_columns.update(
                    col for col in accessible_columns if column == col
                )
        if not filtered_columns:
            raise HTTPException(
                status_code=403, detail="User no acess to read the resource/fields"
            )
        return list(filtered_columns)

    def filter_user_write_accessible_columns(
        self, collection, user_id, requested_columns
    ):
        allowed_columns = self.get_allowed_columns(collection, "write", user_id)
        if not allowed_columns:
            raise HTTPException(
                status_code=403, detail=f"User no acess to create/edit the {collection}"
            )
        editable_columns = []
        if allowed_columns:
            for column in allowed_columns:
                editable_columns.append(column.get("field"))

        for column in requested_columns:
            if column not in editable_columns:
                raise HTTPException(
                    status_code=403, detail=f"User no acess to edit the {column}"
                )

    def get_flatten_data(self, collection_data, table_name):
        base_columns, _ = self.get_data_from_table(
            "collection_fields", ["*.*"], {"collection_eq": table_name}, page=-1
        )

        relation_map_keys = {}
        boolean_keys = []
        headers = {}
        for column in base_columns:
            field = column.get("field")
            label = column.get("label")
            headers.update({field: label})
            if column.get("interface") == "FORM_SEARCH":
                display_field = ast.literal_eval(column.get("display_options"))
                print("display_field", display_field, type(display_field))
                relation_map_keys[field] = display_field[0]
            elif column.get("data_type") == "BOOL":
                boolean_keys.append(field)

        for data in collection_data:
            for field, value in relation_map_keys.items():
                print("field", field)
                print("value", value)
                print("data", data)
                if isinstance(data[field], dict) and value in data[field]:
                    data[field] = data[field][value]
                print("data", data)
        return collection_data, headers, boolean_keys

    def export_as_file(
        self,
        data,
        file_type,
        file_name,
        summary=None,
        custom_headers=None,
        ignore_columns: list = None,
        base64_download: bool = False,   # <---- added
    ):
        flattened_data, headers, boolean_keys = self.get_flatten_data(
            data, table_name=file_name
        )
        df = pd.DataFrame(flattened_data)

        items, _ = self.get_data_from_table(
            "collection_fields",
            ["field", "export_eligible", "sort"],
            {"collection_eq": file_name},
            sort_by=["sort"],
            page=-1,
        )
        delete_columns: list = [item["field"] for item in items if item["field"] and item["export_eligible"] == False]

        if not custom_headers:
            new_header_order = [item['field'] for item in sorted(
                [item for item in items if item['export_eligible']],
                key=lambda x: (x['sort'] is None, x['sort'])
            )]
            df = df[new_header_order]

        if ignore_columns:
            delete_columns.extend(ignore_columns)
        df = df.drop(columns=delete_columns, errors="ignore")

        for bool_key in boolean_keys:
            df[bool_key] = df[bool_key].replace({True: "Yes", False: "No"})

        df = df.rename(columns=headers if not custom_headers else custom_headers)
        current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename_base = f"{file_name}_{current_timestamp}"

        # ----- CSV -----
        if file_type == "csv":
            output = io.StringIO()
            df.to_csv(output, index=False)
            content = output.getvalue().encode()
            output.close()

        # ----- XLSX -----
        elif file_type == "xlsx":
            output = io.BytesIO()
            start_row_index = 0
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                if summary:
                    summary_df = pd.DataFrame(summary, index=[0])
                    summary_df.to_excel(writer, index=False, sheet_name=file_name, startrow=start_row_index)
                    start_row_index = len(summary_df) + 2
                df.to_excel(writer, index=False, sheet_name=file_name, startrow=start_row_index)
            output.seek(0)
            content = output.getvalue()
            output.close()

        # ----- Return as base64 or upload -----
        if base64_download:
            base64_content = base64.b64encode(content).decode()
            filename = f"{filename_base}.{file_type}"
            headers = {"Content-Disposition": f"attachment; filename={filename}"}
            return Response(content=base64_content, media_type="application/octet-stream", headers=headers)
        else:
            s3_key = f"downloads/{filename_base}.{file_type}"
            if locally_save_file:
                with open(s3_key, "wb") as f:
                    f.write(content)
            else:
                self.s3_client.put_object(Bucket=self.s3_bucket, Key=s3_key, Body=content)
            upload_url = s3_key if locally_save_file else f"{docs_url}/{s3_key}"
            return make_success_response(
                data=[{"url": upload_url}], message="File Download successfully"
            )

    def get_role_by_user_id(self, user_id):
        result = self.get_record_by_id("users", user_id, ["role.name"])
        if result:
            return result[0].get("role").get("name")

    def get_co_mapped_bbh(self, user_id):
        data, _ = self.get_data_from_table(
            "co_bbh_mappings", ["*.*"], {"co_id_eq": int(user_id)}
        )
        bbh_ids = []
        if data:
            for d in data:
                bbh_ids.extend(d.get("bbh_ids"))
        return bbh_ids

    def get_bbh_mapped_rm(self, user_ids):
        data, _ = self.get_data_from_table(
            "bbh_rm_mappings", ["*.*"], {"bbh_id_in": user_ids}
        )
        rm_ids = []
        if data:
            for d in data:
                rm_ids.extend(d.get("rm_ids"))
        return rm_ids

    def get_user_location(self, user_id):
        branche_model = self.get_model("branches")
        role = self.get_role_by_user_id(user_id)
        locations = []
        if role == "ADMIN" or role == "CO":
            with self.Session() as session:
                data = (
                    session.query(
                        distinct(branche_model.branch_name).label("locations")
                    )
                    .select_from(branche_model)
                    .all()
                )
                if data:
                    locations = [location[0] for location in data]
                return locations

        else:
            result = self.get_record_by_id(
                "users", user_id, ["branch_code.branch_name"]
            )
            if result:
                locations.append(result[0].get("branch_code").get("branch_name"))
            return locations

    def get_user_branch_id(self, user_id):
        branche_model = self.get_model("branches")
        role = self.get_role_by_user_id(user_id)
        locations = []
        if role == "ADMIN" or role == "CO":
            with self.Session() as session:
                data = (
                    session.query(distinct(branche_model.id).label("locations"))
                    .select_from(branche_model)
                    .all()
                )
                if data:
                    locations = [location[0] for location in data]
                return locations

        else:
            result = self.get_record_by_id("users", user_id, ["branch_code.id"])
            if result:
                locations.append(result[0].get("branch_code").get("id"))
            return locations

    def get_user_branch(self, user_id):
        branche_model = self.get_model("branches")
        role = self.get_role_by_user_id(user_id)
        branches = []
        if role == "ADMIN" or role == "CO":
            with self.Session() as session:
                data = (
                    session.query(
                        distinct(branche_model.branch_code).label("locations")
                    )
                    .select_from(branche_model)
                    .all()
                )
                if data:
                    branches = [location[0] for location in data]
                return branches
        else:
            result = self.get_record_by_id("users", user_id, ["branch_code"])
            if result:
                branches.append(result[0].get("branch_code"))
            return branches

    def get_user_mapped_rm(self, user_id):
        role = self.get_role_by_user_id(user_id)
        if role == "ADMIN" or role == "CO":
            bbh_ids = self.get_co_mapped_bbh(user_id)
            return list(set(self.get_bbh_mapped_rm(bbh_ids)))
        elif role == "BBH":
            return list(set(self.get_bbh_mapped_rm([int(user_id)])))
        elif role == "RM":
            return [user_id]
