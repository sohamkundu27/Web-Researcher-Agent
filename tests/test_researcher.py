"""Unit tests for Web Researcher Agent."""

import os
import pytest
import requests
from unittest.mock import Mock, patch

from src.config import ResearchConfig
from src.researcher import WebResearcher, ContentCache
from src.utils import (
    extract_domain,
    is_valid_url,
    sanitize_text,
    hash_content,
    chunk_text,
    extract_text_from_html,
    fetch_url_content,
    merge_dicts,
    format_sources,
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

    def test_cache_cleanup_on_expiration(self):
        """Test that expired items are removed from cache dict."""
        cache = ContentCache(ttl=0)
        cache.set("key1", "value1")
        assert len(cache.cache) == 1

        import time
        time.sleep(0.1)

        # Accessing expired item should return None and clean it up
        result = cache.get("key1")
        assert result is None
        assert len(cache.cache) == 0, "Expired item should be removed from cache dict"

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

    def test_sanitize_text_edge_cases(self):
        """Test text sanitization edge cases."""
        # Empty string
        assert sanitize_text("") == ""
        # Only whitespace
        assert sanitize_text("   \t\n   ") == ""
        # Already clean text
        assert sanitize_text("Hello world") == "Hello world"
        # Multiple spaces replaced with single space
        assert sanitize_text("Hello     world") == "Hello world"

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

    def test_extract_text_from_html_basic(self):
        """Test basic HTML text extraction."""
        html = "<html><body><h1>Title</h1><p>Content here</p></body></html>"
        result = extract_text_from_html(html)
        assert "Title" in result
        assert "Content here" in result

    def test_extract_text_from_html_removes_script_style(self):
        """Test that script and style tags are removed."""
        html = "<html><body><script>var x = 1;</script><style>body {color: red;}</style><p>Text</p></body></html>"
        result = extract_text_from_html(html)
        assert "var x" not in result
        assert "color: red" not in result
        assert "Text" in result

    def test_extract_text_from_html_max_length(self):
        """Test max_length parameter."""
        html = "<p>" + "a" * 1000 + "</p>"
        result = extract_text_from_html(html, max_length=100)
        assert len(result) <= 100

    def test_extract_text_from_html_invalid(self):
        """Test handling of invalid HTML."""
        result = extract_text_from_html("<invalid>not closed")
        assert isinstance(result, str)

    def test_extract_text_from_html_empty(self):
        """Test empty HTML."""
        result = extract_text_from_html("")
        assert result == ""

    def test_merge_dicts_simple(self):
        """Test simple dictionary merge."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3}
        result = merge_dicts(dict1, dict2)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_merge_dicts_overwrite(self):
        """Test dictionary merge with value overwriting."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 20, "c": 3}
        result = merge_dicts(dict1, dict2)
        assert result == {"a": 1, "b": 20, "c": 3}

    def test_merge_dicts_nested(self):
        """Test deep nested dictionary merge."""
        dict1 = {"a": {"x": 1, "y": 2}, "b": 3}
        dict2 = {"a": {"y": 20, "z": 30}, "c": 4}
        result = merge_dicts(dict1, dict2)
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}

    def test_merge_dicts_mixed_types(self):
        """Test merge with mixed dict and non-dict values."""
        dict1 = {"a": {"x": 1}, "b": 2}
        dict2 = {"a": "string", "b": 20}
        result = merge_dicts(dict1, dict2)
        # Non-dict value should overwrite dict value
        assert result == {"a": "string", "b": 20}

    def test_format_sources_empty(self):
        """Test formatting empty sources list."""
        result = format_sources([])
        assert result == ""

    def test_format_sources_single(self):
        """Test formatting single source."""
        result = format_sources(["https://www.example.com/page"])
        assert "## Sources" in result
        assert "example.com" in result
        assert "https://www.example.com/page" in result

    def test_format_sources_multiple(self):
        """Test formatting multiple sources."""
        sources = ["https://www.example.com", "https://test.org/path"]
        result = format_sources(sources)
        assert "## Sources" in result
        assert "1." in result
        assert "2." in result
        assert "example.com" in result
        assert "test.org" in result

    @patch("src.utils.requests.get")
    def test_fetch_url_content_success(self, mock_get):
        """Test successful URL fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<p>Test content</p>"
        mock_response.headers = {"Content-Type": "text/html"}
        mock_get.return_value = mock_response

        result = fetch_url_content("https://example.com")
        assert result["status"] == "success"
        assert result["url"] == "https://example.com"
        assert result["status_code"] == 200
        assert "Test content" in result["content"]
        assert "Content-Type" in result["headers"]

    @patch("src.utils.requests.get")
    def test_fetch_url_content_error(self, mock_get):
        """Test URL fetch with network error."""
        mock_get.side_effect = requests.RequestException("Connection failed")

        result = fetch_url_content("https://example.com")
        assert result["status"] == "error"
        assert result["url"] == "https://example.com"
        assert "Connection failed" in result["error"]


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

    def test_config_with_api_key_empty_api_key(self):
        """Test that empty api_key raises ValueError."""
        with pytest.raises(ValueError, match="api_key cannot be empty"):
            ResearchConfig.with_api_key("")

    def test_config_with_api_key_invalid_max_search_results(self):
        """Test that non-positive max_search_results raises ValueError."""
        with pytest.raises(ValueError, match="max_search_results must be greater than 0"):
            ResearchConfig.with_api_key("test-key", max_search_results=0)

        with pytest.raises(ValueError, match="max_search_results must be greater than 0"):
            ResearchConfig.with_api_key("test-key", max_search_results=-1)

    def test_config_with_api_key_invalid_max_depth(self):
        """Test that non-positive max_depth raises ValueError."""
        with pytest.raises(ValueError, match="max_depth must be greater than 0"):
            ResearchConfig.with_api_key("test-key", max_depth=0)

        with pytest.raises(ValueError, match="max_depth must be greater than 0"):
            ResearchConfig.with_api_key("test-key", max_depth=-5)

    def test_config_with_api_key_invalid_timeout(self):
        """Test that non-positive timeout raises ValueError."""
        with pytest.raises(ValueError, match="timeout must be greater than 0"):
            ResearchConfig.with_api_key("test-key", timeout=0)

        with pytest.raises(ValueError, match="timeout must be greater than 0"):
            ResearchConfig.with_api_key("test-key", timeout=-10)

    def test_config_with_api_key_invalid_cache_ttl(self):
        """Test that negative cache_ttl raises ValueError."""
        with pytest.raises(ValueError, match="cache_ttl must be non-negative"):
            ResearchConfig.with_api_key("test-key", cache_ttl=-1)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True)
    def test_config_from_env_missing_api_key(self):
        """Test that missing ANTHROPIC_API_KEY raises ValueError."""
        import os
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable not set"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "MAX_SEARCH_RESULTS": "not_a_number"})
    def test_config_from_env_invalid_max_search_results(self):
        """Test that invalid MAX_SEARCH_RESULTS raises descriptive ValueError."""
        with pytest.raises(ValueError, match="MAX_SEARCH_RESULTS must be a valid integer"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "MAX_DEPTH": "invalid"})
    def test_config_from_env_invalid_max_depth(self):
        """Test that invalid MAX_DEPTH raises descriptive ValueError."""
        with pytest.raises(ValueError, match="MAX_DEPTH must be a valid integer"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "TIMEOUT": "xyz"})
    def test_config_from_env_invalid_timeout(self):
        """Test that invalid TIMEOUT raises descriptive ValueError."""
        with pytest.raises(ValueError, match="TIMEOUT must be a valid integer"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "CACHE_TTL": "not_int"})
    def test_config_from_env_invalid_cache_ttl(self):
        """Test that invalid CACHE_TTL raises descriptive ValueError."""
        with pytest.raises(ValueError, match="CACHE_TTL must be a valid integer"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "MAX_SEARCH_RESULTS": "0"})
    def test_config_from_env_zero_max_search_results(self):
        """Test that zero MAX_SEARCH_RESULTS raises ValueError."""
        with pytest.raises(ValueError, match="MAX_SEARCH_RESULTS must be greater than 0"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "MAX_DEPTH": "-5"})
    def test_config_from_env_negative_max_depth(self):
        """Test that negative MAX_DEPTH raises ValueError."""
        with pytest.raises(ValueError, match="MAX_DEPTH must be greater than 0"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "TIMEOUT": "-1"})
    def test_config_from_env_negative_timeout(self):
        """Test that negative TIMEOUT raises ValueError."""
        with pytest.raises(ValueError, match="TIMEOUT must be greater than 0"):
            ResearchConfig.from_env()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "CACHE_TTL": "-10"})
    def test_config_from_env_negative_cache_ttl(self):
        """Test that negative CACHE_TTL raises ValueError."""
        with pytest.raises(ValueError, match="CACHE_TTL must be non-negative"):
            ResearchConfig.from_env()


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
        researcher.search("test query", num_results=5)
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


def test_agent_clear_history():
    """Test clearing history in agent."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.researcher.sources = ["https://example.com"]
    agent.last_research = {"topic": "test", "status": "success"}

    agent.clear_history()

    assert agent.researcher.sources == []
    assert agent.researcher.research_history == []
    assert agent.last_research is None


