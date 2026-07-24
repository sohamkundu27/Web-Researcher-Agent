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

    def test_cache_negative_ttl(self):
        """Test that negative TTL raises ValueError."""
        with pytest.raises(ValueError, match="ttl must be non-negative"):
            ContentCache(ttl=-1)

    def test_cache_with_falsy_values(self):
        """Test that cache correctly stores and retrieves falsy values."""
        cache = ContentCache(ttl=60)

        # Test with 0
        cache.set("key1", 0)
        assert cache.get("key1") == 0

        # Test with False
        cache.set("key2", False)
        assert cache.get("key2") is False

        # Test with empty string
        cache.set("key3", "")
        assert cache.get("key3") == ""

        # Test with empty dict
        cache.set("key4", {})
        assert cache.get("key4") == {}

        # Test with empty list
        cache.set("key5", [])
        assert cache.get("key5") == []

    def test_cache_ttl_boundary_exact(self):
        """Test cache respects exact TTL boundary by directly setting expiration times."""
        from datetime import datetime, timedelta

        cache = ContentCache(ttl=10)
        now = datetime.now()

        # Test 1: Item that expires in the future should be accessible
        future_expires = now + timedelta(seconds=10)
        cache.cache["future_key"] = {"value": "future_value", "expires": future_expires}
        assert cache.get("future_key") == "future_value"

        # Test 2: Item that expired just now should not be accessible
        past_expires = now - timedelta(seconds=0.001)
        cache.cache["past_key"] = {"value": "past_value", "expires": past_expires}
        result = cache.get("past_key")
        assert result is None, "Item should be expired when expiration time is in the past"
        assert "past_key" not in cache.cache, "Expired item should be removed from cache dict"

        # Test 3: Item that expires exactly at now should not be accessible
        # (comparison uses < not <=, so at equality, item is expired)
        exact_expires = now
        cache.cache["exact_key"] = {"value": "exact_value", "expires": exact_expires}
        result = cache.get("exact_key")
        assert result is None, "Item should be expired when expiration time equals now"
        assert "exact_key" not in cache.cache, "Expired item should be removed from cache"

    def test_cache_with_none_value(self):
        """Test that cache correctly stores and retrieves None as a cached value."""
        cache = ContentCache(ttl=60)

        # Store None explicitly
        cache.set("none_key", None)
        result = cache.get("none_key")

        # Verify None is retrieved correctly
        assert result is None
        # Verify the key is actually in the cache (not just a cache miss)
        assert "none_key" in cache.cache

    def test_cache_get_nonexistent_key(self):
        """Test that get() returns None for keys that don't exist in cache."""
        cache = ContentCache(ttl=60)
        result = cache.get("nonexistent_key")
        assert result is None
        assert "nonexistent_key" not in cache.cache

    def test_cache_update_key(self):
        """Test that setting a key multiple times updates the value and expiration."""
        cache = ContentCache(ttl=60)

        # Set initial value
        cache.set("key", "value1")
        assert cache.get("key") == "value1"

        # Update with new value
        cache.set("key", "value2")
        assert cache.get("key") == "value2"

        # Verify only one entry exists
        assert len(cache.cache) == 1

    def test_cache_set_ttl_calculation(self):
        """Test that set() correctly calculates expiration time based on TTL."""
        from datetime import datetime, timedelta

        cache = ContentCache(ttl=10)

        before = datetime.now()
        cache.set("key1", "value1")
        after = datetime.now()

        # Get the expiration time from the cache
        entry = cache.cache["key1"]
        expires = entry["expires"]

        # Verify that expiration time is approximately now + ttl seconds
        # Account for the time elapsed between capturing before and after
        expected_expires_min = before + timedelta(seconds=10)
        expected_expires_max = after + timedelta(seconds=10)

        assert expected_expires_min <= expires <= expected_expires_max, \
            f"Expiration time {expires} should be between {expected_expires_min} and {expected_expires_max}"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_extract_domain(self):
        """Test domain extraction from URL."""
        url = "https://www.example.com/path/to/page"
        assert extract_domain(url) == "www.example.com"

    def test_extract_domain_invalid_type_none(self):
        """Test domain extraction with None."""
        with pytest.raises(TypeError, match="url must be a string"):
            extract_domain(None)

    def test_extract_domain_invalid_type_int(self):
        """Test domain extraction with non-string type."""
        with pytest.raises(TypeError, match="url must be a string"):
            extract_domain(123)

    def test_extract_domain_invalid_type_list(self):
        """Test domain extraction with list type."""
        with pytest.raises(TypeError, match="url must be a string"):
            extract_domain([])

    def test_is_valid_url(self):
        """Test URL validation."""
        assert is_valid_url("https://example.com") is True
        assert is_valid_url("http://example.com") is True
        assert is_valid_url("not a url") is False
        assert is_valid_url("ftp://example.com") is False

    def test_is_valid_url_none(self):
        """Test URL validation with None."""
        assert is_valid_url(None) is False

    def test_is_valid_url_invalid_type(self):
        """Test URL validation with non-string types."""
        assert is_valid_url(123) is False
        assert is_valid_url([]) is False
        assert is_valid_url({}) is False

    def test_sanitize_text(self):
        """Test text sanitization."""
        text = "Hello    world!  @#$  Test."
        result = sanitize_text(text)
        assert "Hello world!" in result
        assert "@#$" not in result

    def test_sanitize_text_edge_cases(self):
        """Test text sanitization edge cases."""
        assert sanitize_text("") == ""
        assert sanitize_text("   \t\n   ") == ""
        assert sanitize_text("Hello world") == "Hello world"
        assert sanitize_text("Hello     world") == "Hello world"

    def test_sanitize_text_invalid_type_none(self):
        """Test text sanitization with None."""
        with pytest.raises(TypeError, match="text must be a string"):
            sanitize_text(None)

    def test_sanitize_text_invalid_type_int(self):
        """Test text sanitization with non-string type."""
        with pytest.raises(TypeError, match="text must be a string"):
            sanitize_text(123)

    def test_sanitize_text_invalid_type_list(self):
        """Test text sanitization with list type."""
        with pytest.raises(TypeError, match="text must be a string"):
            sanitize_text([])

    def test_sanitize_text_apostrophe_removal(self):
        """Test that apostrophes are removed (contractions become invalid)."""
        # This documents the current behavior: apostrophes are stripped
        text = "don't can't won't"
        result = sanitize_text(text)
        # Apostrophes are removed, leaving "dont cant wont"
        assert "don't" not in result
        assert "dont" in result or result  # Either apostrophe removed or text modified
        # The regex [^\w\s.,!?-] removes apostrophes
        assert "'" not in result

    def test_sanitize_text_special_chars_with_spaces(self):
        """Test that whitespace is normalized after removing special characters."""
        # Special chars surrounded by spaces should not leave double spaces
        result = sanitize_text("Hello @#$ world")
        assert result == "Hello world"
        # Adjacent special chars should be removed without leaving gaps
        result = sanitize_text("Hello@#$world")
        assert result == "Helloworld"
        # Mixed punctuation and special chars
        result = sanitize_text("Hello!?@#$world")
        assert result == "Hello!?world"

    def test_hash_content(self):
        """Test content hashing."""
        content = "test content"
        hash1 = hash_content(content)
        hash2 = hash_content(content)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hash length

    def test_hash_content_invalid_type_none(self):
        """Test hash_content with None."""
        with pytest.raises(TypeError, match="content must be a string"):
            hash_content(None)

    def test_hash_content_invalid_type_int(self):
        """Test hash_content with integer."""
        with pytest.raises(TypeError, match="content must be a string"):
            hash_content(123)

    def test_hash_content_invalid_type_list(self):
        """Test hash_content with list."""
        with pytest.raises(TypeError, match="content must be a string"):
            hash_content([])

    def test_hash_content_invalid_type_dict(self):
        """Test hash_content with dict."""
        with pytest.raises(TypeError, match="content must be a string"):
            hash_content({})

    def test_hash_content_empty_string(self):
        """Test hash_content with empty string."""
        result = hash_content("")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 hash length

    def test_chunk_text(self):
        """Test text chunking."""
        text = "a" * 2500
        chunks = chunk_text(text, chunk_size=1000, overlap=100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_chunk_text_invalid_chunk_size_zero(self):
        """Test chunk_text with zero chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            chunk_text("text", chunk_size=0)

    def test_chunk_text_invalid_chunk_size_negative(self):
        """Test chunk_text with negative chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            chunk_text("text", chunk_size=-100)

    def test_chunk_text_invalid_overlap_negative(self):
        """Test chunk_text with negative overlap."""
        with pytest.raises(ValueError, match="overlap must be a non-negative integer"):
            chunk_text("text", chunk_size=100, overlap=-1)

    def test_chunk_text_overlap_equals_chunk_size(self):
        """Test chunk_text when overlap equals chunk_size."""
        with pytest.raises(ValueError, match="overlap .* must be less than chunk_size"):
            chunk_text("text", chunk_size=100, overlap=100)

    def test_chunk_text_overlap_greater_than_chunk_size(self):
        """Test chunk_text when overlap is greater than chunk_size."""
        with pytest.raises(ValueError, match="overlap .* must be less than chunk_size"):
            chunk_text("text", chunk_size=100, overlap=150)

    def test_chunk_text_invalid_text_type(self):
        """Test chunk_text with non-string text."""
        with pytest.raises(TypeError, match="text must be a string"):
            chunk_text(123, chunk_size=100)

    def test_chunk_text_invalid_chunk_size_type(self):
        """Test chunk_text with non-integer chunk_size."""
        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            chunk_text("text", chunk_size="100")

    def test_chunk_text_invalid_overlap_type(self):
        """Test chunk_text with non-integer overlap."""
        with pytest.raises(ValueError, match="overlap must be a non-negative integer"):
            chunk_text("text", chunk_size=100, overlap="10")

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

    def test_extract_text_from_html_zero_max_length(self):
        """Test extract_text_from_html with zero max_length."""
        with pytest.raises(ValueError, match="max_length must be a positive integer"):
            extract_text_from_html("<p>Test</p>", max_length=0)

    def test_extract_text_from_html_negative_max_length(self):
        """Test extract_text_from_html with negative max_length."""
        with pytest.raises(ValueError, match="max_length must be a positive integer"):
            extract_text_from_html("<p>Test</p>", max_length=-1)

    def test_extract_text_from_html_invalid_max_length_type(self):
        """Test extract_text_from_html with non-integer max_length."""
        with pytest.raises(ValueError, match="max_length must be a positive integer"):
            extract_text_from_html("<p>Test</p>", max_length="100")

    def test_extract_text_from_html_with_html_entities(self):
        """Test that HTML entities are properly decoded."""
        html = "<p>Hello &nbsp; world &lt; test &gt;</p>"
        result = extract_text_from_html(html)
        assert "Hello" in result
        assert "world" in result
        # HTML entities should be decoded by BeautifulSoup
        assert result.strip() != ""

    def test_extract_text_from_html_with_nested_tags(self):
        """Test extraction with deeply nested HTML tags."""
        html = "<div><section><article><p>Nested <strong>bold <em>italic</em></strong> text</p></article></section></div>"
        result = extract_text_from_html(html)
        assert "Nested" in result
        assert "bold" in result
        assert "italic" in result
        assert "text" in result

    def test_extract_text_from_html_preserves_punctuation(self):
        """Test that periods, commas, and question marks are preserved."""
        html = "<p>Hello. World, how are you? I'm fine!</p>"
        result = extract_text_from_html(html)
        assert "." in result
        assert "," in result
        assert "?" in result
        assert "!" in result

    def test_extract_text_from_html_invalid_html_type_none(self):
        """Test extract_text_from_html with None."""
        with pytest.raises(TypeError, match="html must be a string"):
            extract_text_from_html(None)

    def test_extract_text_from_html_invalid_html_type_int(self):
        """Test extract_text_from_html with integer."""
        with pytest.raises(TypeError, match="html must be a string"):
            extract_text_from_html(123)

    def test_extract_text_from_html_invalid_html_type_list(self):
        """Test extract_text_from_html with list."""
        with pytest.raises(TypeError, match="html must be a string"):
            extract_text_from_html([])

    def test_extract_text_from_html_invalid_html_type_dict(self):
        """Test extract_text_from_html with dict."""
        with pytest.raises(TypeError, match="html must be a string"):
            extract_text_from_html({})

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

    def test_merge_dicts_empty_dicts(self):
        """Test merge with empty dictionaries."""
        # Merge empty dict with non-empty
        result = merge_dicts({}, {"a": 1, "b": 2})
        assert result == {"a": 1, "b": 2}

        # Merge non-empty with empty dict
        result = merge_dicts({"a": 1, "b": 2}, {})
        assert result == {"a": 1, "b": 2}

        # Merge two empty dicts
        result = merge_dicts({}, {})
        assert result == {}

    def test_merge_dicts_deeply_nested(self):
        """Test merge with deeply nested (3+ levels) dictionaries."""
        dict1 = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
        dict2 = {"a": {"b": {"c": {"e": 20, "f": 30}, "x": 100}}}
        result = merge_dicts(dict1, dict2)
        expected = {"a": {"b": {"c": {"d": 1, "e": 20, "f": 30}, "x": 100}}}
        assert result == expected

    def test_merge_dicts_with_none_values(self):
        """Test merge with None values in dictionaries."""
        dict1 = {"a": None, "b": 2}
        dict2 = {"a": 1, "c": None}
        result = merge_dicts(dict1, dict2)
        assert result == {"a": 1, "b": 2, "c": None}

    def test_merge_dicts_does_not_mutate_inputs(self):
        """Test that merge_dicts does not mutate input dictionaries."""
        dict1 = {"a": {"x": 1, "y": 2}, "b": 3}
        dict2 = {"a": {"y": 20, "z": 30}, "c": 4}
        original_dict1 = {"a": {"x": 1, "y": 2}, "b": 3}
        original_dict2 = {"a": {"y": 20, "z": 30}, "c": 4}

        result = merge_dicts(dict1, dict2)

        # Verify inputs are not modified
        assert dict1 == original_dict1
        assert dict2 == original_dict2
        # Verify result is correct
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3, "c": 4}

    def test_merge_dicts_invalid_dict1_type_none(self):
        """Test merge_dicts with None as dict1."""
        with pytest.raises(TypeError, match="dict1 must be a dictionary"):
            merge_dicts(None, {"b": 2})

    def test_merge_dicts_invalid_dict1_type_string(self):
        """Test merge_dicts with string as dict1."""
        with pytest.raises(TypeError, match="dict1 must be a dictionary"):
            merge_dicts("not a dict", {"b": 2})

    def test_merge_dicts_invalid_dict1_type_list(self):
        """Test merge_dicts with list as dict1."""
        with pytest.raises(TypeError, match="dict1 must be a dictionary"):
            merge_dicts([1, 2, 3], {"b": 2})

    def test_merge_dicts_invalid_dict1_type_int(self):
        """Test merge_dicts with int as dict1."""
        with pytest.raises(TypeError, match="dict1 must be a dictionary"):
            merge_dicts(42, {"b": 2})

    def test_merge_dicts_invalid_dict2_type_none(self):
        """Test merge_dicts with None as dict2."""
        with pytest.raises(TypeError, match="dict2 must be a dictionary"):
            merge_dicts({"a": 1}, None)

    def test_merge_dicts_invalid_dict2_type_string(self):
        """Test merge_dicts with string as dict2."""
        with pytest.raises(TypeError, match="dict2 must be a dictionary"):
            merge_dicts({"a": 1}, "not a dict")

    def test_merge_dicts_invalid_dict2_type_list(self):
        """Test merge_dicts with list as dict2."""
        with pytest.raises(TypeError, match="dict2 must be a dictionary"):
            merge_dicts({"a": 1}, [1, 2, 3])

    def test_merge_dicts_invalid_dict2_type_int(self):
        """Test merge_dicts with int as dict2."""
        with pytest.raises(TypeError, match="dict2 must be a dictionary"):
            merge_dicts({"a": 1}, 42)

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

    def test_format_sources_invalid_type_none(self):
        """Test format_sources with None."""
        with pytest.raises(TypeError, match="sources must be a list"):
            format_sources(None)

    def test_format_sources_invalid_type_string(self):
        """Test format_sources with string instead of list."""
        with pytest.raises(TypeError, match="sources must be a list"):
            format_sources("https://example.com")

    def test_format_sources_invalid_type_dict(self):
        """Test format_sources with dict instead of list."""
        with pytest.raises(TypeError, match="sources must be a list"):
            format_sources({"url": "https://example.com"})

    def test_format_sources_invalid_item_type_int(self):
        """Test format_sources with integer item in list."""
        with pytest.raises(TypeError, match="all sources must be strings.*index 0.*int"):
            format_sources([123])

    def test_format_sources_invalid_item_type_none(self):
        """Test format_sources with None item in list."""
        with pytest.raises(TypeError, match="all sources must be strings.*index 0.*NoneType"):
            format_sources([None])

    def test_format_sources_invalid_item_type_mixed(self):
        """Test format_sources with mixed string and non-string items."""
        with pytest.raises(TypeError, match="all sources must be strings.*index 1.*int"):
            format_sources(["https://example.com", 456])

    def test_format_sources_invalid_item_type_list(self):
        """Test format_sources with list item in sources list."""
        with pytest.raises(TypeError, match="all sources must be strings.*index 0.*list"):
            format_sources([["https://example.com"]])

    def test_format_sources_invalid_item_type_dict_in_list(self):
        """Test format_sources with dict item in sources list."""
        with pytest.raises(TypeError, match="all sources must be strings.*index 1.*dict"):
            format_sources(["https://example.com", {"url": "https://test.com"}])

    def test_format_sources_with_empty_string_item(self):
        """Test format_sources with empty string in sources list."""
        # Empty string is accepted but produces invalid markdown link []()
        result = format_sources(["https://example.com", ""])
        assert "## Sources" in result
        assert "example.com" in result
        # Verify empty string creates an empty link
        assert "[]" in result
        assert "()" in result

    def test_fetch_url_content_invalid_url_type_none(self):
        """Test fetch_url_content with None URL."""
        with pytest.raises(TypeError, match="url must be a string"):
            fetch_url_content(None)

    def test_fetch_url_content_invalid_url_type_int(self):
        """Test fetch_url_content with integer URL."""
        with pytest.raises(TypeError, match="url must be a string"):
            fetch_url_content(123)

    def test_fetch_url_content_invalid_url_type_list(self):
        """Test fetch_url_content with list URL."""
        with pytest.raises(TypeError, match="url must be a string"):
            fetch_url_content([])

    def test_fetch_url_content_invalid_url_format_no_protocol(self):
        """Test fetch_url_content with URL missing protocol."""
        with pytest.raises(ValueError, match="url must be a valid HTTP\\(S\\) URL"):
            fetch_url_content("example.com")

    def test_fetch_url_content_invalid_url_format_ftp(self):
        """Test fetch_url_content with FTP URL."""
        with pytest.raises(ValueError, match="url must be a valid HTTP\\(S\\) URL"):
            fetch_url_content("ftp://example.com")

    def test_fetch_url_content_invalid_timeout_type(self):
        """Test fetch_url_content with non-integer timeout."""
        with pytest.raises(ValueError, match="timeout must be a positive integer"):
            fetch_url_content("https://example.com", timeout="10")

    def test_fetch_url_content_invalid_timeout_zero(self):
        """Test fetch_url_content with zero timeout."""
        with pytest.raises(ValueError, match="timeout must be a positive integer"):
            fetch_url_content("https://example.com", timeout=0)

    def test_fetch_url_content_invalid_timeout_negative(self):
        """Test fetch_url_content with negative timeout."""
        with pytest.raises(ValueError, match="timeout must be a positive integer"):
            fetch_url_content("https://example.com", timeout=-5)

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

    @patch("src.utils.requests.get")
    def test_fetch_url_content_http_error(self, mock_get):
        """Test URL fetch with HTTP error (404, 500, etc)."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        result = fetch_url_content("https://example.com")
        assert result["status"] == "error"
        assert result["url"] == "https://example.com"
        assert "404 Not Found" in result["error"]

    @patch("src.utils.requests.get")
    def test_fetch_url_content_timeout_parameter_passed(self, mock_get):
        """Test that timeout parameter is correctly passed to requests.get."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<p>Content</p>"
        mock_response.headers = {}
        mock_get.return_value = mock_response

        fetch_url_content("https://example.com", timeout=25)

        # Verify that requests.get was called with the correct timeout
        mock_get.assert_called_once_with("https://example.com", timeout=25)


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

    def test_config_with_api_key_invalid_max_search_results_type(self):
        """Test that non-integer max_search_results raises TypeError."""
        with pytest.raises(TypeError, match="max_search_results must be an integer"):
            ResearchConfig.with_api_key("test-key", max_search_results="10")

        with pytest.raises(TypeError, match="max_search_results must be an integer"):
            ResearchConfig.with_api_key("test-key", max_search_results=10.5)

        with pytest.raises(TypeError, match="max_search_results must be an integer"):
            ResearchConfig.with_api_key("test-key", max_search_results=[10])

    def test_config_with_api_key_invalid_max_depth_type(self):
        """Test that non-integer max_depth raises TypeError."""
        with pytest.raises(TypeError, match="max_depth must be an integer"):
            ResearchConfig.with_api_key("test-key", max_depth="3")

        with pytest.raises(TypeError, match="max_depth must be an integer"):
            ResearchConfig.with_api_key("test-key", max_depth=3.5)

        with pytest.raises(TypeError, match="max_depth must be an integer"):
            ResearchConfig.with_api_key("test-key", max_depth={"value": 3})

    def test_config_with_api_key_invalid_timeout_type(self):
        """Test that non-integer timeout raises TypeError."""
        with pytest.raises(TypeError, match="timeout must be an integer"):
            ResearchConfig.with_api_key("test-key", timeout="30")

        with pytest.raises(TypeError, match="timeout must be an integer"):
            ResearchConfig.with_api_key("test-key", timeout=30.5)

        with pytest.raises(TypeError, match="timeout must be an integer"):
            ResearchConfig.with_api_key("test-key", timeout=None)

    def test_config_with_api_key_invalid_cache_ttl_type(self):
        """Test that non-integer cache_ttl raises TypeError."""
        with pytest.raises(TypeError, match="cache_ttl must be an integer"):
            ResearchConfig.with_api_key("test-key", cache_ttl="3600")

        with pytest.raises(TypeError, match="cache_ttl must be an integer"):
            ResearchConfig.with_api_key("test-key", cache_ttl=3600.5)

        with pytest.raises(TypeError, match="cache_ttl must be an integer"):
            ResearchConfig.with_api_key("test-key", cache_ttl=[3600])

    @patch.dict(os.environ, {}, clear=True)
    def test_config_from_env_missing_api_key(self):
        """Test that missing ANTHROPIC_API_KEY raises ValueError."""
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


