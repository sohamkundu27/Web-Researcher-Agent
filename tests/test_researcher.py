"""Unit tests for Web Researcher Agent."""

import pytest
from unittest.mock import Mock, patch

from src.config import ResearchConfig
from src.researcher import WebResearcher, ContentCache
from src.utils import (
    extract_domain,
    is_valid_url,
    sanitize_text,
    hash_content,
    chunk_text,
)


class TestContentCache:
    """Test ContentCache class."""

    def test_cache_set_and_get(self):
        """Test setting and getting cache values."""
        cache = ContentCache(ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = ContentCache(ttl=0)
        cache.set("key1", "value1")
        import time

        time.sleep(0.1)
        assert cache.get("key1") is None

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = ContentCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestUtilityFunctions:
    """Test utility functions."""

    def test_extract_domain(self):
        """Test domain extraction from URL."""
        url = "https://www.example.com/path/to/page"
        assert extract_domain(url) == "www.example.com"

    def test_is_valid_url(self):
        """Test URL validation."""
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://example.com") is True
        assert is_valid_url("not a url") is False
        assert is_valid_url("ftp://example.com") is False

    def test_sanitize_text(self):
        """Test text sanitization."""
        text = "Hello    world!  @#$  Test."
        result = sanitize_text(text)
        assert "Hello world!" in result
        assert "@#$" not in result

    def test_hash_content(self):
        """Test content hashing."""
        content = "test content"
        hash1 = hash_content(content)
        hash2 = hash_content(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hash length

    def test_chunk_text(self):
        """Test text chunking."""
        text = "a" * 2500
        chunks = chunk_text(text, chunk_size=1000, overlap=100)
        assert len(chunks) > 1
        # Each chunk should be <= 1000 characters
        for chunk in chunks:
            assert len(chunk) <= 1000


class TestResearchConfig:
    """Test ResearchConfig class."""

    def test_config_with_api_key(self):
        """Test creating config with explicit API key."""
        config = ResearchConfig.with_api_key("test-key")
        assert config.api_key == "test-key"
        assert config.model == "claude-3-5-sonnet-20241022"

    def test_config_defaults(self):
        """Test config default values."""
        config = ResearchConfig.with_api_key("test-key")
        assert config.max_search_results == 10
        assert config.max_depth == 3
        assert config.timeout == 30
        assert config.cache_enabled is True


class TestWebResearcher:
    """Test WebResearcher class."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        return ResearchConfig.with_api_key("test-key")

    @pytest.fixture
    def researcher(self, config):
        """Create test researcher."""
        return WebResearcher(config)

    def test_researcher_initialization(self, researcher):
        """Test researcher initialization."""
        assert researcher.sources == []
        assert researcher.research_history == []

    def test_get_sources(self, researcher):
        """Test getting sources."""
        researcher.sources = ["https://example.com", "https://test.com"]
        assert researcher.get_sources() == ["https://example.com", "https://test.com"]

    def test_clear_history(self, researcher):
        """Test clearing history."""
        researcher.sources = ["https://example.com"]
        researcher.research_history = [{"topic": "test"}]
        researcher.clear_history()
        assert researcher.sources == []
        assert researcher.research_history == []

    @patch("src.researcher.WebResearcher.search")
    def test_search_called(self, mock_search, researcher):
        """Test that search is called properly."""
        mock_search.return_value = [
            {"url": "https://example.com", "title": "Test"}
        ]
        result = researcher.search("test query", num_results=5)
        mock_search.assert_called_once_with("test query", num_results=5)


def test_agent_initialization():
    """Test ResearchAgent initialization."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    assert agent.config.api_key == "test-key"
    assert agent.last_research is None


def test_agent_get_sources():
    """Test getting sources from agent."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.researcher.sources = ["https://example.com"]
    assert agent.get_sources() == ["https://example.com"]
