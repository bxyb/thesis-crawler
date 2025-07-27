"""
Email notification system for paper recommendations.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict
import logging
from datetime import datetime, timedelta
from jinja2 import Template
import os

from src.database.models import User, Recommendation, Paper, Topic
from src.database.connection import db_manager


class EmailService:
    """Service for sending email notifications."""
    
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_user = os.getenv('EMAIL_USER')
        self.email_password = os.getenv('EMAIL_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL', self.email_user)
        
        self.logger = logging.getLogger(__name__)
        
        # Email templates
        self.templates = {
            'daily_digest': self._load_template('daily_digest.html'),
            'weekly_digest': self._load_template('weekly_digest.html'),
            'instant_notification': self._load_template('instant_notification.html')
        }
    
    def _load_template(self, template_name: str) -> Template:
        """Load email template."""
        template_path = f'templates/email/{template_name}'
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return Template(f.read())
        except FileNotFoundError:
            # Return default template
            return Template("""
            <html>
            <body>
                <h2>{{ title }}</h2>
                <p>{{ message }}</p>
                <ul>
                {% for paper in papers %}
                    <li>
                        <strong>{{ paper.title }}</strong><br/>
                        <span>Score: {{ paper.score }}</span><br/>
                        <span>{{ paper.reason }}</span><br/>
                        <a href="{{ paper.url }}">Read more</a>
                    </li>
                {% endfor %}
                </ul>
            </body>
            </html>
            """)
    
    def send_daily_digest(self, session=None):
        """Send daily digest emails to all users."""
        if session is None:
            with db_manager.get_session() as session:
                return self._send_daily_digest(session)
        else:
            return self._send_daily_digest(session)
    
    def _send_daily_digest(self, session):
        """Internal method for sending daily digest."""
        users = session.query(User).filter_by(
            is_active=True, 
            email_notifications=True, 
            daily_digest=True
        ).all()
        
        for user in users:
            try:
                recommendations = self._get_user_daily_recommendations(session, user)
                if recommendations:
                    self._send_digest_email(user, recommendations, 'daily')
                    self.logger.info(f"Daily digest sent to {user.email}")
            except Exception as e:
                self.logger.error(f"Failed to send daily digest to {user.email}: {e}")
    
    def send_weekly_digest(self, session=None):
        """Send weekly digest emails to all users."""
        if session is None:
            with db_manager.get_session() as session:
                return self._send_weekly_digest(session)
        else:
            return self._send_weekly_digest(session)
    
    def _send_weekly_digest(self, session):
        """Internal method for sending weekly digest."""
        users = session.query(User).filter_by(
            is_active=True, 
            email_notifications=True, 
            weekly_digest=True
        ).all()
        
        for user in users:
            try:
                recommendations = self._get_user_weekly_recommendations(session, user)
                if recommendations:
                    self._send_digest_email(user, recommendations, 'weekly')
                    self.logger.info(f"Weekly digest sent to {user.email}")
            except Exception as e:
                self.logger.error(f"Failed to send weekly digest to {user.email}: {e}")
    
    def send_instant_notification(self, user: User, recommendations: List[Dict]):
        """Send instant notification for important papers."""
        try:
            if not user.email_notifications:
                return
            
            subject = f"🔥 New Hot Papers for {user.username}"
            body = self._create_notification_body(recommendations, 'instant')
            
            self._send_email(user.email, subject, body)
            self.logger.info(f"Instant notification sent to {user.email}")
            
        except Exception as e:
            self.logger.error(f"Failed to send instant notification to {user.email}: {e}")
    
    def _get_user_daily_recommendations(self, session, user: User) -> List[Dict]:
        """Get daily recommendations for a user."""
        from src.recommender import PaperRecommender
        
        recommender = PaperRecommender()
        recommendations = recommender.get_user_recommendations(
            session, user, limit=10, unread_only=True
        )
        
        return [
            {
                'title': rec.paper.title,
                'authors': ', '.join(rec.paper.authors[:3]) + ('...' if len(rec.paper.authors) > 3 else ''),
                'abstract': rec.paper.abstract[:200] + '...',
                'score': rec.overall_score,
                'novelty_score': rec.novelty_score,
                'hot_score': rec.hot_score,
                'reason': rec.reason,
                'url': rec.paper.entry_url,
                'pdf_url': rec.paper.pdf_url,
                'published_date': rec.paper.published_date.strftime('%Y-%m-%d'),
                'categories': ', '.join(rec.paper.categories[:2])
            }
            for rec in recommendations
        ]
    
    def _get_user_weekly_recommendations(self, session, user: User) -> List[Dict]:
        """Get weekly recommendations for a user."""
        from src.recommender import PaperRecommender
        
        recommender = PaperRecommender()
        
        # Get recommendations from the past week
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        recommendations = session.query(Recommendation).filter(
            Recommendation.user_id == user.id,
            Recommendation.created_at >= cutoff_date,
            Recommendation.is_read == False
        ).order_by(Recommendation.overall_score.desc()).limit(20).all()
        
        return [
            {
                'title': rec.paper.title,
                'authors': ', '.join(rec.paper.authors[:3]) + ('...' if len(rec.paper.authors) > 3 else ''),
                'abstract': rec.paper.abstract[:300] + '...',
                'score': rec.overall_score,
                'novelty_score': rec.novelty_score,
                'hot_score': rec.hot_score,
                'reason': rec.reason,
                'url': rec.paper.entry_url,
                'pdf_url': rec.paper.pdf_url,
                'published_date': rec.paper.published_date.strftime('%Y-%m-%d'),
                'categories': ', '.join(rec.paper.categories[:2]),
                'topics': json.loads(rec.topics) if rec.topics else []
            }
            for rec in recommendations
        ]
    
    def _send_digest_email(self, user: User, recommendations: List[Dict], digest_type: str):
        """Send digest email to user."""
        if not recommendations:
            return
        
        subject = f"{'Daily' if digest_type == 'daily' else 'Weekly'} Research Digest - {len(recommendations)} New Papers"
        
        template = self.templates[f'{digest_type}_digest']
        
        html_body = template.render(
            user_name=user.username,
            paper_count=len(recommendations),
            papers=recommendations,
            current_date=datetime.now().strftime('%Y-%m-%d'),
            dashboard_url=os.getenv('DASHBOARD_URL', 'http://localhost:5000')
        )
        
        self._send_email(user.email, subject, html_body)
    
    def _create_notification_body(self, recommendations: List[Dict], notification_type: str) -> str:
        """Create notification email body."""
        template = self.templates[notification_type]
        
        return template.render(
            title="New Hot Papers Alert!",
            message="Here are the latest trending papers that match your interests:",
            papers=recommendations,
            current_date=datetime.now().strftime('%Y-%m-%d')
        )
    
    def _send_email(self, to_email: str, subject: str, html_body: str):
        """Send email using SMTP."""
        if not all([self.email_user, self.email_password]):
            self.logger.warning("Email credentials not configured")
            return
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_email
            msg['To'] = to_email
            
            # Add HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Connect to SMTP server
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            
            # Send email
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            raise
    
    def send_test_email(self, to_email: str):
        """Send a test email to verify configuration."""
        try:
            subject = "Test Email from Thesis Crawler"
            body = """
            <html>
            <body>
                <h2>Test Email Successful!</h2>
                <p>This is a test email from your Thesis Crawler system.</p>
                <p>If you received this email, your email configuration is working correctly.</p>
                <p>Your daily and weekly digests will start arriving soon!</p>
            </body>
            </html>
            """
            
            self._send_email(to_email, subject, body)
            self.logger.info(f"Test email sent to {to_email}")
            
        except Exception as e:
            self.logger.error(f"Failed to send test email: {e}")
            raise
    
    def send_recommendation_summary(self, user: User, summary_data: Dict):
        """Send summary of recommendations to user."""
        try:
            subject = f"Weekly Summary - {summary_data['total_recommendations']} Papers Recommended"
            
            body = f"""
            <html>
            <body>
                <h2>Weekly Summary for {user.username}</h2>
                <p>Here's your weekly summary of paper recommendations:</p>
                <ul>
                    <li>Total recommendations: {summary_data['total_recommendations']}</li>
                    <li>New papers: {summary_data['new_papers']}</li>
                    <li>Read papers: {summary_data['read_papers']}</li>
                    <li>Bookmarked papers: {summary_data['bookmarked_papers']}</li>
                </ul>
                
                <h3>Top Categories:</h3>
                <ul>
                {% for category, count in summary_data['top_categories'].items() %}
                    <li>{{ category }}: {{ count }} papers</li>
                {% endfor %}
                </ul>
                
                <p><a href="{os.getenv('DASHBOARD_URL', 'http://localhost:5000')}">View all recommendations</a></p>
            </body>
            </html>
            """
            
            self._send_email(user.email, subject, body)
            self.logger.info(f"Summary email sent to {user.email}")
            
        except Exception as e:
            self.logger.error(f"Failed to send summary email: {e}")