from sqlalchemy import Column, Integer, String, Float, ForeignKey, Table, DateTime, func
from sqlalchemy.orm import relationship
from database import Base

# Association table for Lead and Search (Many-to-Many)
search_leads = Table(
    'search_leads',
    Base.metadata,
    Column('search_id', Integer, ForeignKey('searches.id'), primary_key=True),
    Column('lead_id', Integer, ForeignKey('leads.id'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    search_api_key = Column(String, nullable=True)
    
    # Relationships
    searches = relationship("Search", back_populates="user")
    saved_leads_assoc = relationship("SavedLead", back_populates="user")
    
    @property
    def saved_leads(self):
        return [assoc.lead for assoc in self.saved_leads_assoc]

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, index=True)
    google_place_id = Column(String, unique=True, index=True)
    name = Column(String)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    category = Column(String, nullable=True)
    
    # Relationships
    searches = relationship("Search", secondary=search_leads, back_populates="leads")
    saved_by_users = relationship("SavedLead", back_populates="lead")

class Search(Base):
    __tablename__ = "searches"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    keyword = Column(String)
    location_name = Column(String)
    radius = Column(Integer)
    max_results = Column(Integer)
    status = Column(String, default="pending") # pending, processing, completed, failed
    progress = Column(Integer, default=0) # 0 to 100
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="searches")
    leads = relationship("Lead", secondary=search_leads, back_populates="searches")

class SavedLead(Base):
    __tablename__ = "saved_leads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    lead_id = Column(Integer, ForeignKey("leads.id"))
    category = Column(String, default="General")
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="saved_leads_assoc")
    lead = relationship("Lead", back_populates="saved_by_users")
