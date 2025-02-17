"""
Markdown conversion and formatting utilities
"""

from typing import List, Optional
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from .types import Documentation, Page, CodeSnippet, Heading

class MarkdownConverter:
    """Convert documentation to markdown format"""
    
    def __init__(self, docs: Documentation):
        self.docs = docs
    
    def _generate_toc(self, headings: List[Heading], level: int = 0) -> str:
        """Generate table of contents from headings"""
        toc = []
        indent = "  " * level
        
        for heading in headings:
            # Create link to heading
            link = f"[{heading.text}](#{heading.id})"
            toc.append(f"{indent}- {link}")
            
            # Add child headings if any
            if heading.children:
                toc.append(self._generate_toc(heading.children, level + 1))
        
        return "\n".join(toc)
    
    def _format_code_snippet(self, snippet: CodeSnippet) -> str:
        """Format a code snippet with language and context"""
        parts = []
        
        # Add context if available
        if snippet.context:
            parts.append(snippet.context.strip())
            parts.append("")  # Empty line before code
        
        # Add code block
        lang_tag = snippet.language if snippet.language != "text" else ""
        parts.extend([
            f"```{lang_tag}",
            snippet.code.strip(),
            "```"
        ])
        
        return "\n".join(parts)
    
    def _convert_html_to_markdown(self, html: str) -> str:
        """Convert HTML to markdown while preserving code blocks"""
        return md(html, heading_style="ATX", bullets="-", code_language_callback=lambda _: "")
    
    def _format_page(self, page: Page) -> str:
        """Format a single page as markdown"""
        parts = []
        
        # Add title
        parts.extend([
            f"# {page.title}",
            ""
        ])
        
        # Add table of contents if page has headings
        if page.headings:
            parts.extend([
                "## Table of Contents",
                "",
                self._generate_toc(page.headings),
                "",
                "---",
                ""
            ])
        
        # Convert main content
        content = self._convert_html_to_markdown(page.content)
        parts.append(content)
        
        # Add code snippets section if any
        if page.code_snippets:
            parts.extend([
                "",
                "## Code Snippets",
                ""
            ])
            
            for snippet in page.code_snippets:
                parts.append(self._format_code_snippet(snippet))
                parts.append("")  # Empty line between snippets
        
        return "\n".join(parts)
    
    def convert(self) -> str:
        """Convert entire documentation to markdown"""
        parts = []
        
        # Add main title
        parts.extend([
            f"# {self.docs.base_url} Documentation",
            "",
            f"Generated at: {self.docs.generated_at.isoformat()}",
            "",
            "---",
            ""
        ])
        
        # Process each page
        for page in self.docs.pages:
            parts.append(self._format_page(page))
            parts.extend([
                "",
                "---",
                ""
            ])
        
        return "\n".join(parts)
