"""Main agent for Web Researcher Agent."""

from typing import Dict, Any, List, Optional

from src.config import ResearchConfig
from src.researcher import WebResearcher
from src.utils import format_sources


class ResearchAgent:
    """High-level agent for conducting research."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-5-sonnet-20241022",
        max_search_results: int = 10,
        max_depth: int = 3,
        **kwargs,
    ):
        """Initialize research agent with configuration."""
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

        self.config = config
        self.researcher = WebResearcher(config)
        self.last_research: Optional[Dict[str, Any]] = None

    def research(
        self,
        topic: str,
        num_sources: int = 5,
    ) -> Dict[str, Any]:
        """Conduct research on a topic.

        Args:
            topic: The topic to research
            num_sources: Number of sources to fetch (default: 5)

        Returns:
            Dictionary containing research results with:
            - topic: The research topic
            - status: "success" or "error"
            - findings: List of summaries from each source
            - analysis: Comprehensive analysis of findings
            - sources: List of URLs used
            - timestamp: When research was conducted
        """
        if num_sources > self.config.max_search_results:
            num_sources = self.config.max_search_results

        result = self.researcher.research_topic(
            topic=topic,
            num_sources=num_sources,
        )

        self.last_research = result
        return result

    def summarize(self, urls: List[str]) -> Dict[str, Any]:
        """Summarize content from multiple URLs.

        Args:
            urls: List of URLs to summarize

        Returns:
            Dictionary with summaries for each URL
        """
        summaries = {}
        for url in urls:
            result = self.researcher.fetch_and_summarize(url)
            summaries[url] = result

        return {
            "status": "success",
            "summaries": summaries,
            "sources_count": len(urls),
        }

    def get_sources(self) -> List[str]:
        """Get list of sources used in the last research."""
        return self.researcher.get_sources()

    def clear_history(self) -> None:
        """Clear research history and cache."""
        self.researcher.clear_history()
        self.last_research = None

    def get_formatted_report(self) -> str:
        """Get formatted research report."""
        if not self.last_research:
            return "No research conducted yet."

        report = f"# Research Report: {self.last_research['topic']}\n\n"

        report += "## Analysis\n\n"
        report += self.last_research.get("analysis", "No analysis available") + "\n\n"

        report += "## Findings\n\n"
        findings = self.last_research.get("findings", [])
        for i, finding in enumerate(findings, 1):
            if finding.get("status") == "success":
                report += f"### Source {i}\n"
                report += f"**URL:** {finding.get('url', 'N/A')}\n\n"
                report += f"**Summary:** {finding.get('summary', 'N/A')}\n\n"

        report += format_sources(self.get_sources())

        return report
