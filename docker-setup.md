# Docker Setup Guide

This guide covers how to run the Thesis Crawler using Docker containers.

## 🐳 Quick Start with Docker

### Prerequisites
- Docker & Docker Compose installed
- At least 2GB RAM and 1GB disk space

### Environment Variables

Create a `.env` file in the project root:

```bash
# Required: Chinese LLM API keys
DEEPSEEK_API_KEY=your-deepseek-key
KIMI_API_KEY=your-kimi-key
SEED_API_KEY=your-seed-key
GLM_API_KEY=your-glm-key

# Required: Email settings
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com

# Optional: Social media APIs
X_API_KEY=your-x-api-key
X_API_SECRET=your-x-api-secret
X_ACCESS_TOKEN=your-x-access-token
X_ACCESS_TOKEN_SECRET=your-x-access-token-secret

REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret

# Optional: Other settings
SECRET_KEY=your-secret-key-here
DASHBOARD_URL=http://localhost:5000
```

## 🚀 Running with Docker

### Option 1: Production Setup (PostgreSQL)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f web
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat

# Stop services
docker-compose down
```

### Option 2: Development Setup (SQLite)

```bash
# Start with SQLite for easier development
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f web

# Stop services
docker-compose -f docker-compose.dev.yml down
```

### Option 3: Single Container (Simple)

```bash
# Build and run just the web app with SQLite
docker build -t thesis-crawler .
docker run -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  thesis-crawler
```

## 📊 Service Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Web UI      │    │   Celery Worker │    │   Celery Beat   │
│   (Flask App)   │    │    (Crawler)    │    │   (Scheduler)   │
│   Port: 5000    │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                   ┌─────────────────┐
                   │     Redis       │
                   │   (Message Q)   │
                   │   Port: 6379    │
                   └─────────────────┘
                                 │
                   ┌─────────────────┐
                   │   PostgreSQL    │
                   │   (Database)    │
                   │  Port: 5432     │
                   └─────────────────┘
```

## 🔧 Management Commands

### View Running Containers
```bash
docker-compose ps

# Or for dev setup
docker-compose -f docker-compose.dev.yml ps
```

### Execute Commands in Containers
```bash
# Run a one-time crawl
 docker-compose exec celery-worker celery -A src.scheduler call daily_crawl

# Access database
 docker-compose exec postgres psql -U thesis -d thesis_crawler

# View web app logs
 docker-compose logs -f web --tail=100
```

### Scale Workers
```bash
# Add more workers for heavy processing
docker-compose up -d --scale celery-worker=3
```

## 📈 Monitoring

### Health Checks
All services include health checks:
- **Redis**: `redis-cli ping`
- **PostgreSQL**: `pg_isready`
- **Web**: `curl http://localhost:5000/health`

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f celery-worker

# With timestamps
docker-compose logs -f --timestamps web
```

## 🗄️ Data Persistence

- **Redis data**: Stored in `redis_data` volume
- **PostgreSQL data**: Stored in `postgres_data` volume
- **App data**: Mounted from `./data/` directory
- **Logs**: Mounted from `./logs/` directory

## 🔄 Updates and Maintenance

### Update Code
```bash
# Pull latest changes
git pull origin master

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Clean Up
```bash
# Stop and remove containers
docker-compose down

# Remove volumes (⚠️ deletes all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

## 🚨 Troubleshooting

### Common Issues

1. **Port conflicts**: Change ports in docker-compose.yml
2. **Database connection**: Check DATABASE_URL environment variable
3. **Memory issues**: Increase Docker memory limit
4. **Permission issues**: Ensure volume mounts have correct permissions

### Debug Mode
```bash
# Run with debug output
docker-compose -f docker-compose.dev.yml up

# Access container shell
docker-compose exec web sh
docker-compose exec celery-worker sh
```

### Check Service Status
```bash
# Check all services
docker-compose ps

# Check specific service
docker-compose ps web

# View service logs
docker-compose logs web --tail=50
```

## 🌐 Production Deployment

### Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml thesis-crawler

# Check services
docker stack services thesis-crawler
```

### Environment Variables for Production

Create `docker-compose.override.yml` for production:

```yaml
version: '3.8'
services:
  web:
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-production-secret
    restart: unless-stopped
  
  celery-worker:
    restart: unless-stopped
  
  celery-beat:
    restart: unless-stopped
```

## 📊 Performance Tuning

### Resource Limits
Add to docker-compose.yml services:

```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
  
  celery-worker:
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
```