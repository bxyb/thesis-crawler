# Thesis Crawler

An intelligent academic paper crawler that discovers trending research papers from arXiv, analyzes them using Chinese LLM providers (DeepSeek, Kimi, Seed, GLM), and provides personalized recommendations based on social media trends and user interests.

## 🎯 Features

- **arXiv Crawling**: Daily automated crawling of latest papers from arXiv
- **Chinese LLM Analysis**: Uses DeepSeek, Kimi, Seed, and GLM for paper analysis
- **Social Trend Detection**: Monitors trends on X, Reddit, Hugging Face, and Zhihu
- **Personalized Recommendations**: Tailored paper suggestions based on user interests
- **Email Notifications**: Daily/weekly digest emails with personalized recommendations
- **Web Dashboard**: Interactive web interface for browsing and managing papers
- **Topic Management**: Dynamic topic monitoring and user-specific interests
- **Clustering**: Groups papers by topics using embeddings and ML
- **Hot Score Calculation**: Combines social media buzz and recency

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/bxyb/thesis-crawler.git
cd thesis-crawler

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and settings
```

### 2. Configuration

Configure your environment variables in `.env`:

```bash
# Required: Chinese LLM API keys
DEEPSEEK_API_KEY=your-deepseek-key
KIMI_API_KEY=your-kimi-key
SEED_API_KEY=your-seed-key
GLM_API_KEY=your-glm-key

# Required: Email settings for notifications
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Optional: Social media APIs
X_API_KEY=your-x-api-key
REDDIT_CLIENT_ID=your-reddit-client-id
```

### 3. Database Setup

```bash
# Initialize database
python -c "from src.database.connection import db_manager; db_manager.create_tables()"
```

### 4. Start Services

```bash
# Start Redis (for Celery)
redis-server

# Start Celery worker for background tasks
celery -A src.scheduler worker --loglevel=info

# Start Celery beat for scheduled tasks
celery -A src.scheduler beat --loglevel=info

# Start web dashboard
python app.py
```

### 5. Access Dashboard

- Web Dashboard: http://localhost:5000
- Register an account and set your topics of interest
- Your daily digest will start automatically

## 📊 Usage

### Web Dashboard

1. **Register/Login**: Create an account and set your research interests
2. **Topics**: Add topics you want to monitor (e.g., "LLM", "Computer Vision")
3. **Preferences**: Configure email frequency and recommendation settings
4. **Browse Papers**: View trending papers with analysis and social buzz
5. **Recommendations**: Get personalized paper suggestions

### API Endpoints

#### Manual Crawling
```bash
# Trigger daily crawl
curl -X POST http://localhost:5000/api/crawl-now \
  -H "Content-Type: application/json" \
  -d '{"topics": ["LLM", "transformer"]}'
```

#### Topic-Specific Crawl
```python
from src.scheduler import topic_specific_crawl

# Crawl specific topic
topic_specific_crawl.delay("LLM", ["large language model", "transformer"])
```

## 🔧 Architecture

```
thesis-crawler/
├── src/
│   ├── crawlers/
│   │   └── arxiv_crawler.py      # arXiv paper discovery
│   ├── llm/
│   │   └── providers.py          # Chinese LLM integrations
│   ├── social/
│   │   └── trend_detector.py     # Social media monitoring
│   ├── clustering/
│   │   └── topic_clusterer.py    # Paper grouping by topics
│   ├── database/
│   │   ├── models.py             # SQLAlchemy models
│   │   └── connection.py         # Database management
│   ├── scheduler.py              # Celery tasks
│   ├── recommender.py           # Personalized recommendations
│   └── email_service.py          # Email notifications
├── templates/
├── app.py                        # Flask web application
└── requirements.txt
```

## 📈 Data Flow

1. **Daily Crawling**: Celery task fetches latest papers from arXiv
2. **LLM Analysis**: Chinese LLMs analyze paper abstracts
3. **Social Monitoring**: Checks trends on social media platforms
4. **Scoring**: Combines novelty, relevance, and social buzz
5. **Clustering**: Groups papers by topics using embeddings
6. **Recommendations**: Generates personalized suggestions
7. **Notifications**: Sends daily/weekly emails to users

## 🎯 Supported Topics

Add any research topics dynamically:
- Large Language Models (LLM)
- Computer Vision (CV)
- Natural Language Processing (NLP)
- Machine Learning (ML)
- Robotics
- AI Ethics
- Reinforcement Learning
- And many more...

## 📧 Email Notifications

**Daily Digest**: Top recommendations based on your interests  
**Weekly Summary**: Comprehensive overview of trending papers  
**Instant Alerts**: Hot papers above threshold  
**Customizable**: Frequency, topics, and preferences

## 🛠️ Development

### Adding New LLM Provider

1. Add provider class in `src/llm/providers.py`
2. Add API key to `.env`
3. Update requirements if needed

### Adding New Social Platform

1. Add detector class in `src/social/trend_detector.py`
2. Add API configuration
3. Update scoring algorithm

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## 🔍 Monitoring

### Logs
```bash
# Check Celery logs
tail -f celery_worker.log
tail -f celery_beat.log

# Check Flask logs
tail -f app.log
```

### Health Checks

```bash
# Test email configuration
python -c "from src.email_service import EmailService; EmailService().send_test_email('your-email@test.com')"

# Test LLM connection
python -c "from src.llm.providers import LLMManager; print(LLMManager().get_available_providers())"
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- Create an issue on GitHub
- Check logs for common issues
- Verify API keys and configuration