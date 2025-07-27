"""
Daily crawling scheduler using Celery for background tasks.
"""

from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import logging
import asyncio
from typing import List, Dict

from src.crawlers.arxiv_crawler import ArxivCrawler, TopicManager
from src.llm.providers import LLMManager
from src.social.trend_detector import SocialTrendAggregator
from src.clustering.topic_clusterer import TopicClusterer
from src.database.connection import db_manager
from src.database.models import Paper, Topic, SocialMention, CrawlingJob, Recommendation
from src.recommender import PaperRecommender
from src.email_service import EmailService

# Configure Celery
celery_app = Celery(
    'thesis_crawler',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'daily-crawl': {
            'task': 'src.scheduler.daily_crawl',
            'schedule': crontab(hour=9, minute=0),  # Daily at 9 AM
        },
        'trending-crawl': {
            'task': 'src.scheduler.trending_crawl',
            'schedule': crontab(hour=12, minute=0),  # Daily at 12 PM
        },
        'weekly-digest': {
            'task': 'src.scheduler.weekly_digest',
            'schedule': crontab(day_of_week=0, hour=8, minute=0),  # Weekly on Monday 8 AM
        }
    }
)

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def daily_crawl(self, topics: List[str] = None, max_results: int = 100):
    """Daily crawling task for new papers."""
    job_id = self.request.id
    
    try:
        with db_manager.get_session() as session:
            # Create crawling job record
            job = CrawlingJob(
                job_type='daily',
                status='running',
                topics=topics,
                max_results=max_results,
                started_at=datetime.utcnow()
            )
            session.add(job)
            session.commit()
            
            # Get active topics if not provided
            if topics is None:
                topic_manager = TopicManager()
                topics = topic_manager.get_active_topics()
            
            logger.info(f"Starting daily crawl for topics: {topics}")
            
            # Initialize components
            crawler = ArxivCrawler()
            llm_manager = LLMManager()
            trend_aggregator = SocialTrendAggregator({})  # Config loaded from env
            
            # Crawl papers
            papers = crawler.search_papers(topics, max_results=max_results, days_back=1)
            job.papers_found = len(papers)
            session.commit()
            
            # Process each paper
            processed_count = 0
            for paper in papers:
                try:
                    # Check if paper already exists
                    existing = session.query(Paper).filter_by(id=paper.id).first()
                    if existing:
                        continue
                    
                    # Create paper record
                    paper_record = Paper(
                        id=paper.id,
                        title=paper.title,
                        abstract=paper.abstract,
                        authors=paper.authors,
                        categories=paper.categories,
                        primary_category=paper.primary_category,
                        published_date=paper.published,
                        updated_date=paper.updated,
                        pdf_url=paper.pdf_url,
                        entry_url=paper.entry_url,
                        last_crawled=datetime.utcnow()
                    )
                    
                    # LLM analysis
                    try:
                        llm_response = asyncio.run(
                            llm_manager.analyze_paper(paper.title, paper.abstract)
                        )
                        analysis = json.loads(llm_response.content)
                        paper_record.llm_analysis = analysis
                        paper_record.novelty_score = analysis.get('novelty_score', 5.0)
                    except Exception as e:
                        logger.error(f"LLM analysis failed for {paper.id}: {e}")
                    
                    # Social trend analysis
                    try:
                        trends = asyncio.run(
                            trend_aggregator.get_paper_trends(paper.id, days_back=1)
                        )
                        paper_record.social_trend = {
                            'mentions': {k: len(v) for k, v in trends.items()},
                            'hot_score': trend_aggregator.calculate_hot_score(trends)
                        }
                        paper_record.hot_score = paper_record.social_trend['hot_score']
                    except Exception as e:
                        logger.error(f"Social trend analysis failed for {paper.id}: {e}")
                    
                    session.add(paper_record)
                    processed_count += 1
                    
                    if processed_count % 10 == 0:
                        session.commit()
                
                except Exception as e:
                    logger.error(f"Error processing paper {paper.id}: {e}")
                    continue
            
            # Generate recommendations
            recommender = PaperRecommender()
            recommender.generate_recommendations(session)
            
            # Send daily digest emails
            email_service = EmailService()
            email_service.send_daily_digest(session)
            
            # Update job status
            job.status = 'completed'
            job.papers_processed = processed_count
            job.completed_at = datetime.utcnow()
            session.commit()
            
            logger.info(f"Daily crawl completed. Processed {processed_count} papers.")
            
    except Exception as e:
        logger.error(f"Daily crawl failed: {e}")
        if 'job' in locals():
            with db_manager.get_session() as session:
                job = session.query(CrawlingJob).get(job_id)
                if job:
                    job.status = 'failed'
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()
                    session.commit()
        raise


