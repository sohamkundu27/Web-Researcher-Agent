"""Utility functions for Web Researcher Agent."""

import hashlib
import re
from typing import List, Dict, Any, TypedDict, Union, Literal
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


class FetchUrlSuccess(TypedDict):
    """Successful URL fetch response."""

    status: Literal["success"]
    url: str
    content: str
    status_code: int
    headers: Dict[str, Any]


class FetchUrlError(TypedDict):
    """Error URL fetch response."""

    status: Literal["error"]
    url: str
    error: str


FetchUrlResult = Union[FetchUrlSuccess, FetchUrlError]


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not isinstance(url, str):
        raise TypeError(f"url must be a string, got {type(url).__name__}")
    parsed = urlparse(url)
    return parsed.netloc


def is_valid_url(url: str) -> bool:
    """Validate if string is a valid URL."""
    if not isinstance(url, str):
        return False
    url_pattern = r"^https?://"
    return re.match(url_pattern, url) is not None


def sanitize_text(text: str) -> str:
    """Clean and normalize text content."""
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")
    text = " ".join(text.split())
    text = re.sub(r"[^\w\s.,!?-]", "", text)
    text = " ".join(text.split())
    return text.strip()


def extract_text_from_html(html: str, max_length: int = 5000) -> str:
    """Extract clean text from HTML content."""
    if not isinstance(max_length, int) or max_length <= 0:
        raise ValueError(f"max_length must be a positive integer, got {max_length}")
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text
        text = soup.get_text()

        # Clean up text
        text = sanitize_text(text)

        # Limit length
        return text[:max_length]
    except ValueError:
        raise
    except Exception as e:
        print(f"Error extracting text from HTML: {e}")
        return ""


def fetch_url_content(url: str, timeout: int = 10) -> FetchUrlResult:
    """Fetch and parse content from URL.

    Retrieves the content of a URL using HTTP GET request and extracts
    clean text from the HTML response. Handles timeouts and HTTP errors gracefully.

    Args:
        url: The URL to fetch content from (must start with http:// or https://)
        timeout: Request timeout in seconds (default: 10, must be positive)

    Returns:
        A dictionary containing the result of the fetch operation.
        On success (status == "success"):
            - status: "success"
            - url: The requested URL
            - content: Extracted and cleaned text from HTML (limited to 5000 chars)
            - status_code: HTTP status code (e.g., 200)
            - headers: Response headers as dict
        On error (status == "error"):
            - status: "error"
            - url: The requested URL
            - error: Error message describing what went wrong

    Raises:
        TypeError: If url is not a string or timeout is not an integer
        ValueError: If url is not a valid HTTP(S) URL or timeout is not positive
    """
    if not isinstance(url, str):
        raise TypeError(f"url must be a string, got {type(url).__name__}")
    if not is_valid_url(url):
        raise ValueError(f"url must be a valid HTTP(S) URL, got '{url}'")
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError(f"timeout must be a positive integer, got {timeout}")

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        return {
            "status": "success",
            "url": url,
            "content": extract_text_from_html(response.text),
            "status_code": response.status_code,
            "headers": dict(response.headers),
        }
    except requests.RequestException as e:
        return {
            "status": "error",
            "url": url,
            "error": str(e),
        }


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks for batch processing.

    Divides text into fixed-size chunks with optional overlap between consecutive chunks.
    Overlapping regions preserve context across chunk boundaries. Empty chunks are filtered out.

    Args:
        text: The text to chunk (must be a string)
        chunk_size: Size of each chunk in characters (default: 1000, must be positive)
        overlap: Number of characters to overlap between consecutive chunks (default: 100,
                 must be non-negative and less than chunk_size)

    Returns:
        A list of text chunks, each at most chunk_size characters. Empty chunks are excluded.

    Raises:
        TypeError: If text is not a string
        ValueError: If chunk_size is not a positive integer, overlap is not a non-negative integer,
                   or overlap is >= chunk_size
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError(f"chunk_size must be a positive integer, got {chunk_size}")
    if not isinstance(overlap, int) or overlap < 0:
        raise ValueError(f"overlap must be a non-negative integer, got {overlap}")
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )

    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i : i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def hash_content(content: str) -> str:
    """Generate hash of content for caching.

    Args:
        content: The content to hash (must be a string)

    Returns:
        A 64-character hexadecimal SHA256 hash of the content

    Raises:
        TypeError: If content is not a string
    """
    if not isinstance(content, str):
        raise TypeError(f"content must be a string, got {type(content).__name__}")
    return hashlib.sha256(content.encode()).hexdigest()


def format_sources(sources: List[str]) -> str:
    """Format sources list as markdown."""
    if not isinstance(sources, list):
        raise TypeError(f"sources must be a list, got {type(sources).__name__}")
    if not sources:
        return ""

    for i, source in enumerate(sources):
        if not isinstance(source, str):
            raise TypeError(
                f"all sources must be strings, item at index {i} is {type(source).__name__}"
            )

    formatted = "## Sources\n\n"
    for i, source in enumerate(sources, 1):
        formatted += f"{i}. [{extract_domain(source)}]({source})\n"

    return formatted


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries.

    Recursively merges dict2 into dict1, combining nested dictionaries while
    preserving all values. Non-dict values in dict2 overwrite values in dict1.
    Input dictionaries are not modified.

    Args:
        dict1: The base dictionary to merge into
        dict2: The dictionary whose values are merged into dict1

    Returns:
        A new dictionary with merged values, where dict2 values take precedence
        in case of conflicts at the same key level. Nested dictionaries are
        recursively merged rather than replaced.

    Raises:
        TypeError: If dict1 or dict2 is not a dictionary
    """
    if not isinstance(dict1, dict):
        raise TypeError(f"dict1 must be a dictionary, got {type(dict1).__name__}")
    if not isinstance(dict2, dict):
        raise TypeError(f"dict2 must be a dictionary, got {type(dict2).__name__}")

    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
