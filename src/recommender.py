"""
Personalized paper recommendation system.
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging
import numpy as np
from sqlalchemy.orm import Session
import json

from src.database.models import Paper, User, Recommendation, Topic, UserPreference
from src.clustering.topic_clusterer import TopicClusterer


class PaperRecommender:
    """Generate personalized paper recommendations for users."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.clusterer = TopicClusterer()
    
    def generate_recommendations(self, session: Session):
        """Generate recommendations for all active users."""
        users = session.query(User).filter_by(is_active=True).all()
        
        for user in users:
            self.generate_user_recommendations(session, user)
    
    def generate_user_recommendations(self, session: Session, user: User):
        """Generate recommendations for a specific user."""
        try:
            # Get user preferences
            preferences = session.query(UserPreference).filter_by(user_id=user.id).first()
            if not preferences:
                preferences = self._create_default_preferences(session, user)
            
            # Get user's topics of interest
            user_topics = [topic.name for topic in user.topics if topic.is_active]
            
            # Get recent papers
            recent_papers = self._get_recent_papers(session, preferences)
            
            # Score papers
            scored_papers = self._score_papers_for_user(
                session, 
                recent_papers, 
                user, 
                preferences, 
                user_topics
            )
            
            # Select top recommendations
            top_papers = scored_papers[:preferences.max_daily_recommendations]
            
            # Create recommendations
            for paper_data in top_papers:
                self._create_recommendation(session, user, paper_data)
            
            session.commit()
            self.logger.info(f"Generated {len(top_papers)} recommendations for user {user.email}")
            
        except Exception as e:
            self.logger.error(f"Error generating recommendations for user {user.id}: {e}")
    
    def generate_recommendations_for_topic(self, session: Session, topic_name: str):
        """Generate recommendations for users interested in a specific topic."""
        topic = session.query(Topic).filter_by(name=topic_name).first()
        if not topic:
            return
        
        # Get users interested in this topic
        users = [user for user in topic.users if user.is_active]
        
        # Get papers for this topic
        papers = session.query(Paper).join(Paper.topics).filter(Topic.name == topic_name).all()
        
        for user in users:
            # Score papers for this user and topic
            scored_papers = self._score_papers_for_user(session, papers, user)
            top_papers = scored_papers[:5]  # Top 5 for topic-specific
            
            for paper_data in top_papers:
                self._create_recommendation(session, user, paper_data)
    
    def _get_recent_papers(self, session: Session, preferences: UserPreference) -> List[Paper]:
        """Get recent papers based on user preferences."""
        days_back = 7
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = session.query(Paper).filter(Paper.published_date >= cutoff_date)
        
        # Filter by categories
        if preferences.preferred_categories:
            query = query.filter(Paper.primary_category.in_(preferences.preferred_categories))
        
        if preferences.excluded_categories:
            query = query.filter(~Paper.primary_category.in_(preferences.excluded_categories))
        
        # Filter by minimum scores
        query = query.filter(Paper.novelty_score >= preferences.min_novelty_score)
        query = query.filter(Paper.hot_score >= preferences.min_hot_score)
        
        return query.order_by(Paper.published_date.desc()).limit(200).all()
    
    def _score_papers_for_user(
        self, 
        session: Session, 
        papers: List[Paper], 
        user: User, 
        preferences: UserPreference = None,
        user_topics: List[str] = None
    ) -> List[Dict]:
        """Score papers for a specific user based on multiple factors."""
        
        if not preferences:
            preferences = session.query(UserPreference).filter_by(user_id=user.id).first()
        
        if not user_topics:
            user_topics = [topic.name for topic in user.topics if topic.is_active]
        
        scored_papers = []
        
        for paper in papers:
            # Skip if already recommended
            existing = session.query(Recommendation).filter_by(
                user_id=user.id, 
                paper_id=paper.id
            ).first()
            if existing:
                continue
            
            # Calculate scores
            relevance_score = self._calculate_relevance_score(paper, user_topics)
            novelty_score = paper.novelty_score
            hot_score = paper.hot_score
            
            # Personal preference score
            preference_score = self._calculate_preference_score(paper, preferences)
            
            # Combined score with weights
            overall_score = (
                relevance_score * 0.4 +
                novelty_score * 0.2 +
                hot_score * 0.3 +
                preference_score * 0.1
            )
            
            # Generate recommendation reason
            reason = self._generate_recommendation_reason(
                paper, relevance_score, novelty_score, hot_score
            )
            
            scored_papers.append({
                'paper': paper,
                'relevance_score': relevance_score,
                'novelty_score': novelty_score,
                'hot_score': hot_score,
                'overall_score': overall_score,
                'reason': reason,
                'topics': [t.name for t in paper.topics]
            })
        
        # Sort by overall score
        scored_papers.sort(key=lambda x: x['overall_score'], reverse=True)
        return scored_papers
    
    def _calculate_relevance_score(self, paper: Paper, user_topics: List[str]) -> float:
        """Calculate how relevant a paper is to user's topics."""
        if not user_topics:
            return 5.0  # Default score
        
        paper_topics = [t.name for t in paper.topics]
        if not paper_topics:
            return 3.0
        
        # Check topic overlap
        overlap = set(user_topics).intersection(set(paper_topics))
        relevance = len(overlap) / len(user_topics) * 10
        
        return min(relevance, 10.0)
    
    def _calculate_preference_score(self, paper: Paper, preferences: UserPreference) -> float:
        """Calculate score based on user preferences."""
        score = 5.0
        
        # Boost score for preferred categories
        if preferences.preferred_categories:
            if paper.primary_category in preferences.preferred_categories:
                score += 2.0
        
        # Reduce score for excluded categories
        if preferences.excluded_categories:
            if paper.primary_category in preferences.excluded_categories:
                score -= 3.0
        
        return max(score, 0.0)
    
    def _generate_recommendation_reason(
        self, 
        paper: Paper, 
        relevance: float, 
        novelty: float, 
        hot_score: float
    ) -> str:
        """Generate a human-readable reason for the recommendation."""
        reasons = []
        
        if relevance > 7:
            reasons.append("highly relevant to your interests")
        
        if novelty > 8:
            reasons.append("highly novel research")
        elif novelty > 6:
            reasons.append("innovative approach")
        
        if hot_score > 50:
            reasons.append("trending in the research community")
        elif hot_score > 20:
            reasons.append("gaining attention")
        
        if not reasons:
            return "Based on your research interests"
        
        return f"Recommended because it's {', '.join(reasons)}"
    
    def _create_recommendation(self, session: Session, user: User, paper_data: Dict):
        """Create a recommendation record."""
        recommendation = Recommendation(
            user_id=user.id,
            paper_id=paper_data['paper'].id,
            relevance_score=paper_data['relevance_score'],
            novelty_score=paper_data['novelty_score'],
            hot_score=paper_data['hot_score'],
            overall_score=paper_data['overall_score'],
            reason=paper_data['reason'],
            topics=json.dumps(paper_data['topics'])
        )
        session.add(recommendation)
    
    def _create_default_preferences(self, session: Session, user: User) -> UserPreference:
        """Create default preferences for a new user."""
        preferences = UserPreference(
            user_id=user.id,
            min_novelty_score=5.0,
            min_hot_score=10.0,
            max_daily_recommendations=10,
            preferred_categories=["cs.AI", "cs.LG", "cs.CL"],
            email_time="09:00",
            timezone="UTC"
        )
        session.add(preferences)
        session.commit()
        return preferences
    
    def get_user_recommendations(
        self, 
        session: Session, 
        user: User, 
        limit: int = 20,
        unread_only: bool = True
    ) -> List[Recommendation]:
        """Get recommendations for a user."""
        query = session.query(Recommendation).filter_by(user_id=user.id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        return query.order_by(Recommendation.overall_score.desc()).limit(limit).all()
    
    def mark_recommendation_read(self, session: Session, recommendation_id: int):
        """Mark a recommendation as read."""
        recommendation = session.query(Recommendation).get(recommendation_id)
        if recommendation:
            recommendation.is_read = True
            session.commit()
    
    def bookmark_recommendation(self, session: Session, recommendation_id: int):
        """Bookmark a recommendation."""
        recommendation = session.query(Recommendation).get(recommendation_id)
        if recommendation:
            recommendation.is_bookmarked = True
            session.commit()
    
    def get_trending_recommendations(self, session: Session, limit: int = 10) -> List[Dict]:
        """Get trending recommendations across all users."""
        trending_papers = session.query(Paper).filter(
            Paper.hot_score > 20,
            Paper.published_date >= datetime.utcnow() - timedelta(days=7)
        ).order_by(Paper.hot_score.desc()).limit(limit).all()
        
        return [
            {
                'paper': paper,
                'hot_score': paper.hot_score,
                'novelty_score': paper.novelty_score,
                'topic': paper.llm_analysis.get('topic', 'Unknown') if paper.llm_analysis else 'Unknown'
            }
            for paper in trending_papers
        ]