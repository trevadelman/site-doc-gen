#!/usr/bin/env python3
"""
Example script to fetch documentation from a GitHub repository
"""

import asyncio
from pathlib import Path
from site_doc_gen import DocGen, Config

async def main():
    # Create configuration
    config = Config(
        concurrency=3,
        # Match markdown and Python files
        match=["*.md", "*.py"],
        output_format="markdown",
        headers={
            "User-Agent": "site-doc-gen/0.1.0",
            "Accept": "application/vnd.github.v3+json"
        },
        # Enable split pages with index
        split_pages=True,
        create_index=True,
        # Preserve code blocks for Python files
        preserve_code_blocks=True
    )
    
    print("Fetching documentation from GitHub repository...")
    
    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    async with DocGen(config) as doc_gen:
        # Process GitHub repository
        docs = await doc_gen.process_site("https://github.com/trevadelman/autonomous-agent-framework")
    
    # Documentation is automatically saved based on configuration
    
    # Print stats
    print(f"\nStats:")
    print(f"- Pages processed: {len(docs.pages)}")
    print(f"- Code snippets extracted: {sum(len(p.code_snippets) for p in docs.pages)}")
    print(f"- Headings found: {sum(len(p.headings) for p in docs.pages)}")

if __name__ == "__main__":
    asyncio.run(main())
