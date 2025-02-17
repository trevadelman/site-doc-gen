"""
Test core documentation generation functionality
"""

import pytest
from pathlib import Path
import json
import os
from site_doc_gen import DocGen, Config

@pytest.fixture
def config():
    """Create a test configuration"""
    return Config(
        concurrency=3,
        match=[
            "*.md",
            "**/*.md",
            "*.py",
            "**/*.py"
        ],
        max_pages=20,
        output_format="markdown",
        headers={
            "User-Agent": "site-doc-gen/0.1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }
    )

@pytest.mark.asyncio
async def test_process_github_repo(config):
    """Test processing a real GitHub repository"""
    # Using a real repository that we know exists
    async with DocGen(config) as doc_gen:
        docs = await doc_gen.process_site("https://github.com/trevadelman/autonomous-agent-framework")
    
    assert docs.base_url == "https://github.com/trevadelman/autonomous-agent-framework"
    assert len(docs.pages) > 0
    
    # Verify we have both markdown and Python files
    md_pages = [p for p in docs.pages if p.title.endswith(".md")]
    py_pages = [p for p in docs.pages if p.title.endswith(".py")]
    
    assert len(md_pages) > 0, "Should have found markdown files"
    assert len(py_pages) > 0, "Should have found Python files"
    
    # Verify markdown content
    readme = next((p for p in md_pages if "README.md" in p.title), None)
    assert readme is not None, "Should have found README.md"
    assert "Autonomous Agent Framework" in readme.content
    assert len(readme.headings) > 0, "README should have headings"
    
    # Verify Python content
    init_py = next((p for p in py_pages if "__init__.py" in p.title), None)
    assert init_py is not None, "Should have found __init__.py"
    assert len(init_py.code_snippets) > 0, "Should have code snippets"
    assert init_py.code_snippets[0].language == "python"

@pytest.mark.asyncio
async def test_github_token_usage(config):
    """Test GitHub API with token authentication"""
    # Skip if no token available
    if "GITHUB_TOKEN" not in os.environ:
        pytest.skip("GITHUB_TOKEN not set")
    
    async with DocGen(config) as doc_gen:
        docs = await doc_gen.process_site("https://github.com/trevadelman/autonomous-agent-framework")
    
    assert docs.base_url == "https://github.com/trevadelman/autonomous-agent-framework"
    assert len(docs.pages) > 0

@pytest.mark.asyncio
async def test_github_url_parsing(config):
    """Test GitHub URL parsing"""
    doc_gen = DocGen(config)
    
    # Test main branch URL
    result = doc_gen._parse_github_url("https://github.com/trevadelman/autonomous-agent-framework")
    assert result == ("trevadelman", "autonomous-agent-framework", "main")
    
    # Test specific branch URL
    result = doc_gen._parse_github_url("https://github.com/trevadelman/autonomous-agent-framework/tree/develop")
    assert result == ("trevadelman", "autonomous-agent-framework", "develop")
    
    # Test non-GitHub URL
    result = doc_gen._parse_github_url("https://example.com")
    assert result is None
