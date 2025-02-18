"""
Utility functions for site-doc-gen
"""

from fnmatch import fnmatch
from typing import Union, List, TypeVar, Any, Dict, Set
from pathlib import Path
from urllib.parse import urlparse, urljoin
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from collections import defaultdict
import re
import os

T = TypeVar('T')

def format_number(num: int) -> str:
    """Format large numbers with K/M suffixes"""
    if num > 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num > 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)

def match_path(path: str, patterns: Union[str, List[str]]) -> bool:
    """Match a path against one or more glob patterns"""
    if isinstance(patterns, str):
        patterns = [patterns]
    
    # Normalize path by removing leading/trailing slashes
    path = path.strip('/')
    if not path:  # Handle root path
        path = '/'
    
    for pattern in patterns:
        if not pattern:
            continue
            
        # Normalize pattern
        pattern = pattern.strip('/')
        
        # Special case for root path
        if path == '/' and (pattern == '/' or pattern == '' or pattern == '*'):
            return True
        
        # For exact matches (no wildcards), compare directly
        if '*' not in pattern:
            if path == pattern or path.startswith(pattern + '/'):
                return True
        # For wildcard patterns, use fnmatch
        else:
            # Try matching with and without trailing /*
            if fnmatch(path, pattern) or fnmatch(path, pattern + '/*'):
                return True
    
    return False

def ensure_array(input_value: Union[T, List[T]]) -> List[T]:
    """Convert a single value or list to a list"""
    if isinstance(input_value, list):
        return input_value
    return [input_value]

