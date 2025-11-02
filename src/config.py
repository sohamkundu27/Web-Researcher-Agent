"""Configuration management for Web Researcher Agent."""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class ResearchConfig:
    """Configuration settings for the research agent."""

    api_key: str
    model: str = "claude-3-5-sonnet-20241022"
    max_search_results: int = 10
    max_depth: int = 3
    timeout: int = 30
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour

    @classmethod
    def from_env(cls) -> "ResearchConfig":
        """Load configuration from environment variables."""
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        return cls(
            api_key=api_key,
            model=os.getenv("RESEARCH_MODEL", "claude-3-5-sonnet-20241022"),
            max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "10")),
            max_depth=int(os.getenv("MAX_DEPTH", "3")),
            timeout=int(os.getenv("TIMEOUT", "30")),
            cache_enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
            cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
        )

    @classmethod
    def with_api_key(cls, api_key: str, **kwargs) -> "ResearchConfig":
        """Create configuration with explicit API key."""
        return cls(api_key=api_key, **kwargs)
