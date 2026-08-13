"""Main agent for Web Researcher Agent."""

from typing import Dict, Any, List, Optional, TypedDict

from src.config import ResearchConfig
from src.researcher import WebResearcher
from src.utils import format_sources, is_valid_url


class SummarizeResult(TypedDict):
    """Type definition for summarize method result."""

    status: str
    summaries: Dict[str, Dict[str, Any]]
    sources_count: int


class ResearchAgent:
    """High-level agent for conducting research."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_search_results: int = 10,
        max_depth: int = 3,
        **kwargs,
    ) -> None:
        """Initialize research agent with configuration.

        Args:
            api_key: Anthropic API key. If not provided, loads from ANTHROPIC_API_KEY env var.
            model: Claude model to use for research (default: claude-3-5-sonnet-20241022).
            max_search_results: Maximum number of search results to fetch per query (default: 10).
            max_depth: Reserved for future use (default: 3).
            **kwargs: Additional arguments passed to ResearchConfig (e.g., timeout, cache_ttl).
        """
        if api_key:
            config = ResearchConfig.with_api_key(
                api_key,
                model=model,
                max_search_results=max_search_results,
                max_depth=max_depth,
                **kwargs,
            )
        else:
            config = ResearchConfig.from_env()

        self.config: ResearchConfig = config
        self.researcher: WebResearcher = WebResearcher(config)
        self.last_research: Optional[Dict[str, Any]] = None

    def research(
        self,
        topic: str,
        num_sources: int = 5,
    ) -> Dict[str, Any]:
        """Conduct research on a topic.

        Args:
            topic: The topic to research
            num_sources: Number of sources to fetch (default: 5). Must be a positive integer.
                If greater than max_search_results, will be clamped to max_search_results.

        Returns:
            Dictionary with topic and status ("success" or "error").
            On success, also includes: findings (list of results), analysis, sources (list of URLs),
            timestamp. On error, includes error message instead of findings/analysis/sources/timestamp.

        Raises:
            ValueError: If num_sources is not a positive integer
        """
        if not isinstance(num_sources, int) or num_sources <= 0:
            raise ValueError("num_sources must be a positive integer")

        if num_sources > self.config.max_search_results:
            num_sources = self.config.max_search_results

        result = self.researcher.research_topic(
            topic=topic,
            num_sources=num_sources,
        )

        self.last_research = result
        return result

    def summarize(self, urls: List[str]) -> SummarizeResult:
        """Summarize content from multiple URLs.

        Args:
            urls: List of URLs to summarize (all items must be strings and valid HTTP(S) URLs).

        Returns:
            Dictionary containing:
            - status: "success"
            - summaries: Dict mapping each URL to its summary result
            - sources_count: Number of URLs provided

        Raises:
            TypeError: If urls is not a list, or any item in urls is not a string.
            ValueError: If any URL is not a valid HTTP(S) URL.
        """
        if not isinstance(urls, list):
            raise TypeError(f"urls must be a list, got {type(urls).__name__}")

        for i, url in enumerate(urls):
            if not isinstance(url, str):
                raise TypeError(
                    f"all urls must be strings, item at index {i} is {type(url).__name__}"
                )
            if not is_valid_url(url):
                raise ValueError(
                    f"all urls must be valid HTTP(S) URLs, item at index {i} is invalid: '{url}'"
                )

        summaries: Dict[str, Dict[str, Any]] = {}
        for url in urls:
            result = self.researcher.fetch_and_summarize(url)
            summaries[url] = result

        return {
            "status": "success",
            "summaries": summaries,
            "sources_count": len(urls),
        }

    def get_sources(self) -> List[str]:
        """Get list of all sources processed during research.

        Returns all URLs that have been successfully fetched since the agent was
        created or clear_history() was last called. Sources accumulate across
        multiple research() and summarize() calls.

        Returns:
            List of URLs from all successful fetch operations.
        """
        return self.researcher.get_sources()

    def clear_history(self) -> None:
        """Clear research history and cache."""
        self.researcher.clear_history()
        self.last_research = None

    def get_formatted_report(self) -> str:
        """Get formatted research report.

        Generates a markdown-formatted research report from the last research conducted.
        Includes the research topic, comprehensive analysis, findings from each source
        with URLs and summaries, and a formatted sources section.

        Returns:
            A markdown-formatted research report string. If no research has been
            conducted yet, returns "No research conducted yet.".
            Report format includes:
            - Level 1 header with topic
            - Analysis section
            - Findings section with sources
            - Formatted sources list
        """
        if not self.last_research:
            return "No research conducted yet."

        report = f"# Research Report: {self.last_research['topic']}\n\n"

        report += "## Analysis\n\n"
        report += self.last_research.get("analysis", "No analysis available") + "\n\n"

        report += "## Findings\n\n"
        findings = self.last_research.get("findings", [])
        source_num = 1
        for finding in findings:
            if finding.get("status") == "success":
                report += f"### Source {source_num}\n"
                report += f"**URL:** {finding.get('url', 'N/A')}\n\n"
                report += f"**Summary:** {finding.get('summary', 'N/A')}\n\n"
                source_num += 1

        report += format_sources(self.get_sources())

        return report
