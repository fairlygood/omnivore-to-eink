import os
import requests
import subprocess
import logging
import base64
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from flask import Flask, request, send_file, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from config import DOMAIN, API_ENDPOINT, OUTPUT_DIR, FONT_DIR, STATIC_DIR
from flask import render_template
from datetime import datetime
import uuid
import tempfile

app = Flask(__name__)

CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress WeasyPrint logging
logging.getLogger('weasyprint').setLevel(logging.CRITICAL)
logging.getLogger('fontTools').setLevel(logging.CRITICAL)
logging.getLogger('PIL').setLevel(logging.CRITICAL)

# Set up rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://"
)

# Constants
OUTPUT_DIR = os.path.abspath(OUTPUT_DIR)
FONT_DIR = os.path.abspath(FONT_DIR)
STATIC_DIR = os.path.abspath(STATIC_DIR)

# Omnivore API settings
API_ENDPOINT = "https://api-prod.omnivore.app/api/graphql"

def archive_article(api_key, link_id):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    
    mutation = """
    mutation SetLinkArchived($input: ArchiveLinkInput!) {
        setLinkArchived(input: $input) {
            ... on ArchiveLinkSuccess {
                linkId
                message
            }
            ... on ArchiveLinkError {
                message
                errorCodes
            }
        }
    }
    """
    
    variables = {
        "input": {
            "linkId": link_id,
            "archived": True
        }
    }
    
    payload = {
        "query": mutation,
        "variables": variables
    }
    
    try:
        response = requests.post(API_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return False
        
        result = data["data"]["setLinkArchived"]
        if "linkId" in result:
            logger.info(f"Article {link_id} archived successfully")
            return True
        else:
            logger.error(f"Failed to archive article {link_id}: {result.get('message')}")
            return False
    except Exception as e:
        logger.error(f"Error archiving article {link_id}: {str(e)}")
        return False

def fetch_articles(api_key, tag=None, max_count=10, sort="asc"):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    
    logger.info(f"Received sort parameter: {sort}") 

    sort_order = "saved-asc" if sort == "asc" else "saved-desc"
    query = f"sort:{sort_order} in:inbox"
    if tag:
        query += f" label:\"{tag}\""
    
    graphql_query = {
        "query": """
        query Search(
          $after: String
          $first: Int
          $query: String
          $includeContent: Boolean
        ) {
          search(
            first: $first
            after: $after
            query: $query
            includeContent: $includeContent
          ) {
            ... on SearchSuccess {
              edges {
                cursor
                node {
                  id
                  title
                  slug
                  url
                  author
                  content
                }
              }
            }
            ... on SearchError {
              errorCodes
            }
          }
        }
        """,
        "variables": {
            "after": None,
            "first": max_count,
            "query": query,
            "includeContent": True
        }
    }
    
    try:
        logger.info(f"Sending request to the Omnivore API")
        response = requests.post(API_ENDPOINT, json=graphql_query, headers=headers)
        logger.info(f"Received response with status code: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return []
        
        if "data" not in data or "search" not in data["data"]:
            logger.error(f"Unexpected response structure: {data}")
            return []
        
        search_result = data["data"]["search"]
        
        if isinstance(search_result, dict) and "errorCodes" in search_result:
            logger.error(f"Search error codes: {search_result['errorCodes']}")
            return []
        
        if not isinstance(search_result, dict) or "edges" not in search_result:
            logger.error(f"Unexpected search result structure: {search_result}")
            return []
        
        articles = [edge['node'] for edge in search_result['edges']]
        logger.info(f"Successfully fetched {len(articles)} articles")
        return articles
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        if hasattr(e.response, 'text'):
            logger.error(f"Response content: {e.response.text}")
        return []
    except Exception as e:
        logger.exception(f"Unexpected error in fetch_articles: {str(e)}")
        return []

def encode_font(font_path):
    with open(font_path, "rb") as font_file:
        return base64.b64encode(font_file.read()).decode('utf-8')

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def process_content(content):
    soup = BeautifulSoup(content, 'html.parser')
    
    for figure in soup.find_all('figure'):
        # Remove any existing class attributes
        if figure.has_attr('class'):
            del figure['class']
        
        # Add our custom class
        figure['class'] = 'image-figure'
        
        # Process the image within the figure
        img = figure.find('img')
        if img:
            # Remove all source tags
            for source in figure.find_all('source'):
                source.decompose()
            
            # Remove any existing class attributes from img
            if img.has_attr('class'):
                del img['class']
            
            # Ensure img is directly under figure
            figure.insert(0, img.extract())
        
        # Process the figcaption
        figcaption = figure.find('figcaption')
        if figcaption:
            # Remove any SVG elements from the figcaption
            for svg in figcaption.find_all('svg'):
                svg.decompose()
            
            # Remove any existing class attributes
            if figcaption.has_attr('class'):
                del figcaption['class']
            
            # Add our custom class
            figcaption['class'] = 'image-caption'
    
    return str(soup)

def compress_pdf(input_path, output_path):
    try:
        subprocess.run([
            'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
            '-dPDFSETTINGS=/ebook', '-dNOPAUSE', '-dQUIET', '-dBATCH',
            f'-sOutputFile={output_path}', input_path
        ], check=True)
        
        if os.path.exists(output_path):
            logger.info(f"PDF compressed successfully: {output_path}")
            return output_path
        else:
            logger.error(f"Compressed PDF not created at: {output_path}")
            return input_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Error compressing PDF: {e}")
        return input_path
    except Exception as e:
        logger.exception(f"Unexpected error in compress_pdf: {e}")
        return input_path

def create_pdf(articles, current_date, pdf_path):
    # Encode fonts and cover image
    bookerly_regular = encode_font(os.path.join(FONT_DIR, 'Bookerly-Regular.ttf'))
    bookerly_bold = encode_font(os.path.join(FONT_DIR, 'Bookerly-Bold.ttf'))
    lexend_regular = encode_font(os.path.join(FONT_DIR, 'Lexend-Regular.ttf'))
    
    # Read and encode SVG cover
    cover_svg_path = os.path.join(STATIC_DIR, 'cover.svg')
    try:
        with open(cover_svg_path, 'r') as svg_file:
            cover_svg = svg_file.read()
    except Exception as e:
        logger.error(f"Error reading cover SVG: {e}")
        cover_svg = None

    page_width_px = 810
    page_height_px = 1080

    html_content = f"""
    <html>
    <head>
        <style>

            @font-face {{
                font-family: 'Bookerly';
                src: url(data:font/truetype;charset=utf-8;base64,{bookerly_regular}) format('truetype');
                font-weight: normal;
                font-style: normal;
            }}
            @font-face {{
                font-family: 'Bookerly';
                src: url(data:font/truetype;charset=utf-8;base64,{bookerly_bold}) format('truetype');
                font-weight: bold;
                font-style: normal;
            }}
            @font-face {{
                font-family: 'Lexend';
                src: url(data:font/truetype;charset=utf-8;base64,{lexend_regular}) format('truetype');
                font-weight: normal;
                font-style: normal;
            }}
            @page {{
                size: {page_width_px}px {page_height_px}px;
                margin: 50px 50px;
            }}
            @page :first {{
                margin: 0;
            }}
            body {{ 
                font-family: 'Lexend', sans-serif; 
                font-size: 15px; 
                line-height: 1.4; 
                margin: 0;
                padding: 0;
            }}
            .cover {{
                width: {page_width_px}px;
                height: {page_height_px}px;
                display: block;
                page-break-after: always;
            }}
            .cover svg {{
                width: 100%;
                height: 100%;
            }}
            p {{ 
                font-family: 'Lexend', sans-serif;
                text-align: justify; 
                margin-bottom: 20px;
            }}
            h1 {{ 
                font-family: 'Bookerly', serif; 
                font-size: 26px; 
                font-weight: bold; 
                margin-top: 30px;
                margin-bottom: 20px;
                page-break-before: always;
            }}
            h2 {{ 
                font-family: 'Bookerly', serif; 
                font-size: 20px; 
                font-weight: bold; 
                margin-top: 25px;
                margin-bottom: 15px;
            }}
            .metadata {{ 
                font-family: 'Lexend', sans-serif;
                font-size: 12px; 
                color: #666; 
                margin-bottom: 10px;
            }}
            img {{ 
                max-width: 100%;
                height: auto;
                display: block;
                margin: 30px auto;
                page-break-inside: avoid;
                border-radius: 5px;
            }}
            .image-container {{
                text-align: center;
                margin: 30px 0;
                page-break-inside: avoid;
            }}
            .image-figure {{
                text-align: center;
                margin: 30px 0;
                page-break-inside: avoid;
            }}
            .image-figure img {{
                max-width: 100%;
                height: auto;
                display: block;
                margin: 0 auto;
                border-radius: 5px;
            }}
            .image-caption {{
                font-size: 12px;
                color: #666;
                margin-top: 10px;
                font-style: italic;
            }}
            ul {{
                font-family: 'Lexend', sans-serif;
                padding-left: 30px;
            }}
            li {{
                margin-bottom: 10px;
            }}
            .toc {{
                page-break-after: always;
            }}
            a {{
                color: black;
                text-decoration: none;
                border-bottom: 1px solid black;
                padding-bottom: 2px;
            }}
            .toc a,
            .toc a:link,
            .toc a:visited,
            .toc a:hover,
            .toc a:active {{
                text-decoration: none !important;
                border-bottom: none !important;
                color: black !important;
            }}
            .toc ul {{
                list-style-type: none;
                padding-left: 0;
            }}
            .toc li {{
                margin-bottom: 10px;
            }}
                </style>
    </head>
    <body>
    """

    if cover_svg:
        html_content += f'<div class="cover">{cover_svg}</div>'
    else:
        logger.warning("Cover SVG not available. Skipping cover page.")

    html_content += """
        <div class="toc">
            <h1>Table of Contents</h1>
            <ul>
    """

    for index, article in enumerate(articles, start=1):
        html_content += f'<li><a href="#article-{index}">{article["title"]}</a></li>'

    html_content += """
            </ul>
        </div>
    """

    for index, article in enumerate(articles, start=1):
        processed_content = process_content(article['content'])
        html_content += f"""
        <h1 id="article-{index}">{article['title']}</h1>
        <p class="metadata">{article['author'] or 'Unknown'} | {urlparse(article['url']).netloc}</p>
        <hr>
        {processed_content}
        """

    html_content += "</body></html>"

    font_config = FontConfiguration()
    
    try:
        HTML(string=html_content).write_pdf(
            pdf_path,
            font_config=font_config,
            presentational_hints=True,
            metadata={
                'title': f'Omnivore {current_date}',
                'author': 'Various',
                'creator': 'Omnivore to PDF Converter'
            }
        )
        logger.info(f"PDF created successfully: {pdf_path}")
        return pdf_path
    except Exception as e:
        logger.error(f"Error creating PDF: {e}")
        return None
    
@app.route('/')
def index():
    return render_template('index.html', domain=DOMAIN)

@app.route('/settings')
def settings():
    return render_template('settings.html', domain=DOMAIN)

@app.route('/generate_pdf', methods=['POST'])
@limiter.limit("1 per minute")
def generate_pdf():
    try:
        api_key = request.json.get('api_key')
        max_count = request.json.get('max_count', 10)
        tag = request.json.get('tag')
        should_archive = request.json.get('archive', False)
        sort = request.json.get('sort', 'asc')

        if not api_key:
            logger.warning("API key not provided")
            return jsonify({"error": "API key is required"}), 400

        articles = fetch_articles(api_key, tag, max_count, sort)
        
        if not articles:
            logger.warning("No articles fetched. Check your API key.")
            return jsonify({"error": "No articles fetched. Check your API key."}), 404

        current_date = datetime.now().strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:8]
        pdf_filename = f"Omnivore_{current_date}_{unique_id}.pdf"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pdf_path = os.path.join(temp_dir, 'temp_omnivore_articles.pdf')
            pdf_path = create_pdf(articles, current_date, temp_pdf_path)
            
            if pdf_path and os.path.exists(pdf_path):
                compressed_pdf_path = os.path.join(temp_dir, pdf_filename)
                final_pdf_path = compress_pdf(pdf_path, compressed_pdf_path)

                if os.path.exists(final_pdf_path):
                    logger.info(f"Sending file: {final_pdf_path}")
                    
                    if should_archive:
                        archived_count = 0
                        for article in articles:
                            if archive_article(api_key, article['id']):
                                archived_count += 1
                        logger.info(f"Archived {archived_count} out of {len(articles)} articles")
                    
                    return send_file(final_pdf_path, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
                else:
                    logger.error(f"Compressed PDF not found at: {final_pdf_path}")
                    return jsonify({"error": "Compressed PDF not found"}), 500
            else:
                logger.error(f"Original PDF not found at: {pdf_path}")
                return jsonify({"error": "Failed to create PDF"}), 500

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

