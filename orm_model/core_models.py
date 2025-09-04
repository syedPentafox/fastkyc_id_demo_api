from sqlalchemy import (
    Column,
    DateTime,
    Identity,
    Integer,
    PrimaryKeyConstraint,
    text,
    create_engine,
    Date,
    String,
    Boolean,
    ForeignKey,
    Text,
    Float,
    Numeric,
    Sequence,
)
from dotenv import load_dotenv
import os
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import ENUM
import json
from sqlalchemy.types import TypeDecorator, Text as TextType
import codecs
from datetime import datetime
import re

load_dotenv()


# Database URL from environment variable
DB_URL = os.getenv("DATABASE_URL")
MASTER_DATA_FOLDER_PATH = os.getenv("MASTER_DATA_FOLDER_PATH")

SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_pre_ping": True,
    "poolclass": NullPool,
    "echo": True,
}
engine = create_engine(DB_URL, **SQLALCHEMY_ENGINE_OPTIONS)
"""
Each instance of the SessionLocal class will be a database session. The class itself is not a database session yet.
But once we create an instance of the SessionLocal class, this instance will be the actual database session.
We name it SessionLocal to distinguish it from the Session we are importing from SQLAlchemy.
We will use Session as a datatype in the apis and other function.Example: db: Session = Depends(get_db)
"""
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)

"""
Now we will use the function declarative_base() that returns a class.
Later we will inherit from this class to create each of the database orm_models or classes (the ORM orm_models).
"""
Base = declarative_base()


