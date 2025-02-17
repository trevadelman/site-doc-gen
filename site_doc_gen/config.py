"""
Configuration handling for site-doc-gen
"""

from dataclasses import dataclass, field
from typing import Optional, List, Union, Callable, Literal
from pathlib import Path

from .utils import ensure_array, match_path

@dataclass
class Config:
    """Configuration for the documentation generator"""
    
    # Concurrency settings
    concurrency: int = 3
    timeout: int = 30  # Seconds
    
    # Content matching
    match: Optional[List[str]] = None  # URL patterns to include
    exclude: Optional[List[str]] = None  # URL patterns to exclude
    content_selector: Optional[Union[str, Callable]] = None
    max_depth: Optional[int] = None
    
    # Limits
    max_pages: Optional[int] = None
    max_size_mb: float = 50.0  # Max size of all content
    
    # Output options
    output_format: Literal["json", "markdown"] = "markdown"
    output_dir: Path = field(default_factory=lambda: Path("output"))
    include_toc: bool = True
    preserve_code_blocks: bool = True
    split_pages: bool = False  # Whether to create separate files for each page
    create_index: bool = True  # Whether to create an index.html for split pages
    
    # Code snippet options
    code_block_markers: List[str] = field(
        default_factory=lambda: ["```", "~~~", "<pre>", "<code>"]
    )
    detect_languages: bool = True
    extract_code_context: bool = True
    
    # HTTP options
    headers: dict = field(
        default_factory=lambda: {
            "User-Agent": "site-doc-gen/0.1.0 (https://github.com/yourusername/site-doc-gen)"
        }
    )
    follow_redirects: bool = True
    verify_ssl: bool = True
    
    # Logging options
    quiet: bool = False  # Suppress informational output
    
    def __post_init__(self):
        """Validate and process configuration after initialization"""
        # Convert output_dir to Path if it's a string
        if isinstance(self.output_dir, str):
            self.output_dir = Path(self.output_dir)
        
        # Ensure match and exclude are lists
        if self.match:
            self.match = ensure_array(self.match)
        if self.exclude:
            self.exclude = ensure_array(self.exclude)
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def should_process_url(self, url: str) -> bool:
        """Check if a URL should be processed based on match/exclude patterns"""
        if self.match and not match_path(url, self.match):
            return False
        if self.exclude and match_path(url, self.exclude):
            return False
        return True
    
    def get_content_selector(self, url: str) -> Optional[str]:
        """Get the content selector for a specific URL"""
        if callable(self.content_selector):
            return self.content_selector(url)
        return self.content_selector
