from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True)
    business_name = Column(String(255), nullable=True)
    business_type = Column(String(255), nullable=True)
    team_size = Column(String(100), nullable=True)
    main_challenges = Column(JSON, nullable=True)  # Store list as JSON
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions = relationship("Session", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    insights = relationship("Insight", back_populates="user")
    documents = relationship("Document", back_populates="user")

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    date = Column(DateTime, default=datetime.utcnow)
    summary = Column(Text, nullable=False)
    topics = Column(JSON, nullable=True)  # Store list as JSON

    user = relationship("UserProfile", back_populates="sessions")

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    goal = Column(Text, nullable=False)
    deadline = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed = Column(Boolean, default=False)

    user = relationship("UserProfile", back_populates="goals")

class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    insight = Column(Text, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="insights")

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=True)
    filename = Column(String(255), unique=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("UserProfile", back_populates="documents")
