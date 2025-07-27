"""
arXiv paper crawler with topic filtering and date-based retrieval.
"""

import arxiv
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class ArxivPaper:
    """arXiv paper data structure."""
    id: str
    title: str
    abstract: str
    authors: List[str]
    categories: List[str]
    published: datetime
    updated: datetime
    pdf_url: str
    entry_url: str
    primary_category: str


class ArxivCrawler:
    """Crawler for arXiv papers with topic filtering."""
    
    def __init__(self):
        self.client = arxiv.Client()
        self.logger = logging.getLogger(__name__)
    
    def search_papers(
        self,
        topics: List[str],
        max_results: int = 100,
        days_back: int = 7,
        categories: Optional[List[str]] = None
    ) -> List[ArxivPaper]:
        """
        Search arXiv papers by topics.
        
        Args:
            topics: List of topics to search for
            max_results: Maximum number of results
            days_back: Number of days back to search
            categories: arXiv categories to search in (e.g., cs.AI, cs.LG, cs.CL)
        
        Returns:
            List of ArxivPaper objects
        """
        if categories is None:
            categories = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.CY"]
        
        # Build search query
        topic_query = " OR ".join([f'"{topic}"' for topic in topics])
        category_query = " OR ".join([f"cat:{cat}" for cat in categories])
        
        query = f"({topic_query}) AND ({category_query})"
        
        # Date filter
        start_date = datetime.now() - timedelta(days=days_back)
        
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        for result in self.client.results(search):
            if result.published.date() < start_date.date():
                break
                
            paper = ArxivPaper(
                id=result.entry_id.split("/")[-1],
                title=result.title,
                abstract=result.summary,
                authors=[author.name for author in result.authors],
                categories=result.categories,
                published=result.published,
                updated=result.updated,
                pdf_url=result.pdf_url,
                entry_url=result.entry_id,
                primary_category=result.primary_category
            )
            papers.append(paper)
        
        self.logger.info(f"Found {len(papers)} papers for topics: {topics}")
        return papers
    
    def get_trending_papers(
        self,
        topics: List[str],
        days_back: int = 3,
        min_score: float = 0.0
    ) -> List[Dict]:
        """
        Get trending papers based on topics and recency.
        
        Args:
            topics: List of trending topics
            days_back: Days to look back
            min_score: Minimum relevance score
        
        Returns:
            List of papers with trending information
        """
        papers = self.search_papers(topics, days_back=days_back)
        
        # Calculate trending score based on recency and topic relevance
        trending_papers = []
        for paper in papers:
            # Calculate days since publication
            days_since_pub = (datetime.now().date() - paper.published.date()).days
            
            # Recency score (higher for more recent papers)
            recency_score = max(0, 1 - (days_since_pub / days_back))
            
            # Topic relevance score (based on title/abstract matches)
            title_lower = paper.title.lower()
            abstract_lower = paper.abstract.lower()
            
            topic_matches = 0
            for topic in topics:
                topic_lower = topic.lower()
                if topic_lower in title_lower:
                    topic_matches += 3
                if topic_lower in abstract_lower:
                    topic_matches += 1
            
            relevance_score = min(topic_matches / len(topics), 3.0)
            
            # Combined trending score
            trending_score = (recency_score * 0.7 + relevance_score * 0.3)
            
            if trending_score >= min_score:
                trending_papers.append({
                    "paper": paper,
                    "trending_score": trending_score,
                    "recency_score": recency_score,
                    "relevance_score": relevance_score,
                    "days_since_pub": days_since_pub
                })
        
        # Sort by trending score
        trending_papers.sort(key=lambda x: x["trending_score"], reverse=True)
        
        return trending_papers
    
    def get_papers_by_category(
        self,
        category: str,
        max_results: int = 50,
        days_back: int = 7
    ) -> List[ArxivPaper]:
        """
        Get papers from specific arXiv category.
        
        Args:
            category: arXiv category (e.g., cs.LG, cs.AI)
            max_results: Maximum results
            days_back: Days to look back
        
        Returns:
            List of papers in category
        """
        return self.search_papers(
            topics=["*"],
            max_results=max_results,
            days_back=days_back,
            categories=[category]
        )
    
    def save_papers(self, papers: List[ArxivPaper], filename: str):
        """Save papers to JSON file."""
        data = []
        for paper in papers:
            data.append({
                "id": paper.id,
                "title": paper.title,
                "abstract": paper.abstract,
                "authors": paper.authors,
                "categories": paper.categories,
                "published": paper.published.isoformat(),
                "updated": paper.updated.isoformat(),
                "pdf_url": paper.pdf_url,
                "entry_url": paper.entry_url,
                "primary_category": paper.primary_category
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved {len(papers)} papers to {filename}")
    
    def load_papers(self, filename: str) -> List[ArxivPaper]:
        """Load papers from JSON file."""
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        papers = []
        for item in data:
            paper = ArxivPaper(
                id=item["id"],
                title=item["title"],
                abstract=item["abstract"],
                authors=item["authors"],
                categories=item["categories"],
                published=datetime.fromisoformat(item["published"]),
                updated=datetime.fromisoformat(item["updated"]),
                pdf_url=item["pdf_url"],
                entry_url=item["entry_url"],
                primary_category=item["primary_category"]
            )
            papers.append(paper)
        
        self.logger.info(f"Loaded {len(papers)} papers from {filename}")
        return papers


class TopicManager:
    """Manage dynamic topics for paper monitoring."""
    
    def __init__(self, config_file: str = "config/topics.json"):
        self.config_file = Path(config_file)
        self.topics = self._load_topics()
    
    def _load_topics(self) -> Dict[str, Dict]:
        """Load topics from config file."""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def save_topics(self):
        """Save topics to config file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.topics, f, ensure_ascii=False, indent=2)
    
    def add_topic(self, topic: str, keywords: List[str], categories: Optional[List[str]] = None):
        """Add a new topic to monitor."""
        self.topics[topic] = {
            "keywords": keywords,
            "categories": categories or ["cs.AI", "cs.LG", "cs.CL"],
            "added_date": datetime.now().isoformat(),
            "active": True
        }
        self.save_topics()
    
    def remove_topic(self, topic: str):
        """Remove a topic."""
        if topic in self.topics:
            self.topics[topic]["active"] = False
            self.save_topics()
    
    def get_active_topics(self) -> List[str]:
        """Get list of active topics."""
        return [topic for topic, config in self.topics.items() if config.get("active", True)]
    
    def get_topic_config(self, topic: str) -> Dict:
        """Get configuration for specific topic."""
        return self.topics.get(topic, {})


# Example usage
if __name__ == "__main__":
    # Initialize components
    crawler = ArxivCrawler()
    topic_manager = TopicManager()
    
    # Add some topics
    topic_manager.add_topic("LLM", ["large language model", "transformer", "GPT", "BERT", "fine-tuning"])
    topic_manager.add_topic("Computer Vision", ["computer vision", "CNN", "image classification", "object detection"])
    
    # Get trending papers
    active_topics = topic_manager.get_active_topics()
    print(f"Monitoring topics: {active_topics}")
    
    trending = crawler.get_trending_papers(active_topics, days_back=3)
    
    for paper_data in trending[:5]:
        paper = paper_data["paper"]
        print(f"\nTitle: {paper.title}")
        print(f"Score: {paper_data['trending_score']:.2f}")
        print(f"Published: {paper.published.date()}")
        print(f"Categories: {', '.join(paper.categories)}")