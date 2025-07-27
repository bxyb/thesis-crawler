"""
Paper clustering by topics using embeddings and clustering algorithms.
"""

from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
import logging
from datetime import datetime


@dataclass
class PaperCluster:
    """Represents a cluster of papers."""
    cluster_id: int
    papers: List[Dict]
    keywords: List[str]
    centroid: np.ndarray
    size: int
    avg_novelty: float
    avg_hot_score: float


class TopicClusterer:
    """Cluster papers by topics using embeddings and TF-IDF."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2
        )
        self.logger = logging.getLogger(__name__)
    
    def cluster_papers(
        self,
        papers: List[Dict],
        n_clusters: int = 5,
        method: str = "kmeans"
    ) -> List[PaperCluster]:
        """
        Cluster papers based on their abstracts and titles.
        
        Args:
            papers: List of paper dictionaries with title, abstract, and metadata
            n_clusters: Number of clusters to create
            method: Clustering method ("kmeans" or "hierarchical")
        
        Returns:
            List of PaperCluster objects
        """
        if len(papers) < n_clusters:
            n_clusters = max(1, len(papers))
        
        # Combine title and abstract for clustering
        texts = [f"{p['title']} {p['abstract']}" for p in papers]
        
        # Get embeddings
        embeddings = self.model.encode(texts)
        
        # Perform clustering
        if method == "kmeans":
            clusterer = KMeans(n_clusters=n_clusters, random_state=42)
        else:
            clusterer = AgglomerativeClustering(n_clusters=n_clusters)
        
        cluster_labels = clusterer.fit_predict(embeddings)
        
        # Create clusters
        clusters = []
        for cluster_id in range(n_clusters):
            cluster_papers = [
                paper for paper, label in zip(papers, cluster_labels)
                if label == cluster_id
            ]
            
            if cluster_papers:
                cluster_embeddings = embeddings[cluster_labels == cluster_id]
                centroid = np.mean(cluster_embeddings, axis=0)
                
                # Extract keywords for this cluster
                cluster_texts = [f"{p['title']} {p['abstract']}" for p in cluster_papers]
                keywords = self._extract_cluster_keywords(cluster_texts)
                
                # Calculate average scores
                avg_novelty = np.mean([p.get('llm_analysis', {}).get('novelty_score', 5) 
                                     for p in cluster_papers])
                avg_hot_score = np.mean([p.get('social_trend', {}).get('hot_score', 0) 
                                       for p in cluster_papers])
                
                cluster = PaperCluster(
                    cluster_id=cluster_id,
                    papers=cluster_papers,
                    keywords=keywords,
                    centroid=centroid,
                    size=len(cluster_papers),
                    avg_novelty=avg_novelty,
                    avg_hot_score=avg_hot_score
                )
                clusters.append(cluster)
        
        self.logger.info(f"Created {len(clusters)} clusters from {len(papers)} papers")
        return clusters
    
    def _extract_cluster_keywords(self, texts: List[str]) -> List[str]:
        """Extract top keywords for a cluster."""
        if not texts:
            return []
        
        tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
        feature_names = self.tfidf_vectorizer.get_feature_names_out()
        
        # Get top keywords by TF-IDF score
        scores = np.array(tfidf_matrix.sum(axis=0)).flatten()
        top_indices = scores.argsort()[-10:][::-1]
        keywords = [feature_names[i] for i in top_indices]
        
        # Filter out generic terms
        keywords = [kw for kw in keywords if len(kw) > 3 and not kw.isdigit()]
        return keywords[:5]
    
    def find_similar_papers(
        self,
        target_paper: Dict,
        all_papers: List[Dict],
        top_k: int = 5
    ) -> List[Tuple[Dict, float]]:
        """
        Find papers similar to a target paper.
        
        Args:
            target_paper: The paper to find similarities for
            all_papers: List of papers to search from
            top_k: Number of similar papers to return
        
        Returns:
            List of (paper, similarity_score) tuples
        """
        target_text = f"{target_paper['title']} {target_paper['abstract']}"
        all_texts = [f"{p['title']} {p['abstract']}" for p in all_papers]
        
        # Get embeddings
        target_embedding = self.model.encode([target_text])[0]
        all_embeddings = self.model.encode(all_texts)
        
        # Calculate similarities
        similarities = []
        for paper, embedding in zip(all_papers, all_embeddings):
            if paper['id'] != target_paper['id']:  # Exclude the target paper itself
                similarity = np.dot(target_embedding, embedding) / (
                    np.linalg.norm(target_embedding) * np.linalg.norm(embedding)
                )
                similarities.append((paper, similarity))
        
        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]
    
    def analyze_cluster_trends(self, clusters: List[PaperCluster]) -> Dict:
        """Analyze trends within clusters."""
        analysis = {
            "total_clusters": len(clusters),
            "total_papers": sum(c.size for c in clusters),
            "largest_cluster": max(clusters, key=lambda c: c.size).cluster_id if clusters else None,
            "highest_novelty_cluster": max(clusters, key=lambda c: c.avg_novelty).cluster_id if clusters else None,
            "hottest_cluster": max(clusters, key=lambda c: c.avg_hot_score).cluster_id if clusters else None,
            "cluster_summary": []
        }
        
        for cluster in clusters:
            analysis["cluster_summary"].append({
                "cluster_id": cluster.cluster_id,
                "size": cluster.size,
                "keywords": cluster.keywords,
                "avg_novelty": cluster.avg_novelty,
                "avg_hot_score": cluster.avg_hot_score,
                "papers_count": len(cluster.papers)
            })
        
        return analysis


class DynamicTopicDetector:
    """Detect emerging topics from paper clusters."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def detect_emerging_topics(
        self,
        current_clusters: List[PaperCluster],
        historical_clusters: List[PaperCluster],
        threshold: float = 0.1
    ) -> List[Dict]:
        """
        Detect new or growing topics compared to historical data.
        
        Args:
            current_clusters: Current paper clusters
            historical_clusters: Historical paper clusters
            threshold: Growth threshold to consider a topic emerging
        
        Returns:
            List of emerging topic information
        """
        emerging_topics = []
        
        for current_cluster in current_clusters:
            current_keywords = set(current_cluster.keywords)
            
            # Find similar historical clusters
            similar_historical = []
            for historical_cluster in historical_clusters:
                historical_keywords = set(historical_cluster.keywords)
                similarity = len(current_keywords.intersection(historical_keywords)) / \
                           len(current_keywords.union(historical_keywords))
                
                if similarity > 0.3:  
                    similar_historical.append((historical_cluster, similarity))
            
            if not similar_historical:
                # Completely new topic
                emerging_topics.append({
                    "type": "new",
                    "keywords": current_cluster.keywords,
                    "size": current_cluster.size,
                    "avg_novelty": current_cluster.avg_novelty,
                    "avg_hot_score": current_cluster.avg_hot_score
                })
            else:
                # Check growth
                max_size = max(hc[0].size for hc in similar_historical)
                growth_rate = (current_cluster.size - max_size) / max_size if max_size > 0 else 1.0
                
                if growth_rate > threshold:
                    emerging_topics.append({
                        "type": "growing",
                        "keywords": current_cluster.keywords,
                        "size": current_cluster.size,
                        "growth_rate": growth_rate,
                        "avg_novelty": current_cluster.avg_novelty,
                        "avg_hot_score": current_cluster.avg_hot_score
                    })
        
        # Sort by growth rate or size for new topics
        emerging_topics.sort(
            key=lambda x: x.get("growth_rate", 1.0) if x["type"] == "growing" else x["size"],
            reverse=True
        )
        
        return emerging_topics


# Example usage
if __name__ == "__main__":
    # Example papers
    sample_papers = [
        {
            "id": "paper1",
            "title": "Attention Is All You Need",
            "abstract": "We propose a new simple network architecture, the Transformer...",
            "llm_analysis": {"novelty_score": 9.5},
            "social_trend": {"hot_score": 85.0}
        },
        {
            "id": "paper2",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "abstract": "We introduce a new language representation model called BERT...",
            "llm_analysis": {"novelty_score": 8.5},
            "social_trend": {"hot_score": 75.0}
        }
    ]
    
    clusterer = TopicClusterer()
    clusters = clusterer.cluster_papers(sample_papers, n_clusters=2)
    
    for cluster in clusters:
        print(f"Cluster {cluster.cluster_id}: {cluster.keywords}")
        print(f"  Size: {cluster.size}, Avg Novelty: {cluster.avg_novelty}")
        print(f"  Avg Hot Score: {cluster.avg_hot_score}")
        print()