
import os
import uuid
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,Enum,
    DateTime, Text, ForeignKey, text, JSON
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import NullPool

# =====================================================
# DATABASE
# =====================================================

DB_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    poolclass=NullPool,
    connect_args={"charset": "utf8mb4"},
    pool_recycle=3600,
    echo=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =====================================================
# MASTER TABLES
# =====================================================

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    
    # Tokens (Nullable)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    
    # Login Timestamps
    first_logged_in = Column(DateTime, nullable=True)
    last_logged_in = Column(DateTime, nullable=True)
    
    # Contact Info
    mobile = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    
    # Organization link (Defaulted to 1 as per your schema)
    organization_id = Column(Integer, nullable=False, default=1)
    
    # Enum Status fields
    status = Column(Enum('active', 'inactive'), server_default='active')
    sb_enabled = Column(Enum('0', '1'), server_default='0')
    prod_enabled = Column(Enum('0', '1'), server_default='0')
    
class FeatureMaster(Base):
    __tablename__ = "features_master"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Core fields
    feature = Column(Text, nullable=False)
    title = Column(String(255), nullable=True)
    feature_description = Column(Text, nullable=True)
    category = Column(String(255), nullable=True)
    icon = Column(String(255), nullable=True)
    status = Column(String(50), nullable=True, server_default=text("'active'"))
    url = Column(String(255), nullable=True)
    request = Column(Text, nullable=True)
    response = Column(Text, nullable=True)

    # Audit fields
    created_date = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    modified_date = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    )

    last_modified_by = Column(
        Integer,
        nullable=True,
        server_default=text("0")
    )



class FieldMaster(Base):
    __tablename__ = "field_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field = Column(String(255))
    label = Column(String(255))
    type = Column(String(100))
    interface = Column(String(100))
    is_required = Column(Boolean, default=True)
    regex = Column(String(255))
    upload_type = Column(String(100))
    extensions = Column(String(255))
    multipart = Column(Boolean, default=False)
    hidden = Column(Boolean, default=False)
    max_file_size = Column(Integer)
    options = Column(Text)
    sort = Column(Integer)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

# =====================================================
# FEATURE CONFIGURATION
# =====================================================

class FeatureFlow(Base):
    __tablename__ = "feature_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255))
    status = Column(String(50), default="active", server_default="active")
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))


class FeatureApiDependency(Base):
    __tablename__ = "feature_api_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_id = Column(Integer, ForeignKey("feature_flow.id"), nullable=False)
    api_id = Column(Integer, ForeignKey("features_master.id"), nullable=False)

    execution_order = Column(Integer)

    api_type = Column(String(50), default="default")
    poll_interval = Column(Integer)
    poll_max_attempts = Column(Integer)
    poll_success_path = Column(String(255))
    poll_success_value = Column(String(255))

    is_conditional = Column(Boolean, default=False)
    condition_field = Column(String(255))
    condition_value = Column(String(255))

    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    feature = relationship("FeatureFlow")
    api = relationship("FeatureMaster")


class ApiRequiredField(Base):
    __tablename__ = "api_required_fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_id = Column(Integer, ForeignKey("features_master.id"), nullable=False)
    field_id = Column(Integer, ForeignKey("field_master.id"), nullable=False)
    is_mandatory = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    api = relationship("FeatureMaster")
    field = relationship("FieldMaster")

# =====================================================
# FLOW CONFIGURATION
# =====================================================

class Flow(Base):
    __tablename__ = "flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255))
    status = Column(String(50))
    created_by = Column(Integer, ForeignKey("customers.id"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    creator = relationship("Customer")


class FlowFeatureMap(Base):
    __tablename__ = "flow_features_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False)
    feature_id = Column(Integer, ForeignKey("feature_flow.id"), nullable=False)
    execution_order = Column(Integer)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    flow = relationship("Flow")
    feature = relationship("FeatureFlow")

# =====================================================
# FLOW RUNTIME
# =====================================================

class ActiveFlow(Base):
    __tablename__ = "active_flows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False)

    end_customer_identifier = Column(JSON)

    current_feature_id = Column(Integer)
    current_api_id = Column(Integer)

    authentication_required = Column(Boolean, default=False)
    authentication_type = Column(String(50), default=None)

    current_step = Column(Integer)
    total_step = Column(Integer)

    expires_at = Column(DateTime)
    status = Column(String(50))
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))

    activated_by = Column(Integer, ForeignKey("customers.id"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    flow = relationship("Flow")
    customer = relationship("Customer")


class JourneyLog(Base):
    __tablename__ = "journey_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    active_flow_id = Column(String(36), ForeignKey("active_flows.id"), nullable=False)
    feature_id = Column(Integer, ForeignKey("feature_flow.id"), nullable=False)
    api_id = Column(Integer, ForeignKey("features_master.id"), nullable=False)

    execution_order = Column(Integer)
    status = Column(String(50))

    request_log = Column(Text)
    response_log = Column(Text)

    poll_attempt = Column(Integer)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    active_flow = relationship("ActiveFlow")
    feature = relationship("FeatureFlow")
    api = relationship("FeatureMaster")

# =====================================================
# CUSTOMER ↔ FLOW
# =====================================================

class CustomerFlowMapping(Base):
    __tablename__ = "customer_flow_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    flow_id = Column(Integer, ForeignKey("flows.id"), nullable=False)
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

    customer = relationship("Customer")
    flow = relationship("Flow")

# =====================================================
# CREATE TABLES
# =====================================================

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully.")
