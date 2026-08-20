"""Setup configuration for Web Researcher Agent."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="web-researcher-agent",
    version="0.1.0",
    author="Soham Kundu",
    description="AI-powered web research agent using Claude AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sohamkundu27/Web-Researcher-Agent",
    packages=find_packages(),
    package_data={"src": ["py.typed"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "anthropic>=0.31.0",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=23.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
        ]
    },
)
