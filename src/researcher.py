"""Web research functionality for Web Researcher Agent."""

import json
from typing import List, Dict, Any, Optional, TypedDict, Union, cast
from datetime import datetime, timedelta

from anthropic import Anthropic

from src.utils import (
    fetch_url_content,
    is_valid_url,
    chunk_text,
)
from src.config import ResearchConfig


class CacheEntry(TypedDict):
    """Type definition for cache entry structure."""

    value: Any
    expires: datetime


class SearchResult(TypedDict):
    """Type definition for search result from search method."""

    url: str
    title: str


class FetchAndSummarizeSuccess(TypedDict):
    """Type definition for successful fetch_and_summarize result."""

    url: str
    status: str
    summary: str
    content_preview: str


class FetchAndSummarizeError(TypedDict):
    """Type definition for error fetch_and_summarize result."""

    url: str
    error: str
    status: str


FetchAndSummarizeResult = Union[FetchAndSummarizeSuccess, FetchAndSummarizeError]


class ResearchTopicSuccess(TypedDict):
    """Type definition for successful research_topic result."""

    topic: str
    status: str
    findings: List[Dict[str, Any]]
    analysis: str
    sources: List[str]
    timestamp: str


class ResearchTopicError(TypedDict):
    """Type definition for error research_topic result."""

    topic: str
    status: str
    error: str


ResearchTopicResult = Union[ResearchTopicSuccess, ResearchTopicError]


