import logging
import subprocess
import base64
import os
import io
import requests
from PIL import Image
from weasyprint import HTML, urls
from weasyprint.text.fonts import FontConfiguration
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import current_app
from concurrent.futures import ThreadPoolExecutor, as_completed
from app import socketio

logger = logging.getLogger(__name__)

def encode_font(font_path):
    with open(font_path, "rb") as font_file:
        return base64.b64encode(font_file.read()).decode('utf-8')

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

def is_valid_image_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def process_content(content):
    soup = BeautifulSoup(content, 'html.parser')
    
    for img in soup.find_all('img'):
        src = img.get('src')
        if not src or not is_valid_image_url(src):
            logger.warning(f"Removing invalid image URL: {src}")
            img.decompose()
            continue

    for figure in soup.find_all('figure'):
        if figure.has_attr('class'):
            del figure['class']
        figure['class'] = 'image-figure'
        
        img = figure.find('img')
        if img:
            for source in figure.find_all('source'):
                source.decompose()
            if img.has_attr('class'):
                del img['class']
            figure.insert(0, img.extract())
        
        figcaption = figure.find('figcaption')
        if figcaption:
            for svg in figcaption.find_all('svg'):
                svg.decompose()
            if figcaption.has_attr('class'):
                del figcaption['class']
            figcaption['class'] = 'image-caption'
    
    return str(soup)

def optimize_image(url, max_width=800, max_height=1000, quality=85):
    try:
        response = requests.get(url, timeout=5)
        img = Image.open(io.BytesIO(response.content))
        
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')
        
        if img.width > max_width or img.height > max_height:
            img.thumbnail((max_width, max_height), Image.LANCZOS)
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', optimize=True, quality=quality)
        return img_byte_arr.getvalue(), 'image/jpeg'
    except Exception as e:
        logger.warning(f"Failed to process image: {url}. Error: {str(e)}")
        return None, None

def fetch_url_wrapper(url):
    try:
        result = urls.default_url_fetcher(url)
        if result['mime_type'].startswith('image/'):
            optimized_image, mime_type = optimize_image(url)
            if optimized_image:
                return {
                    'string': optimized_image,
                    'mime_type': mime_type
                }
        return result
    except Exception as e:
        logger.warning(f"Failed to fetch URL: {url}. Error: {str(e)}")
        return None

def process_article_content(article, article_index, total_articles):
    try:
        processed_content = process_content(article['content'])
        return {
            'title': article['title'],
            'author': article['author'],
            'url': article['url'],
            'processed_content': processed_content
        }
    except Exception as e:
        logger.error(f"Error processing article {article['title']}: {e}")
        return None

import logging
import os
import io
from weasyprint import HTML, urls
from weasyprint.text.fonts import FontConfiguration
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from flask import current_app
from concurrent.futures import ThreadPoolExecutor, as_completed
from app import socketio

logger = logging.getLogger(__name__)

