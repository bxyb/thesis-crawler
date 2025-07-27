"""
Thesis Crawler - Main crawler module
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional


class ThesisCrawler:
    """Main crawler class for academic paper collection."""
    
    def __init__(self, base_url: str, delay: float = 1.0):
        """
        Initialize the crawler.
        
        Args:
            base_url: Base URL to crawl
            delay: Delay between requests in seconds
        """
        self.base_url = base_url
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ThesisCrawler/1.0 (Academic Research)'
        })
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page and return its content."""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            time.sleep(self.delay)
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"Error fetching {url}: {e}")
            return None
    
    def parse_page(self, html: str) -> Dict:
        """Parse HTML content and extract relevant data."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Basic structure - to be customized based on target site
        return {
            'title': soup.find('title').text if soup.find('title') else '',
            'links': [a.get('href') for a in soup.find_all('a', href=True)],
            'text': soup.get_text(),
            'timestamp': time.time()
        }
    
    def crawl(self, start_url: str, max_pages: int = 100) -> List[Dict]:
        """
        Crawl pages starting from the given URL.
        
        Args:
            start_url: Starting URL for crawling
            max_pages: Maximum number of pages to crawl
            
        Returns:
            List of extracted data from crawled pages
        """
        results = []
        visited = set()
        to_visit = [start_url]
        
        while to_visit and len(visited) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue
                
            self.logger.info(f"Crawling: {url}")
            html = self.fetch_page(url)
            
            if html:
                data = self.parse_page(html)
                data['url'] = url
                results.append(data)
                visited.add(url)
                
                # Add new links to crawl queue
                # This is a basic implementation - customize as needed
                for link in data.get('links', []):
                    if link.startswith('http') and link not in visited:
                        to_visit.append(link)
        
        return results


if __name__ == "__main__":
    # Example usage
    crawler = ThesisCrawler("https://example.com")
    results = crawler.crawl("https://example.com", max_pages=5)
    print(f"Crawled {len(results)} pages")