@patch("src.researcher.WebResearcher.fetch_and_summarize")
def test_agent_summarize_with_mixed_results(mock_fetch):
    """Test summarizing URLs with some failures."""
    from src.agent import ResearchAgent

    mock_fetch.side_effect = [
        {"status": "success", "summary": "Summary 1", "url": "https://example.com"},
        {"status": "error", "error": "Connection failed", "url": "https://invalid.com"},
    ]

    agent = ResearchAgent(api_key="test-key")
    urls = ["https://example.com", "https://invalid.com"]
    result = agent.summarize(urls)

    assert result["status"] == "success"
    assert result["sources_count"] == 2
    assert len(result["summaries"]) == 2
    # Success result should include summary
    assert result["summaries"]["https://example.com"]["status"] == "success"
    assert result["summaries"]["https://example.com"]["summary"] == "Summary 1"
    # Error result should include error
    assert result["summaries"]["https://invalid.com"]["status"] == "error"
    assert "Connection failed" in result["summaries"]["https://invalid.com"]["error"]


def test_agent_summarize_empty_urls():
    """Test summarizing empty URL list."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    result = agent.summarize([])

    assert result["status"] == "success"
    assert result["sources_count"] == 0
    assert result["summaries"] == {}


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


def test_agent_get_formatted_report_all_failures():
    """Test getting formatted report when all findings fail."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.last_research = {
        "topic": "Python",
        "analysis": "Python is a programming language.",
        "findings": [
            {
                "status": "error",
                "url": "https://url1.com",
                "error": "Failed to fetch",
            },
            {
                "status": "error",
                "url": "https://url2.com",
                "error": "Timeout",
            },
        ],
    }
    agent.researcher.sources = []

    report = agent.get_formatted_report()

    assert "# Research Report: Python" in report
    assert "## Analysis" in report
    assert "Python is a programming language." in report
    assert "## Findings" in report
    # Failed findings should not appear in report
    assert "Failed to fetch" not in report
    assert "Timeout" not in report
    # With no sources, Sources section should not appear
    assert "## Sources" not in report


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


