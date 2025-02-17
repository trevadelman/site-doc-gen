from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
import asyncio
from pathlib import Path
import sys
import json
from site_doc_gen import DocGen, Config
import os

# Get the absolute path to the site-doc-gen directory
ROOT_DIR = Path(__file__).parent.parent.absolute()
OUTPUT_DIR = ROOT_DIR / 'output'

app = Flask(__name__, static_folder=None)  # Disable default static folder
app.secret_key = os.urandom(24)
app.config['PROPAGATE_EXCEPTIONS'] = True  # For better async error handling

# Ensure the output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        url = request.form.get('url')
        if not url:
            flash('URL is required')
            return redirect(url_for('home'))
        
        config = Config(
            concurrency=int(request.form.get('concurrency', 3)),
            max_pages=int(request.form.get('max_pages', 0)) or None,
            match=request.form.get('match', '').split(',') if request.form.get('match') else None,
            content_selector=request.form.get('content_selector'),
            split_pages=bool(request.form.get('split_pages')),
            create_index=bool(request.form.get('create_index')),
            preserve_code_blocks=bool(request.form.get('preserve_code_blocks')),
            output_format=request.form.get('output_format', 'markdown')
        )
        
        async def process():
            async with DocGen(config) as doc_gen:
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
                metadata = {
                    'source_url': url,
                    'generated_at': asyncio.get_event_loop().time()
                }
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
        
        asyncio.run(process())
        flash('Documentation generated successfully!')
        return redirect(url_for('docs'))
    
    return render_template('home.html')

@app.route('/docs')
def docs():
    output_dir = OUTPUT_DIR
    sites = []
    
    if output_dir.exists():
        for site_dir in output_dir.iterdir():
            if site_dir.is_dir():
                index_path = site_dir / 'index.html'
                if index_path.exists():
                    # Read metadata file if it exists
                    metadata_file = site_dir / 'metadata.json'
                    source_url = None
                    if metadata_file.exists():
                        with open(metadata_file) as f:
                            metadata = json.load(f)
                            source_url = metadata.get('source_url')
                    
                    sites.append({
                        'name': site_dir.name,
                        'path': f'{site_dir.name}/index.html',
                        'source_url': source_url
                    })
    
    return render_template('docs.html', sites=sites)

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
