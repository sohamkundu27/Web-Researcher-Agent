"""Example usage of the Web Researcher Agent."""

import os
from src.agent import ResearchAgent


def main():
    """Run research example."""
    # Initialize agent with API key from environment
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

    topic = "Artificial Intelligence in Healthcare"
    print(f"\nResearching: {topic}\n")

    result = agent.research(topic, num_sources=3)

    if result["status"] == "success":
        print(f"Topic: {result['topic']}")
        print(f"Timestamp: {result['timestamp']}")
        print(f"\nAnalysis:")
        print(result.get("analysis", "No analysis available"))

        print(f"\n\nFindings ({len(result.get('findings', []))} sources):")
        for i, finding in enumerate(result.get("findings", []), 1):
            if finding.get("status") == "success":
                print(f"\n{i}. {finding.get('url', 'Unknown URL')}")
                print(f"   Summary: {finding.get('summary', 'N/A')[:200]}...")

        print(f"\n\nSources used ({len(result.get('sources', []))}):")
        for i, source in enumerate(result.get("sources", []), 1):
            print(f"{i}. {source}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

    # Example 2: Get formatted report
    print("\n" + "=" * 60)
    print("Example 2: Formatted Report")
    print("=" * 60)

    report = agent.get_formatted_report()
    print("\n" + report)

    # Example 3: Summarize specific URLs
    print("\n" + "=" * 60)
    print("Example 3: Summarize Specific URLs")
    print("=" * 60)

    urls = [
        "https://www.wikipedia.org/wiki/Artificial_intelligence",
        "https://www.wikipedia.org/wiki/Machine_learning",
    ]

    print(f"\nSummarizing {len(urls)} URLs...")
    summary_result = agent.summarize(urls)

    if summary_result["status"] == "success":
        for url, summary_data in summary_result["summaries"].items():
            print(f"\nURL: {url}")
            if summary_data.get("status") == "success":
                print(f"Summary: {summary_data.get('summary', 'N/A')[:300]}...")
            else:
                print(f"Error: {summary_data.get('error', 'Unknown error')}")


if __name__ == "__main__":
    main()