def test_agent_num_sources_zero():
    """Test that num_sources=0 raises ValueError."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    with pytest.raises(ValueError, match="num_sources must be a positive integer"):
        agent.research("test query", num_sources=0)


def test_agent_num_sources_negative():
    """Test that negative num_sources raises ValueError."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    with pytest.raises(ValueError, match="num_sources must be a positive integer"):
        agent.research("test query", num_sources=-5)


def test_agent_num_sources_float():
    """Test that float num_sources raises ValueError."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    with pytest.raises(ValueError, match="num_sources must be a positive integer"):
        agent.research("test query", num_sources=5.5)


def test_agent_num_sources_boundary():
    """Test that num_sources at boundary (equals max_search_results) works."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key", max_search_results=5)

    with patch.object(agent.researcher, "research_topic") as mock_research:
        mock_research.return_value = {"topic": "test", "status": "success"}

        # Request exactly max_search_results
        agent.research("test query", num_sources=5)

        # Verify it was NOT clamped (should be 5, not less)
        mock_research.assert_called_once_with(topic="test query", num_sources=5)


def test_agent_num_sources_minimum():
    """Test that num_sources=1 (minimum valid) works."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key", max_search_results=5)

    with patch.object(agent.researcher, "research_topic") as mock_research:
        mock_research.return_value = {"topic": "test", "status": "success"}

        # Request minimum valid sources
        agent.research("test query", num_sources=1)

        # Verify it was passed as-is
        mock_research.assert_called_once_with(topic="test query", num_sources=1)


def test_agent_get_formatted_report_numbered_sources_correctly():
    """Test that successful sources are numbered sequentially (1, 2, 3) when there are mixed success/error findings."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.last_research = {
        "topic": "Test Topic",
        "analysis": "Test analysis.",
        "findings": [
            {
                "status": "success",
                "url": "https://first.com",
                "summary": "First source",
            },
            {
                "status": "error",
                "url": "https://failed.com",
                "error": "Failed to fetch",
            },
            {
                "status": "success",
                "url": "https://second.com",
                "summary": "Second source",
            },
            {
                "status": "error",
                "url": "https://also-failed.com",
                "error": "Connection timeout",
            },
            {
                "status": "success",
                "url": "https://third.com",
                "summary": "Third source",
            },
        ],
    }
    agent.researcher.sources = ["https://first.com", "https://second.com", "https://third.com"]

    report = agent.get_formatted_report()

    # Verify that successful sources are numbered sequentially
    assert "### Source 1" in report
    assert "### Source 2" in report
    assert "### Source 3" in report
    # Verify gap numbering doesn't appear
    assert "### Source 4" not in report
    assert "### Source 5" not in report
    # Verify all successful sources are present
    assert "https://first.com" in report
    assert "First source" in report
    assert "https://second.com" in report
    assert "Second source" in report
    assert "https://third.com" in report
    assert "Third source" in report
    # Verify failed sources are not present
    assert "Failed to fetch" not in report
    assert "Connection timeout" not in report


