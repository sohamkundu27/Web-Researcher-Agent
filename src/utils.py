"""Utility functions for Web Researcher Agent."""

import hashlib
import json
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc


def is_valid_url(url: str) -> bool:
    """Validate if string is a valid URL."""
    url_pattern = r"^https?://"
    return re.match(url_pattern, url) is not None


def sanitize_text(text: str) -> str:
    """Clean and normalize text content."""
    # Remove extra whitespace
    text = " ".join(text.split())
    # Remove special characters but keep basic punctuation
    text = re.sub(r"[^\w\s.,!?-]", "", text)
    return text.strip()


def extract_text_from_html(html: str, max_length: int = 5000) -> str:
    """Extract clean text from HTML content."""
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
    except Exception as e:
        print(f"Error extracting text from HTML: {e}")
        return ""


def fetch_url_content(url: str, timeout: int = 10) -> Dict[str, Any]:
    """Fetch and parse content from URL."""
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
    """Split text into overlapping chunks."""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i : i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def hash_content(content: str) -> str:
    """Generate hash of content for caching."""
    return hashlib.sha256(content.encode()).hexdigest()


def format_sources(sources: List[str]) -> str:
    """Format sources list as markdown."""
    if not sources:
        return ""

    formatted = "## Sources\n\n"
    for i, source in enumerate(sources, 1):
        formatted += f"{i}. [{extract_domain(source)}]({source})\n"

    return formatted


def merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result
