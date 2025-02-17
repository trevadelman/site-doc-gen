"""
Core documentation generation functionality
"""

import asyncio
import os
import re
from typing import Dict, List, Optional, Set, Tuple
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from pathlib import Path
from readability import Document

from .config import Config
from .types import Documentation, Page, CodeSnippet, Heading

logger = logging.getLogger(__name__)

class DocGen:
    """Main documentation generator class"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.processed_urls: Set[str] = set()
        self.base_url: Optional[str] = None
        self.base_domain: Optional[str] = None
        self.semaphore: Optional[asyncio.Semaphore] = None
        
    async def __aenter__(self):
        """Set up async context"""
        self.session = aiohttp.ClientSession(headers=self.config.headers)
        self.semaphore = asyncio.Semaphore(self.config.concurrency)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up async context"""
        if self.session:
            await self.session.close()
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to handle relative paths and fragments"""
        if not url:
            return ""
        # Remove fragments
        url = url.split("#")[0]
        # Handle relative URLs
        if self.base_url:
            url = urljoin(self.base_url, url)
        return url
    
    def _is_same_domain(self, url: str) -> bool:
        """Check if URL belongs to the same domain as base_url"""
        if not self.base_domain:
            return False
        parsed = urlparse(url)
        return parsed.netloc == self.base_domain
    
    def _parse_github_url(self, url: str) -> Optional[Tuple[str, str, str]]:
        """Parse GitHub repository URL into owner, repo, and branch.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo, branch) or None if not a GitHub URL
        """
        github_pattern = r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?"
        match = re.match(github_pattern, url)
        if match:
            owner, repo = match.group(1), match.group(2)
            branch = match.group(3) or "main"  # Default to main if no branch specified
            return owner, repo, branch
        return None
    
    async def _fetch_github_contents(
        self,
        owner: str,
        repo: str,
        path: str = ""
    ) -> List[Dict]:
        """Fetch repository contents using GitHub API"""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        # Add GitHub token if available
        headers = dict(self.session.headers)
        github_token = os.environ.get("GITHUB_TOKEN")
        if github_token:
            headers["Authorization"] = f"token {github_token}"
            if not self.config.quiet:
                logger.info("Using GitHub token for authentication")
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.json()
            else:
                logger.error(f"Error fetching {url}: {response.status}")
                return []
    
    async def _fetch_github_file(self, url: str) -> Optional[str]:
        """Fetch raw file content from GitHub"""
        headers = dict(self.session.headers)
        headers["Accept"] = "application/vnd.github.v3.raw"
        
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.text()
            else:
                logger.error(f"Error fetching {url}: {response.status}")
                return None
    
    async def _process_github_repo(
        self,
        owner: str,
        repo: str,
        branch: str
    ) -> Documentation:
        """Process a GitHub repository"""
        async def process_directory(path: str = "") -> List[Page]:
            pages = []
            contents = await self._fetch_github_contents(owner, repo, path)
            
            for item in contents:
                if item["type"] == "file":
                    if any(item["name"].endswith(ext) for ext in [".md", ".py"]):
                        content = await self._fetch_github_file(item["download_url"])
                        if content:
                            # Create a page for the file
                            is_markdown = item["name"].endswith(".md")
                            file_content = content
                            
                            if is_markdown:
                                # For markdown, parse the raw content first
                                headings = []
                                for line in file_content.split('\n'):
                                    if line.startswith('#'):
                                        level = len(line) - len(line.lstrip('#'))
                                        text = line.lstrip('#').strip()
                                        id = text.lower().replace(' ', '-')
                                        headings.append(Heading(level=level, text=text, id=id))
                                
                                # Then wrap in HTML for display
                                soup = BeautifulSoup(
                                    f"<div>{file_content}</div>",
                                    "html.parser"
                                )
                            else:
                                # Wrap code in pre/code tags
                                soup = BeautifulSoup(
                                    f'<pre><code class="language-python">{file_content}</code></pre>',
                                    "html.parser"
                                )
                                headings = []
                            
                            pages.append(Page(
                                url=item["html_url"],
                                title=item["path"],
                                content=str(soup),
                                code_snippets=[CodeSnippet(
                                    language="python" if item["name"].endswith(".py") else "markdown",
                                    code=content,
                                    context=item["path"],
                                    type="source" if item["name"].endswith(".py") else "documentation"
                                )] if not is_markdown else [],
                                headings=headings
                            ))
                
                elif item["type"] == "dir":
                    # Recursively process subdirectories
                    dir_pages = await process_directory(item["path"])
                    pages.extend(dir_pages)
            
            return pages
        
        # Process the entire repository
        pages = await process_directory()
        
        return Documentation(
            base_url=f"https://github.com/{owner}/{repo}",
            pages=pages
        )
    
    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page with error handling"""
        try:
            async with self.semaphore:
                async with self.session.get(
                    url,
                    timeout=self.config.timeout,
                    ssl=self.config.verify_ssl,
                    allow_redirects=self.config.follow_redirects
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to fetch {url}: {response.status}")
                        return None
                    
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type.lower():
                        logger.warning(f"Skipping non-HTML content at {url}")
                        return None
                    
                    return await response.text()
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def _extract_code_snippets(self, soup: BeautifulSoup) -> List[CodeSnippet]:
        """Extract code snippets from HTML content"""
        snippets = []
        
        # Handle markdown-style code blocks
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                # Try to detect language from class
                classes = code.get("class", [])
                language = next((
                    cls.replace("language-", "")
                    for cls in classes
                    if cls.startswith("language-")
                ), "text")
                
                snippets.append(CodeSnippet(
                    language=language,
                    code=code.get_text(),
                    context=pre.parent.get_text()[:100].split('\n')[0],  # Get first line of context
                    type="example" if "example" in pre.parent.get_text().lower() else "unknown"
                ))
        
        return snippets
    
    def _extract_headings(self, soup: BeautifulSoup) -> List[Heading]:
        """Extract heading hierarchy from HTML content"""
        headings = []
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
            level = int(tag.name[1])
            text = tag.get_text().strip()
            # Generate ID from text
            id = text.lower().replace(" ", "-")
            headings.append(Heading(level=level, text=text, id=id))
        return headings
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract links from HTML content"""
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = self._normalize_url(urljoin(base_url, href))
            if (
                full_url
                and self._is_same_domain(full_url)
                and self.config.should_process_url(full_url)
            ):
                links.append(full_url)
        return links
    
    async def _process_page(self, url: str) -> Optional[Page]:
        """Process a single page"""
        if url in self.processed_urls:
            return None
        
        self.processed_urls.add(url)
        print(f"Fetching: {url}")
        html = await self._fetch_page(url)
        if not html:
            print(f"Failed to fetch: {url}")
            return None
        
        # Initial cleanup with BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove unwanted elements
        for selector in ["script", "style", "iframe", "noscript", "meta", "link", "svg", "img", "video"]:
            for element in soup.find_all(selector):
                element.decompose()
        
        # Get title from page
        title = soup.title.string if soup.title else url
        
        # Initialize content_soup
        content_soup = None
        
        # Extract content based on selector if provided
        content_selector = self.config.get_content_selector(url)
        if content_selector:
            content_element = soup.select_one(content_selector)
            if content_element:
                # Keep the original content structure
                content_soup = content_element
        
        # If no content found through selector, use readability
        if not content_soup:
            doc = Document(str(soup))
            article = doc.summary()
            content_soup = BeautifulSoup(article, "html.parser")
        
        return Page(
            url=url,
            title=title or url,
            content=str(content_soup),
            code_snippets=self._extract_code_snippets(content_soup),
            headings=self._extract_headings(content_soup)
        )
    
    def _create_index_html(self, docs: Documentation, output_dir: Path) -> None:
        """Create an index.html file with links to all pages"""
        index_content = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<title>Documentation</title>",
            "<style>",
            "body { font-family: system-ui, -apple-system, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }",
            "a { color: #0066cc; text-decoration: none; }",
            "a:hover { text-decoration: underline; }",
            ".toc { margin-left: 1rem; }",
            ".depth-0 { margin-left: 0; }",
            ".depth-1 { margin-left: 2rem; }",
            ".depth-2 { margin-left: 4rem; }",
            ".depth-3 { margin-left: 6rem; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>Documentation</h1>",
            f"<p>Generated from: {docs.base_url}</p>",
            "<h2>Table of Contents</h2>",
            "<div class='toc'>"
        ]
        
        for page in docs.pages:
            title = page.title or page.url.split('/')[-1]
            safe_filename = title.lower().replace(' ', '-').replace('/', '-') + ".md"
            depth = page.url.count('/') - 3
            index_content.append(f"<p class='depth-{depth}'><a href='docs/{safe_filename}'>{title}</a></p>")
        
        index_content.extend([
            "</div>",
            "</body>",
            "</html>"
        ])
        
        index_file = output_dir / "index.html"
        index_file.write_text("\n".join(index_content))
    
    def _save_documentation(self, docs: Documentation) -> None:
        """Save documentation to files based on configuration"""
        # Create site-specific output directory
        github_info = self._parse_github_url(docs.base_url)
        if github_info:
            owner, repo, _ = github_info
            site_name = f"github_{owner}_{repo}"
        else:
            site_name = urlparse(docs.base_url).netloc.replace('.', '_')
        
        site_dir = self.config.output_dir / site_name
        site_dir.mkdir(exist_ok=True)
        
        if self.config.split_pages:
            # Create docs directory
            docs_dir = site_dir / "docs"
            docs_dir.mkdir(exist_ok=True)
            
            # Save each page as a separate file
            for page in docs.pages:
                title = page.title or page.url.split('/')[-1]
                safe_filename = title.lower().replace(' ', '-').replace('/', '-') + ".md"
                file_path = docs_dir / safe_filename
                
                # Generate page content
                page_content = []
                
                # Add header
                page_content.extend([
                    f"# {title}",
                    "",
                    f"Source: {page.url}",
                    "",
                    "[Back to Index](../index.html)",
                    ""
                ])
                
                # Add content sections
                content_soup = BeautifulSoup(page.content, "html.parser")
                elements = content_soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre"])
                current_section = []
                
                for element in elements:
                    if element.name.startswith('h'):
                        if current_section:
                            page_content.extend(current_section)
                            page_content.append("")
                        current_section = []
                        level = int(element.name[1])
                        page_content.append(f"{'#' * level} {element.get_text().strip()}")
                    elif element.name == 'p':
                        text = element.get_text().strip()
                        if text:
                            current_section.append(text)
                            current_section.append("")
                    elif element.name == 'pre':
                        if current_section:
                            page_content.extend(current_section)
                            page_content.append("")
                        current_section = []
                        code = element.find("code")
                        if code:
                            language = "text"
                            if code.get("class"):
                                lang_class = next((cls for cls in code.get("class", []) if cls.startswith("language-")), None)
                                if lang_class:
                                    language = lang_class.replace("language-", "")
                            page_content.extend([
                                f"```{language}",
                                code.get_text().strip(),
                                "```",
                                "",
                                f"Context: {element.parent.get_text()[:100].split('\n')[0].strip()}",
                                ""
                            ])
                
                if current_section:
                    page_content.extend(current_section)
                    page_content.append("")
                
                # Add footer with back to index link
                page_content.extend([
                    "---",
                    "",
                    "[Back to Index](../index.html)"
                ])
                
                # Write page file
                file_path.write_text("\n".join(page_content))
            
            # Create index.html if enabled
            if self.config.create_index:
                self._create_index_html(docs, site_dir)
        else:
            # Save as a single file
            output_file = site_dir / "documentation.md"
            content = []
            
            # Add header
            content.extend([
                "# Documentation",
                f"Generated from: {docs.base_url}",
                "",
                "## Table of Contents",
                ""
            ])
            
            # Generate TOC
            for page in docs.pages:
                title = page.title or page.url.split('/')[-1]
                indent = "  " * (page.url.count('/') - 3)
                content.append(f"{indent}- [{title}](#{title.lower().replace(' ', '-')})")
            
            content.extend(["", "## Contents", ""])
            
            # Add page contents
            for page in docs.pages:
                title = page.title or page.url.split('/')[-1]
                content.extend([
                    f"### {title}",
                    "",
                    f"Source: {page.url}",
                    ""
                ])
                
                # Add content sections
                content_soup = BeautifulSoup(page.content, "html.parser")
                elements = content_soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre"])
                current_section = []
                
                for element in elements:
                    if element.name.startswith('h'):
                        if current_section:
                            content.extend(current_section)
                            content.append("")
                        current_section = []
                        level = int(element.name[1])
                        content.append(f"{'#' * level} {element.get_text().strip()}")
                    elif element.name == 'p':
                        text = element.get_text().strip()
                        if text:
                            current_section.append(text)
                            current_section.append("")
                    elif element.name == 'pre':
                        if current_section:
                            content.extend(current_section)
                            content.append("")
                        current_section = []
                        code = element.find("code")
                        if code:
                            language = "text"
                            if code.get("class"):
                                lang_class = next((cls for cls in code.get("class", []) if cls.startswith("language-")), None)
                                if lang_class:
                                    language = lang_class.replace("language-", "")
                            content.extend([
                                f"```{language}",
                                code.get_text().strip(),
                                "```",
                                "",
                                f"Context: {element.parent.get_text()[:100].split('\n')[0].strip()}",
                                ""
                            ])
                
                if current_section:
                    content.extend(current_section)
                    content.append("")
                
                content.append("---\n")
            
            output_file.write_text("\n".join(content))
    
    async def process_site(self, url: str) -> Documentation:
        """Process a website or GitHub repository"""
        # Check if this is a GitHub repository
        github_info = self._parse_github_url(url)
        if github_info:
            owner, repo, branch = github_info
            if not self.config.quiet:
                logger.info(f"Processing GitHub repository: {owner}/{repo} ({branch})")
            docs = await self._process_github_repo(owner, repo, branch)
        else:
            # Process as a regular website
            self.base_url = url
            self.base_domain = urlparse(url).netloc
            
            # Start with the initial URL
            pages = []
            to_process = [url]
            
            while to_process and (
                not self.config.max_pages
                or len(pages) < self.config.max_pages
            ):
                current_url = to_process.pop(0)
                page = await self._process_page(current_url)
                
                if page:
                    print(f"Successfully processed: {current_url}")
                    pages.append(page)
                    
                    # Extract and add new URLs to process
                    soup = BeautifulSoup(page.content, "html.parser")
                    new_urls = self._extract_links(soup, current_url)
                    to_process.extend(
                        url for url in new_urls
                        if url not in self.processed_urls
                    )
            
            docs = Documentation(
                pages=pages,
                base_url=self.base_url
            )
        
        # Save documentation based on configuration
        self._save_documentation(docs)
        
        return docs