@celery_app.task
def trending_crawl():
    """Special crawl for trending papers with higher priority."""
    try:
        with db_manager.get_session() as session:
            # Get trending topics
            topic_manager = TopicManager()
            topics = topic_manager.get_active_topics()
            
            crawler = ArxivCrawler()
            trending_papers = crawler.get_trending_papers(
                topics, 
                days_back=3, 
                min_score=0.5
            )
            
            logger.info(f"Found {len(trending_papers)} trending papers")
            
            # Process trending papers with higher priority
            for paper_data in trending_papers:
                paper = paper_data['paper']
                
                # Check if already exists
                existing = session.query(Paper).filter_by(id=paper.id).first()
                if existing:
                    # Update hot score
                    existing.hot_score = max(existing.hot_score, paper_data['trending_score'] * 100)
                    continue
                
                # Create new paper record
                paper_record = Paper(
                    id=paper.id,
                    title=paper.title,
                    abstract=paper.abstract,
                    authors=paper.authors,
                    categories=paper.categories,
                    primary_category=paper.primary_category,
                    published_date=paper.published,
                    updated_date=paper.updated,
                    pdf_url=paper.pdf_url,
                    entry_url=paper.entry_url,
                    hot_score=paper_data['trending_score'] * 100,
                    last_crawled=datetime.utcnow()
                )
                
                session.add(paper_record)
            
            session.commit()
            logger.info("Trending crawl completed")
            
    except Exception as e:
        logger.error(f"Trending crawl failed: {e}")
        raise


@celery_app.task
def weekly_digest():
    """Generate and send weekly digest emails."""
    try:
        with db_manager.get_session() as session:
            email_service = EmailService()
            email_service.send_weekly_digest(session)
            logger.info("Weekly digest sent")
            
    except Exception as e:
        logger.error(f"Weekly digest failed: {e}")
        raise


@celery_app.task
def topic_specific_crawl(topic: str, keywords: List[str], categories: List[str] = None):
    """Crawl for specific topic with custom parameters."""
    try:
        with db_manager.get_session() as session:
            crawler = ArxivCrawler()
            
            # Add topic if not exists
            topic_manager = TopicManager()
            topic_manager.add_topic(topic, keywords, categories)
            
            # Crawl papers for this topic
            papers = crawler.search_papers(
                [topic] + keywords,
                max_results=200,
                days_back=7,
                categories=categories or ["cs.AI", "cs.LG", "cs.CL"]
            )
            
            logger.info(f"Crawled {len(papers)} papers for topic: {topic}")
            
            # Process papers
            processed = 0
            llm_manager = LLMManager()
            
            for paper in papers:
                if not session.query(Paper).filter_by(id=paper.id).first():
                    paper_record = Paper(
                        id=paper.id,
                        title=paper.title,
                        abstract=paper.abstract,
                        authors=paper.authors,
                        categories=paper.categories,
                        primary_category=paper.primary_category,
                        published_date=paper.published,
                        updated_date=paper.updated,
                        pdf_url=paper.pdf_url,
                        entry_url=paper.entry_url,
                        last_crawled=datetime.utcnow()
                    )
                    
                    # LLM analysis
                    try:
                        llm_response = asyncio.run(
                            llm_manager.analyze_paper(paper.title, paper.abstract)
                        )
                        analysis = json.loads(llm_response.content)
                        paper_record.llm_analysis = analysis
                        paper_record.novelty_score = analysis.get('novelty_score', 5.0)
                    except Exception as e:
                        logger.error(f"LLM analysis failed: {e}")
                    
                    session.add(paper_record)
                    processed += 1
            
            session.commit()
            
            # Generate recommendations for users interested in this topic
            recommender = PaperRecommender()
            recommender.generate_recommendations_for_topic(session, topic)
            
            logger.info(f"Topic-specific crawl completed for {topic}. Processed {processed} papers.")
            
    except Exception as e:
        logger.error(f"Topic-specific crawl failed: {e}")
        raise


if __name__ == "__main__":
    # Test the scheduler
    daily_crawl.delay(["LLM", "computer vision", "machine learning"])