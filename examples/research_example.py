"""Example usage of the Web Researcher Agent."""

from typing import Any, Dict, List, Optional

from src.agent import ResearchAgent
from src.researcher import ResearchTopicResult


def main() -> None:
    """Demonstrate three core use cases of the ResearchAgent.

    This example shows:
    1. Basic research: Conducting topic-based research with multiple sources
    2. Formatted report: Generating a markdown-formatted report from research results
    3. URL summarization: Directly summarizing content from specific URLs

    Requires ANTHROPIC_API_KEY environment variable to be set.
    Prints results for each example to stdout.
    """
    # Initialize agent with API key from environment
    agent: Optional[ResearchAgent] = None
    try:
        agent = ResearchAgent()
    except ValueError as e:
        print(f"Error: {e}")
        print("Please set the ANTHROPIC_API_KEY environment variable")
        return

    # Example 1: Basic research
    print("=" * 60)
    print("Example 1: Basic Research")
    print("=" * 60)

    topic: str = "Artificial Intelligence in Healthcare"
    print(f"\nResearching: {topic}\n")

    result: ResearchTopicResult = agent.research(topic, num_sources=3)

    if result["status"] == "success":
        topic_str: str = result.get("topic", "Unknown")
        print(f"Topic: {topic_str}")
        print(f"Timestamp: {result.get('timestamp', 'N/A')}")
        print("\nAnalysis:")
        print(result.get("analysis", "No analysis available"))

        findings_list: List[Any] = result.get("findings", [])
        print(f"\n\nFindings ({len(findings_list)} sources):")
        for i, finding in enumerate(findings_list, 1):
            if finding.get("status") == "success":
                url: str = finding.get("url", "Unknown URL")
                summary_text: str = finding.get("summary", "N/A")
                print(f"\n{i}. {url}")
                print(f"   Summary: {summary_text[:200]}...")

        sources_list: List[Any] = result.get("sources", [])
        print(f"\n\nSources used ({len(sources_list)}):")
        for i, source in enumerate(sources_list, 1):
            print(f"{i}. {source}")
    else:
        error_msg: str = result.get("error", "Unknown error")
        print(f"Error: {error_msg}")

    # Example 2: Get formatted report
    print("\n" + "=" * 60)
    print("Example 2: Formatted Report")
    print("=" * 60)

    report: str = agent.get_formatted_report()
    print("\n" + report)

    # Example 3: Summarize specific URLs
    print("\n" + "=" * 60)
    print("Example 3: Summarize Specific URLs")
    print("=" * 60)

    urls: List[str] = [
        "https://www.wikipedia.org/wiki/Artificial_intelligence",
        "https://www.wikipedia.org/wiki/Machine_learning",
    ]

    print(f"\nSummarizing {len(urls)} URLs...")
    summary_result: Dict[str, Any] = agent.summarize(urls)

    if summary_result["status"] == "success":
        summaries_dict: Dict[str, Any] = summary_result.get("summaries", {})
        for url, summary_data in summaries_dict.items():
            print(f"\nURL: {url}")
            if summary_data.get("status") == "success":
                summary: str = summary_data.get("summary", "N/A")
                print(f"Summary: {summary[:300]}...")
            else:
                error: str = summary_data.get("error", "Unknown error")
                print(f"Error: {error}")


if __name__ == "__main__":
    main()
