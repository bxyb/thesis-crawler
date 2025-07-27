"""
Social media trend detection for academic papers.
Supports X (Twitter), Reddit, Hugging Face, and Zhihu.
"""

import asyncio
import httpx
import tweepy
import praw
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import json
import re
from bs4 import BeautifulSoup


@dataclass
class SocialMention:
    """Social media mention data."""
    platform: str
    content: str
    author: str
    timestamp: datetime
    url: str
    engagement_score: float  # likes, retweets, upvotes, etc.
    paper_mentions: List[str]  # arXiv IDs mentioned
    topic_keywords: List[str]


class XTrendDetector:
    """X (Twitter) trend detection."""
    
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        self.api = tweepy.API(auth)
        self.logger = logging.getLogger(__name__)
    
    def search_paper_mentions(self, arxiv_id: str, days_back: int = 7) -> List[SocialMention]:
        """Search for mentions of specific arXiv paper."""
        query = f"arxiv.org/abs/{arxiv_id} OR arxiv.org/pdf/{arxiv_id}"
        
        mentions = []
        try:
            tweets = tweepy.Cursor(
                self.api.search_tweets,
                q=query,
                tweet_mode='extended',
                result_type='recent'
            ).items(100)
            
            for tweet in tweets:
                if datetime.now() - tweet.created_at < timedelta(days=days_back):
                    mentions.append(SocialMention(
                        platform="x",
                        content=tweet.full_text,
                        author=tweet.user.screen_name,
                        timestamp=tweet.created_at,
                        url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}",
                        engagement_score=tweet.favorite_count + tweet.retweet_count * 2,
                        paper_mentions=[arxiv_id],
                        topic_keywords=self._extract_keywords(tweet.full_text)
                    ))
        
        except Exception as e:
            self.logger.error(f"Error searching X: {e}")
        
        return mentions
    
    def search_trending_topics(self, topics: List[str], days_back: int = 3) -> List[SocialMention]:
        """Search for trending discussions about topics."""
        mentions = []
        
        for topic in topics:
            query = f'"{topic}" ("paper" OR "arxiv" OR "research" OR "study")'
            
            try:
                tweets = tweepy.Cursor(
                    self.api.search_tweets,
                    q=query,
                    tweet_mode='extended',
                    result_type='popular'
                ).items(50)
                
                for tweet in tweets:
                    if datetime.now() - tweet.created_at < timedelta(days=days_back):
                        mentions.append(SocialMention(
                            platform="x",
                            content=tweet.full_text,
                            author=tweet.user.screen_name,
                            timestamp=tweet.created_at,
                            url=f"https://twitter.com/{tweet.user.screen_name}/status/{tweet.id}",
                            engagement_score=tweet.favorite_count + tweet.retweet_count * 2,
                            paper_mentions=self._extract_arxiv_ids(tweet.full_text),
                            topic_keywords=[topic]
                        ))
            
            except Exception as e:
                self.logger.error(f"Error searching X for topic {topic}: {e}")
        
        return mentions
    
    def _extract_arxiv_ids(self, text: str) -> List[str]:
        """Extract arXiv IDs from text."""
        pattern = r'arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)'
        return re.findall(pattern, text, re.IGNORECASE)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract research keywords from text."""
        # Simple keyword extraction - could be enhanced with NLP
        keywords = ["LLM", "transformer", "GPT", "BERT", "diffusion", "RL", "CV", "NLP"]
        found = [kw for kw in keywords if kw.lower() in text.lower()]
        return found[:5]


class RedditTrendDetector:
    """Reddit trend detection."""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.logger = logging.getLogger(__name__)
    
    def search_paper_mentions(self, arxiv_id: str, days_back: int = 7) -> List[SocialMention]:
        """Search Reddit for paper mentions."""
        mentions = []
        
        try:
            # Search relevant subreddits
            subreddits = ["MachineLearning", "artificial", "singularity", "ChatGPT", "LocalLLaMA"]
            
            for subreddit_name in subreddits:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Search submissions
                for submission in subreddit.search(f"arxiv {arxiv_id}", time_filter='week', limit=50):
                    mentions.append(SocialMention(
                        platform="reddit",
                        content=submission.title + " " + submission.selftext,
                        author=submission.author.name if submission.author else "unknown",
                        timestamp=datetime.fromtimestamp(submission.created_utc),
                        url=f"https://reddit.com{submission.permalink}",
                        engagement_score=submission.score + submission.num_comments * 2,
                        paper_mentions=[arxiv_id],
                        topic_keywords=self._extract_keywords(submission.title + " " + submission.selftext)
                    ))
                
                # Search comments
                for comment in subreddit.comments(limit=100):
                    if arxiv_id in comment.body:
                        mentions.append(SocialMention(
                            platform="reddit",
                            content=comment.body,
                            author=comment.author.name if comment.author else "unknown",
                            timestamp=datetime.fromtimestamp(comment.created_utc),
                            url=f"https://reddit.com{comment.permalink}",
                            engagement_score=comment.score,
                            paper_mentions=[arxiv_id],
                            topic_keywords=self._extract_keywords(comment.body)
                        ))
        
        except Exception as e:
            self.logger.error(f"Error searching Reddit: {e}")
        
        return mentions
    
    def search_trending_topics(self, topics: List[str], days_back: int = 3) -> List[SocialMention]:
        """Search Reddit for trending topic discussions."""
        mentions = []
        
        try:
            subreddits = ["MachineLearning", "artificial", "singularity", "ChatGPT"]
            
            for subreddit_name in subreddits:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                for topic in topics:
                    for submission in subreddit.search(topic, time_filter='day', limit=20):
                        mentions.append(SocialMention(
                            platform="reddit",
                            content=submission.title + " " + submission.selftext,
                            author=submission.author.name if submission.author else "unknown",
                            timestamp=datetime.fromtimestamp(submission.created_utc),
                            url=f"https://reddit.com{submission.permalink}",
                            engagement_score=submission.score + submission.num_comments * 2,
                            paper_mentions=self._extract_arxiv_ids(submission.selftext),
                            topic_keywords=[topic]
                        ))
        
        except Exception as e:
            self.logger.error(f"Error searching Reddit for topics: {e}")
        
        return mentions
    
    def _extract_arxiv_ids(self, text: str) -> List[str]:
        """Extract arXiv IDs from text."""
        pattern = r'arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)'
        return re.findall(pattern, text, re.IGNORECASE)
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract research keywords from text."""
        keywords = ["LLM", "transformer", "GPT", "BERT", "diffusion", "RL", "CV", "NLP"]
        found = [kw for kw in keywords if kw.lower() in text.lower()]
        return found[:5]


