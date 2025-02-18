from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
import asyncio
from pathlib import Path
import sys
import json
import time
import shutil
from datetime import datetime
from urllib.parse import urlparse
from site_doc_gen import DocGen, Config
from site_doc_gen.utils import discover_url_patterns
import os

# Get the absolute path to the site-doc-gen directory
ROOT_DIR = Path(__file__).parent.parent.absolute()
OUTPUT_DIR = ROOT_DIR / 'output'

app = Flask(__name__, static_folder=None)  # Disable default static folder
app.secret_key = os.urandom(24)
app.config['PROPAGATE_EXCEPTIONS'] = True  # For better async error handling

# Ensure the output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

def validate_url(url):
    """Validate URL format and accessibility"""
    if not url:
        return False, "URL is required"
    
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return False, "Invalid URL format. Must include protocol (http:// or https://)"
        
        if not (result.scheme == 'http' or result.scheme == 'https'):
            return False, "URL must use HTTP or HTTPS protocol"
            
        return True, None
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"

def count_pages(site_dir):
    """Count total number of generated pages"""
    count = 0
    docs_dir = site_dir / 'docs'
    if docs_dir.exists():
        count = sum(1 for f in docs_dir.glob('**/*') if f.is_file())
    return count

def get_directory_size(site_dir):
    """Get total size of generated documentation"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(site_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total += os.path.getsize(fp)
    return total

@app.route('/discover-patterns', methods=['POST'])
async def discover_patterns():
    """Discover URL patterns from a given URL"""
    url = request.json.get('url')
    is_valid, error_msg = validate_url(url)
    
    if not is_valid:
        return jsonify({'error': error_msg}), 400
    
    try:
        patterns = await discover_url_patterns(url, max_depth=3, max_urls=200)
        
        # Format patterns for display
        formatted_patterns = []
        for pattern, urls in patterns.items():
            formatted_patterns.append({
                'pattern': pattern,
                'example_urls': list(urls)[:3],  # Show up to 3 examples
                'total_urls': len(urls)
            })
        
        # Sort by number of URLs, most frequent first
        formatted_patterns.sort(key=lambda x: x['total_urls'], reverse=True)
        
        return jsonify({
            'patterns': formatted_patterns,
            'total_patterns': len(formatted_patterns),
            'total_urls': sum(p['total_urls'] for p in formatted_patterns)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        url = request.form.get('url')
        is_valid, error_msg = validate_url(url)
        
        if not is_valid:
            flash(error_msg, 'error')
            return redirect(url_for('home'))
        
        # Get patterns from form
        patterns_json = request.form.get('patterns')
        patterns = []
        if patterns_json:
            try:
                patterns_data = json.loads(patterns_json)
                patterns = [p['pattern'] for p in patterns_data if p.get('selected', False)]
            except json.JSONDecodeError:
                flash('Error parsing selected patterns', 'error')
                return redirect(url_for('home'))
        
        config = Config(
            concurrency=int(request.form.get('concurrency', 3)),
            max_pages=int(request.form.get('max_pages', 0)) or None,
            match=patterns if patterns else None,
            content_selector=request.form.get('content_selector'),
            split_pages=bool(request.form.get('split_pages')),
            create_index=bool(request.form.get('create_index')),
            preserve_code_blocks=bool(request.form.get('preserve_code_blocks')),
            output_format=request.form.get('output_format', 'markdown')
        )
        
        start_time = time.time()
        
        try:
            print("\nStarting documentation generation...")
            print(f"URL: {url}")
            print(f"Selected patterns: {patterns if patterns else 'None'}")
            
            async def process():
                print("\nInitializing DocGen with config:")
                print(f"- Concurrency: {config.concurrency}")
                print(f"- Max pages: {config.max_pages}")
                print(f"- Match patterns: {config.match}")
                print(f"- Content selector: {config.content_selector}")
                print(f"- Split pages: {config.split_pages}")
                
                async with DocGen(config) as doc_gen:
                    print("\nProcessing site...")
                    await doc_gen.process_site(url)
                    
                    # Save metadata
                    site_name = url.replace('https://', '').replace('http://', '')
                    if 'github.com' in site_name:
                        parts = site_name.split('/')
                        if len(parts) >= 3:
                            site_name = f"github_{parts[1]}_{parts[2]}"
                    else:
                        site_name = site_name.split('/')[0].replace('.', '_')
                    
                    site_dir = OUTPUT_DIR / site_name
                    metadata_file = site_dir / 'metadata.json'
                    
                    # Enhanced metadata
                    metadata = {
                        'source_url': url,
                        'version': '1.0.0',
                        'generation_info': {
                            'started_at': datetime.fromtimestamp(start_time).isoformat(),
                            'completed_at': datetime.fromtimestamp(time.time()).isoformat(),
                            'duration_seconds': round(time.time() - start_time, 2)
                        },
                        'stats': {
                            'total_pages': count_pages(site_dir),
                            'total_size_bytes': get_directory_size(site_dir)
                        },
                        'config_used': {
                            'concurrency': config.concurrency,
                            'max_pages': config.max_pages,
                            'match': config.match,
                            'content_selector': config.content_selector,
                            'split_pages': config.split_pages,
                            'create_index': config.create_index,
                            'preserve_code_blocks': config.preserve_code_blocks,
                            'output_format': config.output_format
                        }
                    }
                    
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
        
            asyncio.run(process())
            flash('Documentation generated successfully!', 'success')
            return redirect(url_for('docs'))
            
        except Exception as e:
            flash(f'Error generating documentation: {str(e)}', 'error')
            return redirect(url_for('home'))
    
    return render_template('home.html')

@app.route('/delete/<path:site_name>', methods=['POST'])
def delete_docs(site_name):
    """Delete generated documentation"""
    try:
        site_dir = OUTPUT_DIR / site_name
        if site_dir.exists():
            shutil.rmtree(site_dir)
            return jsonify({'success': True, 'message': 'Documentation deleted successfully'})
        return jsonify({'success': False, 'message': 'Documentation not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/docs')
def docs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').lower()
    sort_by = request.args.get('sort', 'newest')  # newest, oldest, name
    output_dir = OUTPUT_DIR
    sites = []
    
    if output_dir.exists():
        # Collect all sites with metadata
        all_sites = []
        for site_dir in output_dir.iterdir():
            if site_dir.is_dir():
                index_path = site_dir / 'index.html'
                if index_path.exists():
                    metadata_file = site_dir / 'metadata.json'
                    metadata = {}
                    if metadata_file.exists():
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                    
                    site_info = {
                        'name': site_dir.name,
                        'path': f'{site_dir.name}/index.html',
                        'source_url': metadata.get('source_url'),
                        'version': metadata.get('version', '1.0.0'),
                        'generated_at': metadata.get('generation_info', {}).get('completed_at'),
                        'total_pages': metadata.get('stats', {}).get('total_pages', 0),
                        'total_size': metadata.get('stats', {}).get('total_size_bytes', 0)
                    }
                    
                    # Apply search filter
                    if search:
                        if search not in site_info['name'].lower() and \
                           search not in (site_info['source_url'] or '').lower():
                            continue
                    
                    all_sites.append(site_info)
        
        # Sort sites
        if sort_by == 'newest':
            all_sites.sort(key=lambda x: x['generated_at'] or '', reverse=True)
        elif sort_by == 'oldest':
            all_sites.sort(key=lambda x: x['generated_at'] or '')
        elif sort_by == 'name':
            all_sites.sort(key=lambda x: x['name'].lower())
        
        # Paginate
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        sites = all_sites[start_idx:end_idx]
        total_pages = (len(all_sites) + per_page - 1) // per_page
    
    return render_template('docs.html', 
                         sites=sites,
                         current_page=page,
                         total_pages=total_pages,
                         per_page=per_page,
                         search=search,
                         sort_by=sort_by)

@app.route('/output/<path:filename>')
def serve_output(filename):
    """Serve files from the output directory"""
    # Handle both the index.html and its referenced files in docs/
    if filename.endswith('index.html'):
        return send_from_directory(str(OUTPUT_DIR), filename)
    else:
        # For other files (like those in docs/), get the parent directory
        parent_dir = os.path.dirname(filename)
        file_name = os.path.basename(filename)
        return send_from_directory(str(OUTPUT_DIR / parent_dir), file_name)

if __name__ == '__main__':
    app.run(debug=True, port=5005)