def get_db():
    """
    It creates independent database session (SessionLocal) per request and use it throughout the request
    and then close it after the request is finished.
    And then a new session will be created for the next request when this method is called.
    :return: A database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db = next(get_db())

AbstractBase = declarative_base()


class JSONEncodedText(TypeDecorator):
    """Platform-independent JSON type using Text storage."""

    impl = TextType

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None


class IDDates:
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)


class IDDatesCreatedByModifiedBy(IDDates):
    created_by = Column(Integer, nullable=True)
    modified_by = Column(Integer, nullable=True)


class IDCreatedByCreatedDate:
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    created_by = Column(Integer, nullable=True)


class AuditLogBase(IDCreatedByCreatedDate):
    data = Column(JSONEncodedText, nullable=False)


class IDCreateDate:
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )


class States(Base):
    __tablename__ = "states"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    name = Column(String(255), unique=True, nullable=False)


class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    branch_code = Column(String(10), unique=True, nullable=True)
    branch_opening_date = Column(Date, nullable=False)
    branch_name = Column(String(255), nullable=False)
    states_id = Column(Integer, ForeignKey("states.id"), nullable=True)
    district = Column(String(255), nullable=True)
    city = Column(String(255), nullable=True)
    pincode = Column(String(20), nullable=True)
    email = Column(String(255), nullable=False)


class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    name = Column(String(255), nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    # created_date = Column(
    #     DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    # )
    # modified_date = Column(DateTime, nullable=False)
    # branch_code = Column(
    #     String(255),
    #     ForeignKey("branches.branch_code"),
    #     nullable=False,
    #     comment="Unique code identifying the branch, linked to the 'branches' table.",
    # )
    emp_code = Column(
        String(255),
        nullable=False,
        unique=True,
        comment="Unique employee code for identifying the user.",
    )
    emp_name = Column(String(255), nullable=False, comment="Full name of the employee.")
    role = Column(
        Integer,
        ForeignKey("roles.id"),
        comment="Role ID linked to the 'roles' table, specifying the user's role.",
    )
    # mobile = Column(
    #     String(255),
    #     nullable=True,
    #     unique=True,
    #     comment="Mobile phone number of the employee, must be unique if provided.",
    # )
    # email = Column(
    #     String(255),
    #     nullable=True,
    #     unique=True,
    #     comment="Email address of the employee, must be unique if provided.",
    # )
    # emp_grade = Column(
    #     String(255),
    #     nullable=False,
    #     comment="Grade or level of the employee in the organization.",
    # )
    # is_active = Column(
    #     Boolean,
    #     server_default=text("1"),
    #     comment="Indicates whether the employee is currently active.",
    # )
    # failed_attempts = Column(
    #     Integer,
    #     server_default=text("0"),
    #     nullable=True,
    #     comment="Tracks the number of failed login attempts.",
    # )
    # lockout_until = Column(
    #     DateTime,
    #     nullable=True,
    #     comment="Datetime until which the account is locked due to multiple failed attempts.",
    # )
    # lockout_count = Column(
    #     Integer,
    #     server_default=text("0"),
    #     nullable=True,
    #     comment="Tracks the number of times the account has been locked.",
    # )
    # is_locked = Column(
    #     Boolean,
    #     server_default=text("0"),
    #     comment="Indicates whether the account is currently locked.",
    # )


class CollectionField(Base):
    __tablename__ = "collection_fields"
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    collection = Column(String(1000))
    field = Column(String(1000))
    label = Column(String(1000))
    type = Column(String(1000))
    special = Column(String(1000))
    interface = Column(String(1000))
    is_required = Column(Boolean)
    options = Column(String(1000))
    display = Column(String(1000))
    display_options = Column(String(1000))
    readonly = Column(Boolean)
    hidden = Column(Boolean)
    sort = Column(Integer)
    width = Column(String(1000))
    data_type = Column(String(1000))
    default_value = Column(String(1000))
    max_length = Column(Integer, nullable=True)
    numeric_precision = Column(Integer, nullable=True)
    numeric_scale = Column(Integer, nullable=True)
    is_nullable = Column(Boolean)
    is_primary_key = Column(Boolean)
    has_auto_increment = Column(String(10))
    foreign_key_column = Column(String(1000))
    foreign_key_table = Column(String(1000))
    filters = Column(String(1000))
    comment = Column(String(1000))
    return_value = Column(String(1000))
    api = Column(String(255))
    regex = Column(String(1000))
    export_eligible = Column(Boolean, default=True, nullable=False)
    template_eligible = Column(Boolean, default=True, nullable=False)



class FileUploadReports(Base):
    __tablename__ = "file_upload_reports"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    table_name = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    elapsed_time = Column(String(255), nullable=False)
    status = Column(String(255), nullable=False)
    total_records = Column(Integer, nullable=False)
    uploaded_records = Column(Integer, nullable=False)
    failed_records = Column(Integer, nullable=False)


class Modules(Base):
    __tablename__ = "modules"

    id = Column(
        Integer,
        Sequence("module_id_seq"),
        primary_key=True,
        nullable=False,
        autoincrement=True,
    )
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(1000))
    description = Column(String(1000))


class Resources(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(1000))
    api = Column(String(1000))
    method = Column(String(1000))
    description = Column(String(1000))
    tag = Column(String(1000))


class Collections(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(1000))
    description = Column(String(1000))


class ResourcePermissionsValidation(Base):
    __tablename__ = "resource_permissions_validations"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    created_date = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    modified_date = Column(DateTime, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    modified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    module = Column(Integer, ForeignKey("modules.id"), nullable=True)
    collection = Column(Integer, ForeignKey("collections.id"), nullable=True)
    resource = Column(Integer, ForeignKey("resources.id"), nullable=True)
    role = Column(Integer, ForeignKey("roles.id"))
    api = Column(String(255), nullable=False)
    method = Column(String(255), nullable=False)
    fields = Column(JSONEncodedText)
    required_fields = Column(JSONEncodedText)
    optional_fields = Column(JSONEncodedText)


class I4CRequest(Base):
    __tablename__ = "i4c_request"
    
    request = Column(Text, nullable=True)  # CLOB
    ack_no = Column(String(30), nullable=True)  # VARCHAR2(30)
    job_id = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    status = Column(String(20), nullable=True)  # VARCHAR2(6)
    msg_type = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    received_dt = Column(DateTime, nullable=True)  # TIMESTAMP(6)

    __table_args__ = (
        PrimaryKeyConstraint("job_id", "msg_type", name="PK_I4C_REQUEST"),
    )

class FraudulentMaster(Base):
    __tablename__ = "fraudulent_master"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    fraud_type = Column(String(50), nullable=False)
    fraud_value = Column(String(100), nullable=False)
    
class UpiFraudTransactions(Base):
    __tablename__ = "upi_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class UpiFraudIncidents(Base):
    __tablename__ = "upi_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)  # NUMBER NOT NULL
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    is_valid = Column(Boolean, nullable=True, default=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)

class UpiFraudResponse(Base):
    __tablename__ = "upi_fraud_responses"

    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL
    is_success = Column(Boolean, nullable=True, default=False)


class EwalletFraudTransaction(Base):
    __tablename__ = "ewallet_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class EwalletFraudIncident(Base):
    __tablename__ = "ewallet_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)
    mode_of_payment = Column(String(50), nullable=False)
    received_dt = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)
    is_valid = Column(Boolean, nullable=True, default=False)


class EwalletFraudResponse(Base):
    __tablename__ = "ewallet_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL  
    is_success = Column(Boolean, nullable=True, default=False)         

#2



class AepsFraudTransaction(Base):
    __tablename__ = "aeps_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class AepsFraudIncident(Base):
    __tablename__ = "aeps_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)
    received_dt = Column(DateTime, nullable=False)
    mode_of_payment = Column(String(50), nullable=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)
    is_valid = Column(Boolean, nullable=True, default=False)


class AepsFraudResponse(Base):
    __tablename__ = "aeps_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL      
    is_success = Column(Boolean, nullable=True, default=False)     

#3



class CreditCardFraudTransaction(Base):
    __tablename__ = "credit_card_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class CreditCardFraudIncident(Base):
    __tablename__ = "credit_card_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    rrn = Column(String(50), primary_key=True, nullable=False)  # VARCHAR2(50) NOT NULL
    first6digit = Column(String(6), nullable=True)  # VARCHAR2(6) NOT NULL
    last4digit = Column(String(4), nullable=True)  # VARCHAR2(4) NOT NULL
    cardlength = Column(String(5), nullable=True)  # VARCHAR2(5) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)  # NUMBER NOT NULL
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    is_valid = Column(Boolean, nullable=True, default=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)

class CreditCardFraudResponse(Base):
    __tablename__ = "credit_card_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL        
    is_success = Column(Boolean, nullable=True, default=False)   

#4


class DematFraudTransaction(Base):
    __tablename__ = "demat_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class DematFraudIncident(Base):
    __tablename__ = "demat_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    is_valid = Column(Boolean, nullable=True, default=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(30) NOT NULL

class DematFraudResponse(Base):
    __tablename__ = "demat_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL           
    is_success = Column(Boolean, nullable=True, default=False)


#5



class EmailFraudTransaction(Base):
    __tablename__ = "email_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class EmailFraudIncident(Base):
    __tablename__ = "email_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)
    received_dt = Column(DateTime, nullable=False)
    mode_of_payment = Column(String(50), nullable=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)
    is_valid = Column(Boolean, nullable=True, default=False)


class EmailFraudResponse(Base):
    __tablename__ = "email_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL           
    is_success = Column(Boolean, nullable=True, default=False)


#6


class InternetBankingFraudTransaction(Base):
    __tablename__ = "internet_banking_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class InternetBankingFraudIncident(Base):
    __tablename__ = "internet_banking_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    is_valid = Column(Boolean, nullable=True, default=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)

class InternetBankingFraudResponse(Base):
    __tablename__ = "internet_banking_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL       
    is_success = Column(Boolean, nullable=True, default=False)    




class VishingFraudTransaction(Base):
    __tablename__ = "vishing_fraud_transactions"
    
    # id = Column(Numeric, primary_key=True) # NUMBER
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    sub_category = Column(String(100), nullable=False)  # VARCHAR2(100) NOT NULL
    requestor = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_bank_code = Column(String(10), nullable=False)  # VARCHAR2(10) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    payer_mobile_number = Column(String(15), nullable=False)  # VARCHAR2(15) NOT NULL
    payer_account_number = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    state = Column(String(100), nullable=True)  # VARCHAR2(100)
    district = Column(String(100), nullable=True)  # VARCHAR2(100)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    incident_response = Column(Text, nullable=True)  # CLOB


class VishingFraudIncident(Base):
    __tablename__ = "vishing_fraud_incidents"
    
    ack_no = Column(String(30), nullable=False, primary_key=True)  # VARCHAR2(30) NOT NULL
    job_id = Column(String(100), nullable=False, primary_key=True)  # VARCHAR2(100) NOT NULL
    amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    rrn = Column(String(50), nullable=False, primary_key=True)  # VARCHAR2(50) NOT NULL
    transaction_date = Column(Date, nullable=False)  # DATE NOT NULL
    transaction_time = Column(String(20), nullable=False)  # VARCHAR2(20) NOT NULL
    disputed_amount = Column(Numeric(10, 2), nullable=False)  # NUMBER(10,2) NOT NULL
    layer = Column(Numeric, nullable=False)
    received_dt = Column(DateTime, nullable=False)  # TIMESTAMP(6) NOT NULL
    mode_of_payment = Column(String(50), nullable=False)  # VARCHAR2(50) NOT NULL
    is_valid = Column(Boolean, nullable=True, default=False)
    status = Column(String(30), nullable=True)  # VARCHAR2(6)

class VishingFraudResponse(Base):
    __tablename__ = "vishing_fraud_responses"
 
    job_id = Column(String(100), nullable=False, primary_key=True)   # VARCHAR2(100) NOT NULL
    ack_no = Column(String(30), nullable=False, primary_key=True)    # VARCHAR2(30) NOT NULL
    rrn = Column(String(30), nullable=False, primary_key=True)       # VARCHAR2(30) NOT NULL
    incident_response = Column(Text, nullable=True)                  # CLOB
    received_dt = Column(DateTime, nullable=False)                   # TIMESTAMP(6) NOT NULL         
    is_success = Column(Boolean, nullable=True, default=False)  


class BranchManagerDetails(Base):
    __tablename__ = "branch_manager_details"   # Oracle table name

    branch_code = Column(String(20), nullable=False, primary_key=True)  # VARCHAR2(20) PK
    branch_name = Column(String(100), nullable=False)  # VARCHAR2(100)
    emp_name = Column(String(100), nullable=False)  # VARCHAR2(100)
    designation = Column(String(100), nullable=False)  # VARCHAR2(100)
    mobile = Column(String(15), nullable=False)  # VARCHAR2(15)
    mail = Column(String(100), nullable=False)  # VARCHAR2(100)

class BankMaster(Base):
    __tablename__ = "bank_master"

    bank_code = Column(Integer, primary_key=True, nullable=False)
    bank_name = Column(String(200), nullable=False)
    ifsc_code = Column(String(20), nullable=True)


class StatusMaster(Base):
    __tablename__ = "status_master"

    status_code = Column(String(20), nullable=False, primary_key=True)  # VARCHAR2(20) PK
    status_name = Column(String(100), nullable=False)  # VARCHAR2(100)
    status_description = Column(Text, nullable=True)  # CLOB

# Dictionary mapping models to their corresponding JSON files
models_and_files = {
    BranchManagerDetails: "branch_manager_details.json",
    BankMaster: "bank_master.json",
    StatusMaster: "status_master.json",
    CollectionField: "collection_fields.json",
    FraudulentMaster: "fraudulent_master.json",
    User: "users.json",
}

# Get a database session
db = next(get_db())


# Regex to detect ISO date or datetime strings
iso_date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
iso_datetime_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def try_parse_datetime(value):
    """Try to parse ISO date or datetime string to a Python datetime object."""
    if isinstance(value, str):
        try:
            if iso_datetime_pattern.match(value):
                return datetime.fromisoformat(value)
            elif iso_date_pattern.match(value):
                return datetime.fromisoformat(value)  # Also safe for dates
        except ValueError:
            pass
    return value


def bulk_insert_from_json(model_class, file_path):
    # Open the JSON file and load its data
    with codecs.open(os.getenv("MASTER_DATA_FOLDER_PATH") + file_path, "r") as file:
        data = json.load(file)
        # Check if the data is a list and the table is empty
        if isinstance(data, list) and db.query(model_class).count() == 0:
            for item in data:
                # Convert any datetime-looking string to Python datetime
                for key, value in item.items():
                    item[key] = try_parse_datetime(value)
            # Create model instances from the JSON data
            records = [model_class(**item) for item in data]
            # Bulk insert the records into the database
            db.bulk_save_objects(records)
            # Commit the transaction
            db.commit()


def bulk_insert_from_json_file():
    # Iterate over each model and its corresponding JSON file
    for model, file_path in models_and_files.items():
        # Perform bulk insert for each model
        bulk_insert_from_json(model, file_path)
