# Web-Researcher-Agent

A sophisticated AI-powered web research agent that can autonomously browse the web, gather information, analyze content, and provide comprehensive research summaries.

## Features

- 🔍 **Autonomous Web Research** - Browse and research topics automatically
- 📊 **Content Analysis** - Extract and summarize key information from web pages
- 🤖 **AI-Powered** - Uses Claude AI for intelligent research and analysis
- 📝 **Structured Reports** - Generate comprehensive research reports
- 🔗 **Link Following** - Navigate multiple pages for deep research
- 💾 **Result Caching** - Optimize API calls with intelligent caching

## Project Structure

```
Web-Researcher-Agent/
├── src/
│   ├── __init__.py
│   ├── agent.py           # Main agent logic
│   ├── researcher.py      # Web research functionality
│   ├── utils.py           # Utility functions
│   └── config.py          # Configuration management
├── examples/
│   └── research_example.py
├── tests/
│   └── test_researcher.py
├── requirements.txt       # Project dependencies
└── README.md
```

## Requirements

- Python 3.8+
- Anthropic API key

## Installation

1. Clone the repository:

```bash
git clone https://github.com/sohamkundu27/Web-Researcher-Agent.git
cd Web-Researcher-Agent
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set up your environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Basic Research

```python
from src.agent import ResearchAgent

agent = ResearchAgent()
result = agent.research("Latest developments in quantum computing")
print(result)
```

### Advanced Configuration

```python
from src.agent import ResearchAgent

agent = ResearchAgent(
    model="claude-3-5-sonnet-20241022",
    max_search_results=10,
    max_depth=3
)

result = agent.research(
    topic="Climate change solutions",
    num_sources=10
)
```

## API Reference

### ResearchAgent

Main agent class for conducting research.

**Methods:**

- `research(topic: str, num_sources: int = 5) -> Dict` - Conduct research on a topic
- `summarize(urls: List[str]) -> str` - Summarize content from multiple URLs
- `get_sources() -> List[str]` - Get list of sources used in the last research

## Development

### Running Tests

```bash
pytest tests/
```

### Running Examples

```bash
python examples/research_example.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Notes

This is an experimental implementation for AgentHub S25.