def test_agent_get_formatted_report_missing_finding_keys():
    """Test that missing 'url' and 'summary' keys default to 'N/A' in findings."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.last_research = {
        "topic": "Test Topic",
        "analysis": "Test analysis.",
        "findings": [
            {
                "status": "success",
                # Missing 'url' key - should show "N/A"
                "summary": "First summary",
            },
            {
                "status": "success",
                "url": "https://second.com",
                # Missing 'summary' key - should show "N/A"
            },
            {
                "status": "success",
                # Missing both 'url' and 'summary' keys
            },
        ],
    }
    agent.researcher.sources = []

    report = agent.get_formatted_report()

    # Verify that N/A appears for missing keys
    assert "**URL:** N/A" in report
    assert "**Summary:** N/A" in report
    # Verify that sources are still numbered correctly
    assert "### Source 1" in report
    assert "### Source 2" in report
    assert "### Source 3" in report
    # Verify valid URL and summary are present
    assert "https://second.com" in report


def test_agent_get_formatted_report_missing_analysis():
    """Test that missing 'analysis' key defaults to 'No analysis available'."""
    from src.agent import ResearchAgent

    agent = ResearchAgent(api_key="test-key")
    agent.last_research = {
        "topic": "Test Topic",
        # Missing "analysis" key - should default to "No analysis available"
        "findings": [
            {
                "status": "success",
                "url": "https://test.com",
                "summary": "Test summary",
            },
        ],
    }
    agent.researcher.sources = ["https://test.com"]

    report = agent.get_formatted_report()

    # Verify that the default message appears when analysis is missing
    assert "No analysis available" in report
    # Verify other parts are still present
    assert "# Research Report: Test Topic" in report
    assert "## Analysis" in report
    assert "## Findings" in report
    assert "https://test.com" in report
    assert "Test summary" in report
