"""
site-doc-gen - A Python-based documentation site crawler and content extractor
"""

from .core import DocGen
from .config import Config
from .types import Page, CodeSnippet, Heading

__version__ = "0.1.0"
__all__ = ["DocGen", "Config", "Page", "CodeSnippet", "Heading"]
