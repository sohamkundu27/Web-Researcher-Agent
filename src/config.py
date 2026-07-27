"""Configuration management for Web Researcher Agent."""

import os
from dataclasses import dataclass
from typing import Any


@dataclass
class ResearchConfig:
    """Configuration settings for the research agent.

    Attributes:
        api_key: Anthropic API key for authenticating Claude API requests (required).
        model: Claude model identifier to use for research tasks
            (default: "claude-3-5-sonnet-20241022").
        max_search_results: Maximum number of search results to fetch per query.
            Must be greater than 0 (default: 10).
        max_depth: Reserved for future use to control research recursion depth.
            Must be greater than 0 (default: 3).
        timeout: Request timeout in seconds for URL fetching. Must be greater than 0
            (default: 30).
        cache_enabled: Whether to enable caching of fetched URLs and summaries
            (default: True).
        cache_ttl: Cache time-to-live in seconds. Must be non-negative.
            Set to 0 for no expiration (default: 3600, which is 1 hour).
    """

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

        try:
            max_search_results = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
        except ValueError:
            raise ValueError(
                f"MAX_SEARCH_RESULTS must be a valid integer, got '{os.getenv('MAX_SEARCH_RESULTS')}'"
            )

        try:
            max_depth = int(os.getenv("MAX_DEPTH", "3"))
        except ValueError:
            raise ValueError(
                f"MAX_DEPTH must be a valid integer, got '{os.getenv('MAX_DEPTH')}'"
            )

        try:
            timeout = int(os.getenv("TIMEOUT", "30"))
        except ValueError:
            raise ValueError(
                f"TIMEOUT must be a valid integer, got '{os.getenv('TIMEOUT')}'"
            )

        try:
            cache_ttl = int(os.getenv("CACHE_TTL", "3600"))
        except ValueError:
            raise ValueError(
                f"CACHE_TTL must be a valid integer, got '{os.getenv('CACHE_TTL')}'"
            )

        if max_search_results <= 0:
            raise ValueError("MAX_SEARCH_RESULTS must be greater than 0")
        if max_depth <= 0:
            raise ValueError("MAX_DEPTH must be greater than 0")
        if timeout <= 0:
            raise ValueError("TIMEOUT must be greater than 0")
        if cache_ttl < 0:
            raise ValueError("CACHE_TTL must be non-negative")

        return cls(
            api_key=api_key,
            model=os.getenv("RESEARCH_MODEL", "claude-3-5-sonnet-20241022"),
            max_search_results=max_search_results,
            max_depth=max_depth,
            timeout=timeout,
            cache_enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
            cache_ttl=cache_ttl,
        )

    @classmethod
    def with_api_key(cls, api_key: str, **kwargs: Any) -> "ResearchConfig":
        """Create configuration with explicit API key."""
        if not api_key:
            raise ValueError("api_key cannot be empty")

        if "model" in kwargs:
            if not isinstance(kwargs["model"], str):
                raise TypeError(
                    f"model must be a string, got {type(kwargs['model']).__name__}"
                )
            if not kwargs["model"]:
                raise ValueError("model cannot be empty")
        if "max_search_results" in kwargs:
            if not isinstance(kwargs["max_search_results"], int):
                raise TypeError(
                    f"max_search_results must be an integer, got {type(kwargs['max_search_results']).__name__}"
                )
            if kwargs["max_search_results"] <= 0:
                raise ValueError("max_search_results must be greater than 0")
        if "max_depth" in kwargs:
            if not isinstance(kwargs["max_depth"], int):
                raise TypeError(
                    f"max_depth must be an integer, got {type(kwargs['max_depth']).__name__}"
                )
            if kwargs["max_depth"] <= 0:
                raise ValueError("max_depth must be greater than 0")
        if "timeout" in kwargs:
            if not isinstance(kwargs["timeout"], int):
                raise TypeError(
                    f"timeout must be an integer, got {type(kwargs['timeout']).__name__}"
                )
            if kwargs["timeout"] <= 0:
                raise ValueError("timeout must be greater than 0")
        if "cache_enabled" in kwargs:
            if not isinstance(kwargs["cache_enabled"], bool):
                raise TypeError(
                    f"cache_enabled must be a boolean, got {type(kwargs['cache_enabled']).__name__}"
                )
        if "cache_ttl" in kwargs:
            if not isinstance(kwargs["cache_ttl"], int):
                raise TypeError(
                    f"cache_ttl must be an integer, got {type(kwargs['cache_ttl']).__name__}"
                )
            if kwargs["cache_ttl"] < 0:
                raise ValueError("cache_ttl must be non-negative")

        return cls(api_key=api_key, **kwargs)
