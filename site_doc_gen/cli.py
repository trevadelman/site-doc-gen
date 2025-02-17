"""
Command-line interface for site-doc-gen
"""

import asyncio
import argparse
import sys
from pathlib import Path
import logging
from typing import Optional
import json

from .core import DocGen
from .config import Config

logger = logging.getLogger(__name__)

def setup_logging(verbose: bool):
    """Configure logging based on verbosity"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Generate documentation from websites with code snippet extraction"
    )
    
    parser.add_argument(
        "url",
        help="URL of the documentation site to process"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: output.md or output.json)",
        type=Path,
        default=None
    )
    
    parser.add_argument(
        "-f", "--format",
        help="Output format (default: markdown)",
        choices=["markdown", "json"],
        default="markdown"
    )
    
    parser.add_argument(
        "-c", "--concurrency",
        help="Number of concurrent requests (default: 3)",
        type=int,
        default=3
    )
    
    parser.add_argument(
        "--match",
        help="URL patterns to include (can be specified multiple times)",
        action="append",
        default=None
    )
    
    parser.add_argument(
        "--exclude",
        help="URL patterns to exclude (can be specified multiple times)",
        action="append",
        default=None
    )
    
    parser.add_argument(
        "--selector",
        help="CSS selector for main content",
        default=None
    )
    
    parser.add_argument(
        "--max-pages",
        help="Maximum number of pages to process",
        type=int,
        default=None
    )
    
    parser.add_argument(
        "-v", "--verbose",
        help="Enable verbose logging",
        action="store_true"
    )
    
    return parser

async def main(args: Optional[list] = None) -> int:
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args(args)
    
    setup_logging(args.verbose)
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = Path(f"output.{args.format}")
    
    # Create configuration
    config = Config(
        concurrency=args.concurrency,
        match=args.match,
        exclude=args.exclude,
        content_selector=args.selector,
        max_pages=args.max_pages,
        output_format=args.format
    )
    
    try:
        # Process site
        doc_gen = DocGen(config)
        docs = await doc_gen.process_site(args.url)
        
        # Generate output
        if args.format == "json":
            output = json.dumps(docs.to_json(), indent=2)
        else:
            output = docs.to_markdown()
        
        # Write output
        output_path.write_text(output)
        logger.info(f"Documentation written to {output_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error processing site: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

def run():
    """Entry point for console script"""
    sys.exit(asyncio.run(main()))

if __name__ == "__main__":
    run()
