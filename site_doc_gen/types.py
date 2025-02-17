"""
Type definitions for site-doc-gen
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

@dataclass
class CodeSnippet:
    """A code snippet extracted from documentation"""
    language: str
    code: str
    context: str = ""  # Surrounding text/documentation
    type: str = "unknown"  # 'example', 'definition', 'output', etc.
    line_numbers: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Heading:
    """A heading in the documentation"""
    level: int
    text: str
    id: str  # Generated ID for linking
    children: List['Heading'] = field(default_factory=list)

@dataclass
class Page:
    """A single documentation page"""
    url: str
    title: str
    content: str
    code_snippets: List[CodeSnippet] = field(default_factory=list)
    headings: List[Heading] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: Optional[datetime] = None
    parent_url: Optional[str] = None  # For maintaining hierarchy

@dataclass
class Documentation:
    """Complete documentation output"""
    pages: List[Page]
    base_url: str
    generated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Convert documentation to markdown format"""
        from .markdown import MarkdownConverter
        converter = MarkdownConverter(self)
        return converter.convert()

    def to_json(self) -> Dict[str, Any]:
        """Convert documentation to JSON format"""
        return {
            "base_url": self.base_url,
            "generated_at": self.generated_at.isoformat(),
            "metadata": self.metadata,
            "pages": [
                {
                    "url": page.url,
                    "title": page.title,
                    "content": page.content,
                    "code_snippets": [
                        {
                            "language": snippet.language,
                            "code": snippet.code,
                            "context": snippet.context,
                            "type": snippet.type,
                            "metadata": snippet.metadata
                        }
                        for snippet in page.code_snippets
                    ],
                    "headings": [
                        {
                            "level": heading.level,
                            "text": heading.text,
                            "id": heading.id
                        }
                        for heading in page.headings
                    ],
                    "metadata": page.metadata,
                    "last_updated": page.last_updated.isoformat() if page.last_updated else None,
                    "parent_url": page.parent_url
                }
                for page in self.pages
            ]
        }
