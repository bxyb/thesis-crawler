"""
Database models for thesis crawler using SQLAlchemy.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

# Association table for paper-topic many-to-many relationship
paper_topics = Table(
    'paper_topics', Base.metadata,
    Column('paper_id', String(50), ForeignKey('papers.id'), primary_key=True),
    Column('topic_id', Integer, ForeignKey('topics.id'), primary_key=True)
)

# Association table for user-topic preferences
user_topics = Table(
    'user_topics', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('topic_id', Integer, ForeignKey('topics.id'), primary_key=True),
    Column('notification_frequency', String(20), default='daily'),
    Column('is_active', Boolean, default=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)


class Paper(Base):
    __tablename__ = 'papers'
    
    id = Column(String(50), primary_key=True)  # arXiv ID
    title = Column(String(500), nullable=False)
    abstract = Column(Text, nullable=False)
    authors = Column(JSON)  # List of author names
    categories = Column(JSON)  # List of arXiv categories
    primary_category = Column(String(20))
    published_date = Column(DateTime, nullable=False)
    updated_date = Column(DateTime)
    pdf_url = Column(String(500))
    entry_url = Column(String(500))
    
    # Analysis results
    llm_analysis = Column(JSON)  # LLM analysis results
    social_trend = Column(JSON)  # Social media trend data
    hot_score = Column(Float, default=0.0)  # Combined hot score
    novelty_score = Column(Float, default=0.0)  # Novelty score from LLM
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_crawled = Column(DateTime)
    
    # Relationships
    topics = relationship('Topic', secondary=paper_topics, back_populates='papers')
    recommendations = relationship('Recommendation', back_populates='paper')
    mentions = relationship('SocialMention', back_populates='paper')


class Topic(Base):
    __tablename__ = 'topics'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    keywords = Column(JSON)  # List of keywords for this topic
    categories = Column(JSON)  # List of arXiv categories
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Statistics
    paper_count = Column(Integer, default=0)
    avg_hot_score = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    papers = relationship('Paper', secondary=paper_topics, back_populates='topics')
    users = relationship('User', secondary=user_topics, back_populates='topics')


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Preferences
    email_notifications = Column(Boolean, default=True)
    daily_digest = Column(Boolean, default=True)
    weekly_digest = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # Relationships
    topics = relationship('Topic', secondary=user_topics, back_populates='users')
    recommendations = relationship('Recommendation', back_populates='user')
    notifications = relationship('Notification', back_populates='user')


class SocialMention(Base):
    __tablename__ = 'social_mentions'
    
    id = Column(Integer, primary_key=True)
    paper_id = Column(String(50), ForeignKey('papers.id'), nullable=False)
    platform = Column(String(50), nullable=False)  # x, reddit, huggingface, zhihu
    content = Column(Text)
    author = Column(String(255))
    url = Column(String(500))
    engagement_score = Column(Float, default=0.0)
    timestamp = Column(DateTime)
    
    # Raw data
    raw_data = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    paper = relationship('Paper', back_populates='mentions')


class Recommendation(Base):
    __tablename__ = 'recommendations'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    paper_id = Column(String(50), ForeignKey('papers.id'), nullable=False)
    
    # Recommendation scores
    relevance_score = Column(Float, default=0.0)
    novelty_score = Column(Float, default=0.0)
    hot_score = Column(Float, default=0.0)
    overall_score = Column(Float, default=0.0)
    
    # Recommendation reason
    reason = Column(String(500))
    topics = Column(JSON)  # Topics that triggered this recommendation
    
    # Status
    is_read = Column(Boolean, default=False)
    is_bookmarked = Column(Boolean, default=False)
    is_emailed = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    emailed_at = Column(DateTime)
    
    # Relationships
    user = relationship('User', back_populates='recommendations')
    paper = relationship('Paper', back_populates='recommendations')


class Notification(Base):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    type = Column(String(50), nullable=False)  # daily_digest, weekly_digest, instant
    title = Column(String(255), nullable=False)
    content = Column(Text)
    data = Column(JSON)  # Additional data like paper IDs
    
    # Status
    is_sent = Column(Boolean, default=False)
    is_read = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
    read_at = Column(DateTime)
    
    # Relationships
    user = relationship('User', back_populates='notifications')


class CrawlingJob(Base):
    __tablename__ = 'crawling_jobs'
    
    id = Column(Integer, primary_key=True)
    job_type = Column(String(50), nullable=False)  # daily, topic_specific, trending
    status = Column(String(20), default='pending')  # pending, running, completed, failed
    
    # Job parameters
    topics = Column(JSON)
    categories = Column(JSON)
    days_back = Column(Integer, default=7)
    max_results = Column(Integer, default=100)
    
    # Results
    papers_found = Column(Integer, default=0)
    papers_processed = Column(Integer, default=0)
    error_message = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)


class UserPreference(Base):
    __tablename__ = 'user_preferences'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Topic preferences
    min_novelty_score = Column(Float, default=5.0)
    min_hot_score = Column(Float, default=10.0)
    max_daily_recommendations = Column(Integer, default=10)
    
    # Category preferences
    preferred_categories = Column(JSON, default=list)
    excluded_categories = Column(JSON, default=list)
    
    # Email preferences
    email_time = Column(String(10), default="09:00")  # HH:MM format
    timezone = Column(String(50), default="UTC")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)