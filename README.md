# site-doc-gen

A Python-based documentation site crawler and content extractor, inspired by siteFetch.

## Core Features

### Content Extraction
- Concurrent page fetching using `aiohttp`
- Smart content selection with configurable CSS selectors
- HTML to Markdown conversion preserving structure
- Link crawling within specified domain
- Heading hierarchy preservation
- Table of contents generation
- Site-specific output directories
- Split-page mode with navigation

### Code Snippet Handling
- Detection of code blocks with language markers
- Preservation of syntax highlighting information
- Context retention (surrounding documentation)
- Support for multiple code block formats:
  - Markdown-style (```language)
  - HTML pre/code tags with class hints
  - Documentation-specific formats

### Configuration Options
```python
@dataclass
class Config:
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
```

### Output Formats

1. Single File Mode:
   - Generates a single markdown file containing all documentation
   - Includes table of contents with anchor links
   - Preserves code blocks with language information
   - Maintains heading hierarchy

2. Split Pages Mode:
   - Creates a site-specific directory (e.g., `output/ai_pydantic_dev/`)
   - Generates individual markdown files for each page
   - Creates an index.html with a hierarchical table of contents
   - Adds navigation links between pages
   - Preserves original URL structure in filenames

### Directory Structure

When using split pages mode:
```
output/
└── domain_name/
    ├── index.html
    └── docs/
        ├── page1.md
        ├── page2.md
        └── ...
```

## Usage Examples

### Basic Usage
```python
from site_doc_gen import DocGen, Config

async def main():
    # Basic configuration
    config = Config(
        concurrency=3,
        match=["*/api/*"],
        include_toc=True
    )
    
    async with DocGen(config) as doc_gen:
        # Generate documentation
        docs = await doc_gen.process_site("https://ai.pydantic.dev/")

if __name__ == "__main__":
    asyncio.run(main())
```

### Split Pages Mode
```python
from site_doc_gen import DocGen, Config
from pathlib import Path

async def main():
    # Enable split pages mode
    config = Config(
        concurrency=3,
        match=["*", "**/*", "/docs/*", "/api/*"],
        output_dir=Path("output"),
        split_pages=True,
        create_index=True,
        content_selector="article.bd-article"  # Site-specific selector
    )
    
    async with DocGen(config) as doc_gen:
        # Each site's docs will be in its own subdirectory
        docs = await doc_gen.process_site("https://ai.pydantic.dev/")

if __name__ == "__main__":
    asyncio.run(main())
```

### Command Line Usage
```bash
# Generate single file documentation
python -m site_doc_gen https://ai.pydantic.dev/ --output docs.md

# Generate split pages with index
python -m site_doc_gen https://ai.pydantic.dev/ --split-pages --create-index
```

## Dependencies

```toml
[dependencies]
aiohttp = "^3.8.0"
beautifulsoup4 = "^4.9.3"
markdown = "^3.3.4"
pydantic = "^2.0.0"
pygments = "^2.10.0"
readability-lxml = "^0.8.1"
```

## Development Status

### Completed Features
- [x] Project structure
- [x] Basic content extraction
- [x] HTML to Markdown conversion
- [x] Concurrent fetching
- [x] Configuration system
- [x] Code block detection
- [x] Language detection
- [x] Context preservation
- [x] Split pages mode
- [x] Site-specific directories
- [x] Navigation links
- [x] Index generation

### Planned Features
- [ ] PDF documentation support
- [ ] Advanced code analysis
- [ ] Type information extraction
- [ ] Function signature parsing
- [ ] Example code validation
- [ ] Cross-reference generation

## Testing

```bash
# Run test suite
pytest tests/

# Test with example sites
python examples/fetch_pydantic.py  # Fetches Pydantic AI docs
python examples/fetch_github.py    # Fetches GitHub repository docs
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see LICENSE file for details