class ContentCache:
    """Simple in-memory cache for web content with TTL-based expiration.

    Stores key-value pairs with automatic expiration after a specified time-to-live (TTL).
    Items expire when the current time reaches or exceeds their expiration time.
    Expired items are lazily deleted when accessed, or can be proactively removed with cleanup().

    Note: None is reserved as the cache-miss sentinel value and cannot be cached.
    Use cleanup() periodically in long-running applications to prevent memory bloat.
    """

    def __init__(self, ttl: int = 3600) -> None:
        """Initialize cache with time-to-live.

        Args:
            ttl: Time-to-live in seconds (must be non-negative)

        Raises:
            TypeError: If ttl is not an integer (bool is rejected as bool is a subclass of int)
            ValueError: If ttl is negative
        """
        if type(ttl) is not int or isinstance(ttl, bool):
            raise TypeError(f"ttl must be an integer, got {type(ttl).__name__}")
        if ttl < 0:
            raise ValueError("ttl must be non-negative")
        self.ttl = ttl
        self.cache: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        """Retrieve item from cache if not expired.

        Args:
            key: The cache key to retrieve.

        Returns:
            The cached value if the key exists and has not expired, None otherwise.
            Expired items are automatically deleted from the cache dict when accessed.
            Items are valid only when current time < expiration time; they expire
            when current time >= expiration time.
        """
        if key in self.cache:
            item = self.cache[key]
            if datetime.now() < item["expires"]:
                return item["value"]
            else:
                del self.cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Store item in cache with expiration.

        Args:
            key: The cache key to store the value under. If the key already exists,
                 its value and expiration time are updated (TTL is reset to now + ttl).
            value: The value to cache (any type except None; falsy values like 0, False, "" are OK).

        Raises:
            ValueError: If value is None (None is reserved as cache-miss sentinel).

        Returns:
            None. The item is added to the cache and will expire after ttl seconds.
        """
        if value is None:
            raise ValueError("Cannot cache None values; None is reserved for cache-miss semantics")
        self.cache[key] = {
            "value": value,
            "expires": datetime.now() + timedelta(seconds=self.ttl),
        }

    def cleanup(self) -> int:
        """Remove all expired entries from the cache.

        Proactively removes entries where the current time is at or beyond the
        expiration time (uses >= comparison with expiration boundary).
        Prevents memory bloat in long-running applications.

        Returns:
            The number of expired entries that were removed.
        """
        expired_keys = [
            key for key, item in self.cache.items()
            if datetime.now() >= item["expires"]
        ]
        for key in expired_keys:
            del self.cache[key]
        return len(expired_keys)

    def clear(self) -> None:
        """Clear all cache entries.

        Removes all cached items from the cache dict.
        This is useful for resetting the cache state.
        """
        self.cache.clear()


class WebResearcher:
    """Web researcher that conducts research using Claude AI."""

    def __init__(self, config: ResearchConfig) -> None:
        """Initialize researcher with configuration.

        Args:
            config: ResearchConfig instance containing API key, model, and operational parameters.

        Attributes:
            config: ResearchConfig instance for accessing API key, model, and settings.
            client: Anthropic API client for making requests to Claude.
            cache: ContentCache instance for caching fetched URLs and summaries. Created only if
                   config.cache_enabled is True; otherwise None.
            sources: List of URLs that have been successfully processed during research.
            research_history: List of research results from all completed research() calls.
        """
        self.config: ResearchConfig = config
        self.client: Anthropic = Anthropic()
        self.cache: Optional[ContentCache] = ContentCache(ttl=config.cache_ttl) if config.cache_enabled else None
        self.sources: List[str] = []
        self.research_history: List[ResearchTopicResult] = []

    def search(
        self,
        query: str,
        num_results: int = 5,
    ) -> List[SearchResult]:
        """Perform web search using Claude's knowledge.

        Generates relevant search results by prompting Claude to produce realistic URLs
        based on its training data. Note: This uses Claude's knowledge rather than
        real-time web search; for live results, integrate with a search API.

        Args:
            query: The search query string to find results for (must be non-empty string).
            num_results: Number of search results to generate (default: 5, must be positive).

        Returns:
            A list of SearchResult dicts, each containing 'url' and 'title' keys.
            Returns an empty list if JSON parsing fails or no results could be generated.

        Raises:
            TypeError: If query is not a string or num_results is not an integer.
            ValueError: If query is empty or num_results is not positive.
        """
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}")
        if not query.strip():
            raise ValueError("query cannot be empty")
        if type(num_results) is not int or isinstance(num_results, bool) or num_results <= 0:
            raise ValueError(f"num_results must be a positive integer, got {num_results}")
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
            return cast(List[SearchResult], results) if isinstance(results, list) else []
        except (json.JSONDecodeError, IndexError, TypeError):
            return []

    def fetch_and_summarize(
        self,
        url: str,
    ) -> FetchAndSummarizeResult:
        """Fetch URL content and generate a summary using Claude.

        Validates the URL, fetches its content, extracts clean text, and
        generates a concise summary. Only successful results are cached if
        caching is enabled; errors are not cached to allow retries.
        The URL is added to the sources list on successful fetch.

        Args:
            url: The URL to fetch and summarize (must be a valid HTTP(S) URL).

        Returns:
            On success (status == "success"):
                - url: The requested URL
                - status: "success"
                - summary: Concise summary of the URL content
                - content_preview: First 500 characters of extracted content
            On error (status == "error"), returns a dict with:
                - url: The requested URL
                - status: "error"
                - error: Error message describing what went wrong
        """
        if not is_valid_url(url):
            error_result: FetchAndSummarizeError = {"error": f"Invalid URL: {url}", "url": url, "status": "error"}
            return error_result

        # Check cache
        if self.cache:
            cached = self.cache.get(url)
            if cached is not None:
                return cast(FetchAndSummarizeResult, cached)

        # Fetch content
        fetch_result = fetch_url_content(url, timeout=self.config.timeout)

        if fetch_result["status"] == "error":
            error_result: FetchAndSummarizeError = {
                "url": fetch_result["url"],
                "error": fetch_result["error"],
                "status": "error",
            }
            return error_result

        content = fetch_result.get("content", "")
        if not content:
            no_content_error: FetchAndSummarizeError = {"error": "No content extracted", "url": url, "status": "error"}
            return no_content_error

        # Summarize content
        summary = self._summarize_content(content)

        result: FetchAndSummarizeSuccess = {
            "url": url,
            "status": "success",
            "summary": summary,
            "content_preview": content[:500],
        }

        # Cache result
        if self.cache:
            self.cache.set(url, result)

        if url not in self.sources:
            self.sources.append(url)

        return result

    def _summarize_content(self, content: str) -> str:
        """Summarize content using Claude.

        Splits content into chunks (size 3000 characters, 100 character overlap) and
        summarizes each of the first 3 chunks. Returns a space-joined
        concatenation of all chunk summaries.

        Args:
            content: The text content to summarize (will be chunked if too long).

        Returns:
            A concatenated summary of up to 3 chunks separated by spaces.
            Returns empty string if no chunks are available or Claude
            returns no content for all chunks.
        """
        # Chunk content if too long
        chunks = chunk_text(content, chunk_size=3000)

        summaries: List[str] = []
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
    ) -> ResearchTopicResult:
        """Conduct comprehensive research on a topic.

        Args:
            topic: The research topic to investigate (must be non-empty string).
            num_sources: Number of sources to fetch (default: 5, must be positive).

        Returns:
            Dictionary containing:
            - topic: The research topic
            - status: "success" or "error"
            - findings: List of results from each source (each has summary on success or error message on failure)
            - analysis: Comprehensive analysis of findings
            - sources: List of URLs used
            - timestamp: When research was conducted

        Raises:
            TypeError: If topic is not a string or num_sources is not an integer.
            ValueError: If topic is empty or num_sources is not positive.
        """
        if not isinstance(topic, str):
            raise TypeError(f"topic must be a string, got {type(topic).__name__}")
        if not topic.strip():
            raise ValueError("topic cannot be empty")
        if type(num_sources) is not int or isinstance(num_sources, bool) or num_sources <= 0:
            raise ValueError(f"num_sources must be a positive integer, got {num_sources}")

        # Generate search queries
        search_results = self.search(topic, num_results=num_sources)

        if not search_results:
            error_result: ResearchTopicError = {
                "topic": topic,
                "status": "error",
                "error": "No search results found",
            }
            return error_result

        # Fetch and summarize each result
        findings: List[Dict[str, Any]] = []
        for result in search_results:
            url = result.get("url")
            if url:
                summary = self.fetch_and_summarize(url)
                findings.append(summary)

        # Generate comprehensive analysis
        analysis = self._generate_analysis(topic, findings)

        research_result: ResearchTopicSuccess = {
            "topic": topic,
            "status": "success",
            "findings": findings,
            "analysis": analysis,
            "sources": self.sources,
            "timestamp": datetime.now().isoformat(),
        }

        self.research_history.append(research_result)
        return research_result

    def _generate_analysis(self, topic: str, findings: List[Dict[str, Any]]) -> str:
        """Generate comprehensive analysis from findings.

        Args:
            topic: The research topic being analyzed
            findings: List of findings dictionaries from sources

        Returns:
            A comprehensive analysis including key insights, trends, and takeaways
        """
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
        """Get list of all sources successfully fetched.

        Returns all URLs that have been successfully fetched since the researcher
        was created or clear_history() was last called. Sources accumulate across
        multiple fetch_and_summarize() and research_topic() calls.

        Returns:
            List of URLs from all successful fetch operations.
        """
        return self.sources

    def clear_history(self) -> None:
        """Clear research history and cache.

        Resets all accumulated state from prior research_topic() and fetch_and_summarize() calls.
        Specifically:
        - Clears research_history list, removing all completed research results
        - Clears sources list, removing all fetched URLs
        - Clears the cache if caching is enabled (no effect if cache_enabled is False)

        Side effects: After calling, get_sources() returns an empty list. Research results
        obtained before the call are no longer retained in the researcher.
        """
        self.research_history.clear()
        self.sources.clear()
        if self.cache:
            self.cache.clear()
