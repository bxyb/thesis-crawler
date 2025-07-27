from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import os
from datetime import datetime, timedelta

from src.database.connection import db_manager
from src.database.models import User, Paper, Topic, Recommendation, UserPreference
from src.recommender import PaperRecommender
from src.crawlers.arxiv_crawler import TopicManager
from src.scheduler import daily_crawl, topic_specific_crawl

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Initialize services
recommender = PaperRecommender()
topic_manager = TopicManager()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Home page with trending papers and basic info."""
    with db_manager.get_session() as db_session:
        # Get trending papers
        trending_papers = db_session.query(Paper).filter(
            Paper.hot_score > 20,
            Paper.published_date >= datetime.utcnow() - timedelta(days=7)
        ).order_by(Paper.hot_score.desc()).limit(10).all()
        
        # Get active topics
        active_topics = db_session.query(Topic).filter_by(is_active=True).all()
        
        return render_template('index.html', 
                             trending_papers=trending_papers, 
                             active_topics=active_topics)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        with db_manager.get_session() as db_session:
            user = db_session.query(User).filter_by(email=email).first()
            
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['username'] = user.username
                flash('Logged in successfully!')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return render_template('register.html')
        
        with db_manager.get_session() as db_session:
            # Check if email already exists
            if db_session.query(User).filter_by(email=email).first():
                flash('Email already registered.')
                return render_template('register.html')
            
            # Check if username already exists
            if db_session.query(User).filter_by(username=username).first():
                flash('Username already taken.')
                return render_template('register.html')
            
            # Create new user
            new_user = User(
                email=email,
                username=username,
                password_hash=generate_password_hash(password)
            )
            db_session.add(new_user)
            db_session.commit()
            
            # Create default preferences
            from src.database.models import UserPreference
            preferences = UserPreference(user_id=new_user.id)
            db_session.add(preferences)
            db_session.commit()
            
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """User logout."""
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard."""
    with db_manager.get_session() as db_session:
        user = db_session.query(User).get(session['user_id'])
        
        # Get user's recommendations
        recommendations = db_session.query(Recommendation).filter_by(
            user_id=user.id,
            is_read=False
        ).order_by(Recommendation.overall_score.desc()).limit(20).all()
        
        # Get user's topics
        user_topics = user.topics
        
        # Get preferences
        preferences = db_session.query(UserPreference).filter_by(user_id=user.id).first()
        
        return render_template('dashboard.html',
                             user=user,
                             recommendations=recommendations,
                             user_topics=user_topics,
                             preferences=preferences)

@app.route('/papers')
@login_required
def papers():
    """Browse all papers."""
    with db_manager.get_session() as db_session:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        query = db_session.query(Paper)
        
        # Filter by topic
        topic_filter = request.args.get('topic')
        if topic_filter:
            query = query.join(Paper.topics).filter(Topic.name == topic_filter)
        
        # Filter by category
        category_filter = request.args.get('category')
        if category_filter:
            query = query.filter(Paper.primary_category == category_filter)
        
        # Sort options
        sort_by = request.args.get('sort', 'date')
        if sort_by == 'hot':
            query = query.order_by(Paper.hot_score.desc())
        elif sort_by == 'novelty':
            query = query.order_by(Paper.novelty_score.desc())
        else:
            query = query.order_by(Paper.published_date.desc())
        
        papers = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Get all topics for filter
        all_topics = db_session.query(Topic).filter_by(is_active=True).all()
        
        return render_template('papers.html', 
                             papers=papers,
                             all_topics=all_topics,
                             topic_filter=topic_filter,
                             category_filter=category_filter,
                             sort_by=sort_by)

@app.route('/paper/<paper_id>')
def paper_detail(paper_id):
    """Paper detail page."""
    with db_manager.get_session() as db_session:
        paper = db_session.query(Paper).get(paper_id)
        if not paper:
            flash('Paper not found.')
            return redirect(url_for('papers'))
        
        # Mark as read if user is logged in
        if 'user_id' in session:
            from src.recommender import PaperRecommender
            recommender = PaperRecommender()
            recommendations = db_session.query(Recommendation).filter_by(
                user_id=session['user_id'],
                paper_id=paper_id
            ).all()
            
            for rec in recommendations:
                recommender.mark_recommendation_read(db_session, rec.id)
        
        return render_template('paper_detail.html', paper=paper)

@app.route('/topics', methods=['GET', 'POST'])
@login_required
def topics():
    """Manage user topics."""
    with db_manager.get_session() as db_session:
        user = db_session.query(User).get(session['user_id'])
        
        if request.method == 'POST':
            topic_name = request.form['topic_name']
            keywords = [k.strip() for k in request.form['keywords'].split(',')]
            categories = [c.strip() for c in request.form.get('categories', '').split(',')]
            
            # Add new topic
            topic_manager.add_topic(topic_name, keywords, categories)
            
            # Add to user's topics
            topic = db_session.query(Topic).filter_by(name=topic_name).first()
            if topic:
                user.topics.append(topic)
                db_session.commit()
            
            flash('Topic added successfully!')
            return redirect(url_for('topics'))
        
        # Get all topics and user's topics
        all_topics = db_session.query(Topic).filter_by(is_active=True).all()
        user_topics = user.topics
        
        return render_template('topics.html', 
                             all_topics=all_topics, 
                             user_topics=user_topics)

@app.route('/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    """User preferences."""
    with db_manager.get_session() as db_session:
        preferences = db_session.query(UserPreference).filter_by(
            user_id=session['user_id']
        ).first()
        
        if request.method == 'POST':
            preferences.min_novelty_score = float(request.form['min_novelty_score'])
            preferences.min_hot_score = float(request.form['min_hot_score'])
            preferences.max_daily_recommendations = int(request.form['max_daily_recommendations'])
            preferences.email_time = request.form['email_time']
            preferences.email_notifications = 'email_notifications' in request.form
            preferences.daily_digest = 'daily_digest' in request.form
            preferences.weekly_digest = 'weekly_digest' in request.form
            
            db_session.commit()
            flash('Preferences updated successfully!')
            return redirect(url_for('preferences'))
        
        return render_template('preferences.html', preferences=preferences)

@app.route('/api/recommendations/mark-read/<recommendation_id>', methods=['POST'])
@login_required
def mark_recommendation_read(recommendation_id):
    """Mark recommendation as read."""
    with db_manager.get_session() as db_session:
        from src.recommender import PaperRecommender
        recommender = PaperRecommender()
        recommender.mark_recommendation_read(db_session, recommendation_id)
        
        return jsonify({'success': True})

@app.route('/api/recommendations/bookmark/<recommendation_id>', methods=['POST'])
@login_required
def bookmark_recommendation(recommendation_id):
    """Bookmark recommendation."""
    with db_manager.get_session() as db_session:
        from src.recommender import PaperRecommender
        recommender = PaperRecommender()
        recommender.bookmark_recommendation(db_session, recommendation_id)
        
        return jsonify({'success': True})

@app.route('/api/crawl-now', methods=['POST'])
@login_required
def crawl_now():
    """Trigger immediate crawling."""
    topics = request.json.get('topics', [])
    
    if topics:
        topic_specific_crawl.delay(topics[0], topics)
    else:
        daily_crawl.delay()
    
    return jsonify({'success': True, 'message': 'Crawling started!'}) 

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)