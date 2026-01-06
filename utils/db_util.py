import os
import json
import logging
import traceback
import pandas as pd
from datetime import datetime
from math import ceil
import re
from sqlalchemy import create_engine, inspect, or_, and_, func, String, text, desc, asc, cast, Date, literal, event
from sqlalchemy.orm import sessionmaker, aliased, Session as orm_session
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

# Setup Logging
logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

class DatabaseHandler:
    def __init__(self):
        # Convert DATABASE_URL to async format if needed or keep standard
        DB_URL = os.getenv("DATABASE_URL")
        # Ensure pymysql is used if mysql is specified
        if DB_URL and DB_URL.startswith("mysql://"):
             DB_URL = DB_URL.replace("mysql://", "mysql+pymysql://")
            
        self.engine = create_engine(
            DB_URL,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_timeout=30,
            connect_args={"charset": "utf8mb4"} 
        )
        self.Base = automap_base()
        self.Base.prepare(self.engine, reflect=True)
        self.Session = sessionmaker(bind=self.engine)
        self.inspector = inspect(self.engine)
        
        self.tables = self.inspector.get_table_names()
        self.table_metadata = {
            table: [col['name'] for col in self.inspector.get_columns(table)]
            for table in self.tables
        }
        
        self.session = self.Session()
        
        self.FILTER_OPERATORS = {
            'eq': lambda column, value: column == value,
            'neq': lambda column, value: column != value,
            'lt': lambda column, value: column < value,
            'lte': lambda column, value: column <= value,
            'gt': lambda column, value: column > value,
            'gte': lambda column, value: column >= value,
            'in': lambda column, value: column.in_(value),
            'null': lambda column, _: column.is_(None),
            'nnull': lambda column, _: column.isnot(None),
            'contains': lambda column, value: column.contains(value),
            'icontains': lambda column, value: column.ilike(f'%{value}%'),
            'starts_with': lambda column, value: column.startswith(value),
            'ends_with': lambda column, value: column.endswith(value),
        }
        
        self.delete_columns = ["id", "created_by", "modified_by", "created_date", "modified_date"]

    def get_db_session(self):
         return self.session
     
    def check_table_exists(self, tbl_name):
        return tbl_name in self.tables

    def get_model(self, tbl_name):
        if self.check_table_exists(tbl_name):
            # Automap base stores classes in .classes
            return getattr(self.Base.classes, tbl_name, None)
        return None
        
    def get_filter_query(self, tbl_name, filters):
        (filter_name, filter_value), = filters.items()
        model = self.get_model(tbl_name) 
        if not model:
            return None

        if '_' in filter_name:
            # Simple heuristic for splitting operator
            # This assumes operator is the last part after last underscore.
            # E.g. name_eq -> column: name, op: eq
            # If column name has underscore, this logic needs to be robust. 
            # For now, following user's pattern:
            parts = filter_name.rsplit('_', 1)
            column_name = parts[0]
            operator_name = parts[1]
            
            filter_operator = self.FILTER_OPERATORS.get(operator_name)
            
            # Handle relations if needed (simplified here)
            if hasattr(model, column_name):
                column = getattr(model, column_name)
                if filter_operator:
                    return filter_operator(column, filter_value)
        return None
        

    def apply_filters(self, query, tbl_name, filters, and_conditions=None, or_conditions=None, operator="and"):
        if not isinstance(filters, dict):
            return query, and_conditions, or_conditions

        if and_conditions is None: and_conditions = []
        if or_conditions is None: or_conditions = []

        for key, value in filters.items():
            if key in ['and', 'or']:
                # Recursive call for logical operators
                for subfilter in value:
                    self.apply_filters(query, tbl_name, subfilter, and_conditions, or_conditions, key)
            else:
                sub_query = self.get_filter_query(tbl_name, {key: value})
                if sub_query is not None:
                    if operator == "and":
                        and_conditions.append(sub_query)
                    elif operator == "or":
                        or_conditions.append(sub_query)
        return query, and_conditions, or_conditions
    
    def generate_filters(self, query, tbl_name, filters):
        query, and_conditions, or_conditions = self.apply_filters(query, tbl_name, filters)
        if and_conditions:
            query = query.filter(and_(*and_conditions))
        if or_conditions:
            query = query.filter(or_(*or_conditions))
        return query

    def execute_query(self, query):
        with self.Session() as s:
            try:
                if isinstance(query, str):
                    result = s.execute(text(query))
                else:
                    result = s.execute(query)
                return result.fetchall()
            except Exception as e:
                logging.error("Error executing query: %s", e)
                return None
            
    def get_data_from_table(self, tbl_name, columns=None, filters=None, sort_by=None, page=1, per_page=10):
        model = self.get_model(tbl_name)
        if not model:
             raise HTTPException(status_code=404, detail=f"Table {tbl_name} not found")

        # Basic Select
        query = self.Session().query(model)
        
        if filters:
            query = self.generate_filters(query, tbl_name, filters)
            
        # Sorting
        if sort_by:
            for col in sort_by:
                if col.startswith("-"):
                    query = query.order_by(desc(getattr(model, col[1:])))
                else:
                    query = query.order_by(asc(getattr(model, col)))
        else:
             # Default sort by id if available
             if hasattr(model, 'id'):
                 query = query.order_by(desc(model.id))
        
        # Pagination
        total_records = query.count()
        total_pages = ceil(total_records / per_page)
        
        if page > 0:
            query = query.offset((page - 1) * per_page).limit(per_page)
            
        result = query.all()
        
        # Serialization
        result_as_json = []
        for row in result:
            # Convert SQLAlchemy object to dict
            row_dict = {c.name: getattr(row, c.name) for c in row.__table__.columns}
            
            # Handle non-serializable types like datetime
            for k, v in row_dict.items():
                if isinstance(v, datetime):
                    row_dict[k] = v.isoformat()
            
            result_as_json.append(row_dict)

        metadata = {"page": page, "per_page": per_page, "total_pages": total_pages, "total_records": total_records}
        return result_as_json, metadata

    def create_record(self, tbl_name, data):
        model = self.get_model(tbl_name)
        if not model:
            raise HTTPException(status_code=404, detail=f"Table {tbl_name} not found")

        # Filter keys that are actual columns
        valid_data = {k: v for k, v in data.items() if k in self.table_metadata.get(tbl_name, [])}
        
        try:
            with self.Session() as s:
                new_record = model(**valid_data)
                s.add(new_record)
                s.commit()
                s.refresh(new_record)
                return new_record.id
        except IntegrityError as e:
            logging.error(f"Integrity Error: {e}")
            raise HTTPException(status_code=400, detail=str(e.orig))
        except Exception as e:
            logging.error(f"DB Error: {e}")
            raise HTTPException(status_code=500, detail="Database Error")

    def update_record(self, tbl_name, record_id, data):
        model = self.get_model(tbl_name)
        if not model:
            raise HTTPException(status_code=404, detail=f"Table {tbl_name} not found")

        try:
            with self.Session() as s:
                record = s.query(model).get(record_id)
                if not record:
                    raise HTTPException(status_code=404, detail="Record not found")
                
                for key, value in data.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                
                s.commit()
                return {"message": "Record Updated Successfully"}
        except Exception as e:
             logging.error(f"DB Error: {e}")
             raise HTTPException(status_code=500, detail=str(e))

    def delete_record(self, tbl_name, record_id):
        model = self.get_model(tbl_name)
        if not model:
             raise HTTPException(status_code=404, detail=f"Table {tbl_name} not found")
        
        try:
            with self.Session() as s:
                record = s.query(model).get(record_id)
                if not record:
                    raise HTTPException(status_code=404, detail="Record not found")
                s.delete(record)
                s.commit()
                return {"message": "Record Deleted Successfully"}
        except Exception as e:
            logging.error(f"DB Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