async def discover_github_patterns(owner: str, repo: str) -> Dict[str, Set[str]]:
    """
    Discover URL patterns in a GitHub repository using the GitHub API.
    """
    patterns = defaultdict(set)
    github_token = os.environ.get("GITHUB_TOKEN")
    headers = {}
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    
    async def fetch_contents(path: str = ""):
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        print(f"\nFetching GitHub contents: {path or '/'}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    contents = await response.json()
                    files_found = 0
                    dirs_found = 0
                    
                    for item in contents:
                        if item["type"] == "file":
                            # Skip binary files and catch all text-based files
                            if not any(item["name"].endswith(ext) for ext in [
                                # Binary files to skip
                                ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo",
                                ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico",
                                ".mp3", ".mp4", ".avi", ".mov", ".wav",
                                ".zip", ".tar", ".gz", ".7z", ".rar",
                                ".pdf", ".doc", ".docx", ".xls", ".xlsx",
                                ".db", ".sqlite", ".sqlite3",
                                ".bin", ".dat"
                            ]):
                                file_path = item["path"]
                                patterns[file_path].add(file_path)
                                # Add directory pattern
                                dir_path = os.path.dirname(file_path)
                                if dir_path:
                                    patterns[f"{dir_path}/*"].add(file_path)
                                files_found += 1
                        elif item["type"] == "dir":
                            dir_path = item["path"]
                            patterns[f"{dir_path}/*"].add(dir_path)
                            dirs_found += 1
                            await fetch_contents(dir_path)
                    
                    if files_found or dirs_found:
                        print(f"✓ Found {files_found} files and {dirs_found} directories in {path or '/'}")
    
    await fetch_contents()
    return dict(patterns)

async def discover_url_patterns(base_url: str, max_depth: int = 2, max_urls: int = 100) -> Dict[str, Set[str]]:
    """
    Perform a quick crawl of a site to discover URL patterns.
    Returns a dictionary of patterns to sets of example URLs.
    
    Args:
        base_url: The starting URL to crawl
        max_depth: Maximum depth to crawl (default: 2)
        max_urls: Maximum number of URLs to process (default: 100)
    
    Returns:
        Dict[str, Set[str]]: Mapping of patterns to example URLs
    """
    # Check if this is a GitHub repository
    github_pattern = r"https?://github\.com/([^/]+)/([^/]+)(?:/tree/[^/]+)?"
    github_match = re.match(github_pattern, base_url)
    if github_match:
        owner, repo = github_match.group(1), github_match.group(2)
        print(f"\nDiscovering patterns for GitHub repository: {owner}/{repo}")
        return await discover_github_patterns(owner, repo)
    
    # Regular website pattern discovery
    base_domain = urlparse(base_url).netloc
    visited = set()
    patterns = defaultdict(set)
    
    async def fetch_urls(url: str, depth: int = 0):
        if depth >= max_depth or len(visited) >= max_urls or url in visited:
            return
        
        visited.add(url)
        print(f"\nDiscovering patterns at depth {depth}: {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Extract all links
                    links = soup.find_all('a', href=True)
                    new_patterns = set()
                    
                    for link in links:
                        href = link['href']
                        full_url = urljoin(url, href)
                        
                        # Skip external links and non-HTTP(S) URLs
                        if not full_url.startswith(('http://', 'https://')):
                            continue
                        parsed = urlparse(full_url)
                        if parsed.netloc != base_domain:
                            continue
                        
                        # Extract path and create pattern
                        path = parsed.path.rstrip('/')
                        if not path:
                            continue
                            
                        # Generate pattern by replacing numeric segments and UUIDs
                        segments = path.split('/')
                        pattern_segments = []
                        for segment in segments:
                            if segment.isdigit() or re.match(r'^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$', segment.lower()):
                                pattern_segments.append('*')
                            else:
                                pattern_segments.append(segment)
                        
                        pattern = '/'.join(pattern_segments)
                        if pattern.startswith('/'):
                            pattern = pattern[1:]
                        
                        # Store pattern with example
                        if pattern not in patterns:
                            new_patterns.add(pattern)
                        patterns[pattern].add(path)
                        
                        # Continue crawling if within limits
                        if len(visited) < max_urls:
                            await fetch_urls(full_url, depth + 1)
                    
                    if new_patterns:
                        print(f"Found {len(new_patterns)} new patterns")
        
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
    
    await fetch_urls(base_url)
    
    # Group and analyze patterns
    grouped_patterns = defaultdict(set)
    
    # Always include root pattern
    grouped_patterns['/'].add('/')
    
    for pattern, urls in patterns.items():
        # For single-segment paths, keep them as exact matches
        if '/' not in pattern:
            grouped_patterns[pattern].update(urls)
        # For multi-segment paths, create both exact and wildcard patterns
        else:
            # Keep the exact pattern
            grouped_patterns[pattern].update(urls)
            # Also create a wildcard pattern for the directory
            dir_pattern = re.sub(r'/[^/]+$', '/*', pattern)
            if not dir_pattern.startswith('*'):
                dir_pattern = '*/' + dir_pattern
            grouped_patterns[dir_pattern].update(urls)
    
    return dict(grouped_patterns)

def suggest_content_selector(html: str) -> str:
    """
    Analyze HTML content and suggest a content selector based on common documentation patterns.
    
    Args:
        html: HTML content to analyze
    
    Returns:
        str: Suggested CSS selector for main content
    """
    soup = BeautifulSoup(html, 'html.parser')
    
    # Common documentation content selectors
    selectors = [
        ('article.content', 10),  # ReadTheDocs style
        ('div.documentation', 10),  # Common documentation class
        ('main.content', 9),  # Common main content
        ('.markdown-body', 8),  # GitHub style
        ('#docs-content', 8),  # Common docs ID
        ('article', 5),  # Generic article
        ('main', 4),  # Generic main
    ]
    
    # Score each selector
    scores = {}
    for selector, base_score in selectors:
        elements = soup.select(selector)
        if not elements:
            continue
            
        for el in elements:
            # Calculate score based on content
            text_length = len(el.get_text())
            heading_count = len(el.find_all(['h1', 'h2', 'h3']))
            code_count = len(el.find_all(['pre', 'code']))
            
            score = base_score
            score += min(text_length / 1000, 10)  # Up to 10 points for length
            score += min(heading_count, 5)  # Up to 5 points for headings
            score += min(code_count, 5)  # Up to 5 points for code blocks
            
            scores[selector] = score
    
    if not scores:
        return None
        
    # Return highest scoring selector
    return max(scores.items(), key=lambda x: x[1])[0]