@patch("src.researcher.WebResearcher.fetch_and_summarize")
def test_agent_summarize(mock_fetch):
    """Test summarizing multiple URLs."""
    from src.agent import ResearchAgent

    mock_fetch.side_effect = [
        {"status": "success", "summary": "Summary 1", "url": "https://example.com"},
        {"status": "success", "summary": "Summary 2", "url": "https://test.com"},
    ]

    agent = ResearchAgent(api_key="test-key")
    urls = ["https://example.com", "https://test.com"]
    result = agent.summarize(urls)

    assert result["status"] == "success"
    assert result["sources_count"] == 2
    assert len(result["summaries"]) == 2
    assert result["summaries"]["https://example.com"]["summary"] == "Summary 1"
    assert result["summaries"]["https://test.com"]["summary"] == "Summary 2"


def test_agent_get_formatted_report_no_research():
    """Test getting formatted report when no research conducted."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    report = agent.get_formatted_report()

    assert report == "No research conducted yet."


def test_agent_get_formatted_report_with_research():
    """Test getting formatted report with completed research."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.last_research = {
        "topic": "Python",
        "analysis": "Python is a programming language.",
        "findings": [
            {
                "status": "success",
                "url": "https://python.org",
                "summary": "Official Python website",
            },
            {
                "status": "error",
                "url": "https://invalid.url",
                "error": "Failed to fetch",
            },
        ],
    }
    agent.researcher.sources = ["https://python.org"]

    report = agent.get_formatted_report()

    assert "# Research Report: Python" in report
    assert "## Analysis" in report
    assert "Python is a programming language." in report
    assert "## Findings" in report
    assert "https://python.org" in report
    assert "Official Python website" in report
    assert "## Sources" in report
    # Invalid finding should not be in report
    assert "Failed to fetch" not in report


def test_agent_num_sources_clamping():
    """Test that num_sources is clamped to max_search_results."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key", max_search_results=5)
    assert agent.config.max_search_results == 5

    with patch.object(agent.researcher, "research_topic") as mock_research:
        mock_research.return_value = {"topic": "test", "status": "success"}

        # Request more sources than allowed
        agent.research("test query", num_sources=10)

        # Verify it was clamped to max_search_results
        mock_research.assert_called_once_with(topic="test query", num_sources=5)
