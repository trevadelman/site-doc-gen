#!/usr/bin/env python3
"""
Example script to fetch documentation from Pydantic's website
"""

import asyncio
from pathlib import Path
from bs4 import BeautifulSoup
from site_doc_gen import DocGen, Config

async def main():
    # Create configuration
    config = Config(
        concurrency=3,
        match=[
            "*",
            "**/*",
            "/",
            "/docs/*",
            "/api/*",
            "/reference/*",
            "/examples/*"
        ],
        max_pages=20,
        output_format="markdown",
        headers={
            "User-Agent": "site-doc-gen/0.1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        },
        # Pydantic uses article tag for main content
        content_selector="article.bd-article",
        # Enable split pages with index
        split_pages=True,
        create_index=True
    )
    
    print("Fetching documentation from Pydantic website...")
    
    # Create output directory
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    async with DocGen(config) as doc_gen:
        docs = await doc_gen.process_site("https://ai.pydantic.dev/")
    
    # Documentation is automatically saved based on configuration
    
    # Print stats
    print(f"\nStats:")
    print(f"- Pages processed: {len(docs.pages)}")
    print(f"- Code snippets extracted: {sum(len(p.code_snippets) for p in docs.pages)}")
    print(f"- Headings found: {sum(len(p.headings) for p in docs.pages)}")

if __name__ == "__main__":
    asyncio.run(main())