def create_pdf(articles, current_date, pdf_path, two_column_layout=False):
    socketio.emit('pdf_progress', {'progress': 0, 'status': 'Starting PDF generation'})
    
    socketio.emit('pdf_progress', {'progress': 5, 'status': 'Loading fonts and cover'})
    bookerly_regular = encode_font(os.path.join(current_app.config['FONT_DIR'], 'Bookerly-Regular.ttf'))
    bookerly_bold = encode_font(os.path.join(current_app.config['FONT_DIR'], 'Bookerly-Bold.ttf'))
    lexend_regular = encode_font(os.path.join(current_app.config['FONT_DIR'], 'Lexend-Regular.ttf'))
    
    cover_svg_path = os.path.join(current_app.root_path, 'static', 'images', 'cover.svg')
    try:
        with open(cover_svg_path, 'r') as svg_file:
            cover_svg = svg_file.read()
    except Exception as e:
        logger.error(f"Error reading cover SVG: {e}")
        cover_svg = None

    socketio.emit('pdf_progress', {'progress': 10, 'status': 'Preparing HTML content'})
    
    page_width_px = 810
    page_height_px = 1080

    column_css = """
    .article-content {
        column-count: 2;
        column-gap: 20px;
        text-align: justify;
    }
    .article-content img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 10px auto;
        page-break-inside: avoid;
    }
    .article-header {
        column-span: all;
    }
    """ if two_column_layout else ""

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
                margin: {'50px 25px' if two_column_layout else '50px 50px'};
            }}
            @page :first {{
                margin: 0;
            }}
            body {{ 
                font-family: 'Lexend', sans-serif; 
                font-size: {'13.5px' if two_column_layout else '15px'}; 
                line-height: 1.5; 
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
                font-size: {'24px' if two_column_layout else '26px'}; 
                font-weight: bold; 
                margin-top: 20px;
                margin-bottom: {'10px' if two_column_layout else '20px'};
                page-break-before: always;
            }}
            h2 {{ 
                font-family: 'Bookerly', serif; 
                font-size: 20px; 
                font-weight: bold; 
                margin-top: 25px;
                margin-bottom: 15px;
            }}
            .article-header {{
                border-bottom: 2px solid black;
                margin-bottom: 1.5rem;
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
            .toc {{
                padding: {'1.5rem' if two_column_layout else '0rem'};
            }}
            .toc h1 {{
                font-size: 28px;
            }}
            .toc a {{
                text-decoration: none;
                border-bottom: none;
                color: black;
            }}
            .toc ul {{
                list-style-type: none;
                padding-left: 0;
                font-size: 15px;
            }}
            .toc li {{
                margin-bottom: 10px;
            }}
            {column_css}
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

    socketio.emit('pdf_progress', {'progress': 20, 'status': 'Processing articles'})

    # Process articles in parallel
    processed_articles = []
    total_articles = len(articles)
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_article = {executor.submit(process_article_content, article, index, total_articles): article 
                             for index, article in enumerate(articles)}
        for future in as_completed(future_to_article):
            result = future.result()
            if result:
                processed_articles.append(result)
                progress = 20 + (len(processed_articles) / total_articles) * 40
                socketio.emit('pdf_progress', {'progress': progress, 'status': f'Processed {len(processed_articles)} of {total_articles} articles'})

    # Sort processed articles to maintain original order
    processed_articles.sort(key=lambda x: articles.index(next(a for a in articles if a['title'] == x['title'])))

    socketio.emit('pdf_progress', {'progress': 60, 'status': 'Generating Table of Contents'})
    # Generate Table of Contents
    for index, article in enumerate(processed_articles, start=1):
        html_content += f'<li><a href="#article-{index}">{article["title"]}</a></li>'

    html_content += """
            </ul>
        </div>
    """

    socketio.emit('pdf_progress', {'progress': 70, 'status': 'Adding article content'})
    # Add processed article content
    for index, article in enumerate(processed_articles, start=1):
        html_content += f"""
        <div class="article">
            <div class="article-header">
                <h1 class="article-title" id="article-{index}">{article['title']}</h1>
                <p class="metadata">{article['author'] or 'Unknown'} | {urlparse(article['url']).netloc}</p>
            </div>
            <div class="article-content">
                {article['processed_content']}
            </div>
        </div>
        """

    html_content += "</body></html>"

    socketio.emit('pdf_progress', {'progress': 80, 'status': 'Generating PDF'})

    font_config = FontConfiguration()
    
    try:
        HTML(string=html_content).write_pdf(
            pdf_path,
            font_config=font_config,
            presentational_hints=True,
            url_fetcher=fetch_url_wrapper,
            metadata={
                'title': f'Omnivore {current_date}',
                'author': 'Various',
                'creator': 'Omnivore to PDF Converter'
            }
        )
        logger.info(f"PDF created successfully: {pdf_path}")
        socketio.emit('pdf_progress', {'progress': 90, 'status': 'Compressing PDF'})
        
        # Compress PDF
        compressed_pdf_path = compress_pdf(pdf_path, pdf_path.replace('.pdf', '_compressed.pdf'))
        
        socketio.emit('pdf_progress', {'progress': 100, 'status': 'PDF generation complete'})
        return compressed_pdf_path
    except Exception as e:
        logger.error(f"Error creating PDF: {e}")
        socketio.emit('pdf_progress', {'progress': 100, 'status': 'Error creating PDF'})
        return None