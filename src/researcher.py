"""Web research functionality for Web Researcher Agent."""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from anthropic import Anthropic

from src.utils import (
    fetch_url_content,
    is_valid_url,
    hash_content,
    chunk_text,
)
from src.config import ResearchConfig


class ContentCache:
    """Simple in-memory cache for web content."""

    def __init__(self, ttl: int = 3600):
        """Initialize cache with time-to-live."""
        self.ttl = ttl
        self.cache: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item from cache if not expired."""
        if key in self.cache:
            item = self.cache[key]
            if datetime.now() < item["expires"]:
                return item["value"]
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Store item in cache with expiration."""
        self.cache[key] = {
            "value": value,
            "expires": datetime.now() + timedelta(seconds=self.ttl),
        }

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()


class WebResearcher:
    """Web researcher that conducts research using Claude AI."""

    def __init__(self, config: ResearchConfig):
        """Initialize researcher with configuration."""
        self.config = config
        self.client = Anthropic()
        self.cache = ContentCache(ttl=config.cache_ttl) if config.cache_enabled else None
        self.sources: List[str] = []
        self.research_history: List[Dict[str, Any]] = []

    def search(
        self,
        query: str,
        num_results: int = 5,
    ) -> List[Dict[str, str]]:
        """
        Perform web search using Claude's knowledge.

        Note: This uses Claude to generate search results based on its training data.
        For real-time web search, you would integrate with a search API.
        """
        prompt = f"""Generate {num_results} relevant URLs for the following search query:
        
Query: {query}

Return a JSON list of URLs. Each URL should be realistic and relevant to the query.
Format: [{"url": "https://...", "title": "..."}, ...]

Only return the JSON list, no other text."""

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )

        try:
            content = response.content[0].text
            # Parse JSON from response
            results = json.loads(content)
            return results if isinstance(results, list) else []
        except (json.JSONDecodeError, IndexError, TypeError):
            return []

    def fetch_and_summarize(
        self,
        url: str,
    ) -> Dict[str, Any]:
        """Fetch URL content and summarize using Claude."""
        if not is_valid_url(url):
            return {"error": f"Invalid URL: {url}", "url": url}

        # Check cache
        if self.cache:
            cached = self.cache.get(hash_content(url))
            if cached:
                return cached

        # Fetch content
        fetch_result = fetch_url_content(url, timeout=self.config.timeout)

        if fetch_result["status"] == "error":
            return fetch_result

        content = fetch_result.get("content", "")
        if not content:
            return {"error": "No content extracted", "url": url}

        # Summarize content
        summary = self._summarize_content(content)

        result = {
            "url": url,
            "status": "success",
            "summary": summary,
            "content_preview": content[:500],
        }

        # Cache result
        if self.cache:
            self.cache.set(hash_content(url), result)

        if url not in self.sources:
            self.sources.append(url)

        return result

    def _summarize_content(self, content: str) -> str:
        """Summarize content using Claude."""
        # Chunk content if too long
        chunks = chunk_text(content, chunk_size=3000)

        summaries = []
        for chunk in chunks[:3]:  # Limit to first 3 chunks
            prompt = f"""Please provide a concise summary of the following content:

{chunk}

Summary should be 2-3 sentences max."""

            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            if response.content:
                summaries.append(response.content[0].text)

        return " ".join(summaries)

    def research_topic(
        self,
        topic: str,
        num_sources: int = 5,
    ) -> Dict[str, Any]:
        """Conduct comprehensive research on a topic."""
        print(f"Starting research on: {topic}")

        # Generate search queries
        search_results = self.search(topic, num_results=num_sources)

        if not search_results:
            return {
                "topic": topic,
                "status": "error",
                "error": "No search results found",
            }

        # Fetch and summarize each result
        findings = []
        for result in search_results:
            url = result.get("url")
            if url:
                summary = self.fetch_and_summarize(url)
                findings.append(summary)
                print(f"  ✓ Processed: {url}")

        # Generate comprehensive analysis
        analysis = self._generate_analysis(topic, findings)

        research_result = {
            "topic": topic,
            "status": "success",
            "findings": findings,
            "analysis": analysis,
            "sources": self.sources,
            "timestamp": datetime.now().isoformat(),
        }

        self.research_history.append(research_result)
        return research_result

    def _generate_analysis(self, topic: str, findings: List[Dict]) -> str:
        """Generate comprehensive analysis from findings."""
        summaries = [
            f.get("summary", f.get("error", ""))
            for f in findings
            if f.get("status") == "success"
        ]

        if not summaries:
            return "Unable to generate analysis from available findings."

        combined_text = "\n\n".join(summaries)

        prompt = f"""Based on the following research findings about "{topic}", provide a comprehensive analysis:

{combined_text}

Please provide:
1. Key insights and trends
2. Main takeaways
3. Important considerations"""

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.content[0].text if response.content else ""

    def get_sources(self) -> List[str]:
        """Get list of sources used in research."""
        return self.sources

    def clear_history(self) -> None:
        """Clear research history and cache."""
        self.research_history.clear()
        self.sources.clear()
        if self.cache:
            self.cache.clear()