class HuggingFaceTrendDetector:
    """Hugging Face trend detection."""
    
    def __init__(self):
        self.base_url = "https://huggingface.co"
        self.logger = logging.getLogger(__name__)
    
    async def get_trending_models(self, topics: List[str]) -> List[SocialMention]:
        """Get trending models on Hugging Face related to topics."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/api/models")
                data = response.json()
                
                mentions = []
                for model in data[:50]:  # Top 50 models
                    model_id = model.get("id", "")
                    model_name = model.get("modelId", "")
                    
                    # Check if related to topics
                    model_text = f"{model_id} {model_name} {model.get('tags', [])}"
                    
                    for topic in topics:
                        if topic.lower() in model_text.lower():
                            mentions.append(SocialMention(
                                platform="huggingface",
                                content=f"Model: {model_name}",
                                author=model.get("author", "unknown"),
                                timestamp=datetime.now(),
                                url=f"{self.base_url}/{model_name}",
                                engagement_score=model.get("downloads", 0),
                                paper_mentions=self._extract_arxiv_ids(str(model)),
                                topic_keywords=[topic]
                            ))
                            break
                
                return mentions
            
            except Exception as e:
                self.logger.error(f"Error accessing Hugging Face: {e}")
                return []
    
    def _extract_arxiv_ids(self, text: str) -> List[str]:
        """Extract arXiv IDs from text."""
        pattern = r'arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)'
        return re.findall(pattern, text, re.IGNORECASE)


class ZhihuTrendDetector:
    """Zhihu trend detection."""
    
    def __init__(self):
        self.base_url = "https://www.zhihu.com"
        self.logger = logging.getLogger(__name__)
    
    async def search_trending_topics(self, topics: List[str]) -> List[SocialMention]:
        """Search Zhihu for trending topics."""
        # Note: This is a simplified implementation
        # Zhihu requires special handling due to anti-bot measures
        
        mentions = []
        
        # For now, return mock data with structure
        # In production, would need proper Zhihu API or web scraping
        for topic in topics:
            mentions.append(SocialMention(
                platform="zhihu",
                content=f"知乎上关于{topic}的热门讨论",
                author="知乎用户",
                timestamp=datetime.now(),
                url=f"{self.base_url}/search?type=content&q={topic}",
                engagement_score=100,  # Mock score
                paper_mentions=[],  # Would extract from actual content
                topic_keywords=[topic]
            ))
        
        return mentions


class SocialTrendAggregator:
    """Aggregate trends from multiple social platforms."""
    
    def __init__(self, config: Dict):
        self.detectors = {}
        
        # Initialize detectors based on config
        if "x" in config:
            self.detectors["x"] = XTrendDetector(**config["x"])
        
        if "reddit" in config:
            self.detectors["reddit"] = RedditTrendDetector(**config["reddit"])
        
        if "huggingface" in config:
            self.detectors["huggingface"] = HuggingFaceTrendDetector()
        
        if "zhihu" in config:
            self.detectors["zhihu"] = ZhihuTrendDetector()
        
        self.logger = logging.getLogger(__name__)
    
    async def get_paper_trends(self, arxiv_id: str, days_back: int = 7) -> Dict[str, List[SocialMention]]:
        """Get social media trends for a specific paper."""
        trends = {}
        
        for platform, detector in self.detectors.items():
            try:
                if platform == "x":
                    trends[platform] = detector.search_paper_mentions(arxiv_id, days_back)
                elif platform == "reddit":
                    trends[platform] = detector.search_paper_mentions(arxiv_id, days_back)
                elif platform in ["huggingface", "zhihu"]:
                    # Async operations
                    if hasattr(detector, 'get_trending_models'):
                        trends[platform] = await detector.get_trending_models([arxiv_id])
                    else:
                        trends[platform] = await detector.search_trending_topics([arxiv_id])
            except Exception as e:
                self.logger.error(f"Error getting trends from {platform}: {e}")
                trends[platform] = []
        
        return trends
    
    async def get_topic_trends(self, topics: List[str], days_back: int = 3) -> Dict[str, List[SocialMention]]:
        """Get social media trends for topics."""
        trends = {}
        
        for platform, detector in self.detectors.items():
            try:
                if platform == "x":
                    trends[platform] = detector.search_trending_topics(topics, days_back)
                elif platform == "reddit":
                    trends[platform] = detector.search_trending_topics(topics, days_back)
                elif platform == "huggingface":
                    trends[platform] = await detector.get_trending_models(topics)
                elif platform == "zhihu":
                    trends[platform] = await detector.search_trending_topics(topics)
            except Exception as e:
                self.logger.error(f"Error getting topic trends from {platform}: {e}")
                trends[platform] = []
        
        return trends
    
    def calculate_hot_score(self, mentions: Dict[str, List[SocialMention]]) -> float:
        """Calculate overall hot score from all platforms."""
        total_score = 0
        total_mentions = 0
        
        for platform_mentions in mentions.values():
            for mention in platform_mentions:
                # Normalize engagement scores per platform
                if mention.platform == "x":
                    normalized_score = min(mention.engagement_score / 1000, 1.0)
                elif mention.platform == "reddit":
                    normalized_score = min(mention.engagement_score / 500, 1.0)
                elif mention.platform == "huggingface":
                    normalized_score = min(mention.engagement_score / 10000, 1.0)
                elif mention.platform == "zhihu":
                    normalized_score = min(mention.engagement_score / 100, 1.0)
                else:
                    normalized_score = 0.5
                
                total_score += normalized_score
                total_mentions += 1
        
        if total_mentions == 0:
            return 0.0
        
        return min(total_score * 100, 100.0)  # Scale to 0-100


# Example usage
if __name__ == "__main__":
    async def main():
        config = {
            "x": {
                "api_key": "your_x_api_key",
                "api_secret": "your_x_api_secret",
                "access_token": "your_access_token",
                "access_token_secret": "your_access_token_secret"
            },
            "reddit": {
                "client_id": "your_reddit_client_id",
                "client_secret": "your_reddit_client_secret",
                "user_agent": "ThesisCrawler/1.0"
            }
        }
        
        aggregator = SocialTrendAggregator(config)
        
        # Example: Get trends for LLM topic
        topics = ["large language model", "transformer", "GPT"]
        trends = await aggregator.get_topic_trends(topics)
        
        for platform, mentions in trends.items():
            print(f"\n{platform.upper()} mentions: {len(mentions)}")
            for mention in mentions[:3]:
                print(f"  - {mention.content[:100]}...")
    
    asyncio.run(main())