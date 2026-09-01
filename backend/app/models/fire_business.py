from sqlalchemy import Column, Integer, String
from app.models.verify_log import Base


class FireBusiness(Base):
    __tablename__ = "fire_businesses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    region = Column(String, index=True)
    search_region = Column(String)
    business_type = Column(String)
    field = Column(String)
    company_name = Column(String, index=True)
    representative = Column(String, index=True)
    zip_code = Column(String)
    address = Column(String)
    phone = Column(String)