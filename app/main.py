from flask import Blueprint, render_template, request, jsonify, send_file, current_app, url_for
from app.api.omnivore import fetch_articles, fetch_articles_by_ids, archive_article
from app.utils.pdf_generator import create_pdf, compress_pdf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
import os
import tempfile
from datetime import datetime
import uuid
from app import socketio
from app.utils.epub_generator import create_epub


bp = Blueprint('main', __name__)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING) 

# Set up rate limiting
limiter = Limiter(get_remote_address, storage_uri="memory://")

def log_pdf_articles(articles):
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, "pdf_articles.log")
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\nArticles converted on {current_date}:\n")
        f.write("=" * 30 + "\n")
        
        for article in articles:
            f.write(f"{article['title']}\n")
            f.write(f"{article['url']}\n\n")


@bp.route('/')
def index():
    return render_template('index.html')

@bp.route('/settings')
def settings():
    return render_template('settings.html')

@bp.route('/fetch_articles', methods=['POST'])
@limiter.limit("10 per minute") 
def fetch_all_articles_route():
    api_key = request.json.get('api_key')
    tag = request.json.get('tag')
    sort = request.json.get('sort', 'asc')
    page_type = request.json.get('page_type', 'index')
    emit_progress = request.json.get('emit_progress', False)
    
    if not api_key:
        return jsonify({"error": "API key is required"}), 400

    articles, _, _ = fetch_articles(api_key, tag=tag, sort=sort, socketio=socketio, emit_progress=emit_progress)
    
    # Only limit to 10 for index page
    if page_type == 'index':
        articles = articles[:10]
    
    return jsonify({
        "articles": articles
    })

@bp.route('/generate_document', methods=['POST'])
@limiter.limit("10 per hour")
def generate_document():
    try:
        socketio.emit('document_progress', {'progress': 5, 'status': 'Initializing document generation process'})
        
        api_key = request.json.get('api_key')
        article_slugs = request.json.get('article_slugs', [])
        archive = request.json.get('archive', False)
        two_column_layout = request.json.get('two_column_layout', False)
        output_format = request.json.get('output_format', 'pdf')

        if not api_key:
            logger.warning("API key not provided")
            socketio.emit('document_progress', {'progress': 100, 'status': 'Error: API key is required'})
            return jsonify({"error": "API key is required"}), 400

        if len(article_slugs) > 10:
            logger.warning("Too many articles selected")
            socketio.emit('document_progress', {'progress': 100, 'status': 'Error: Too many articles selected'})
            return jsonify({"error": "You can only select up to 10 articles"}), 400

        socketio.emit('document_progress', {'progress': 10, 'status': 'Fetching articles'})
        articles = fetch_articles_by_ids(api_key, article_slugs)

        if not articles:
            logger.warning("No articles fetched. Check your API key or criteria.")
            socketio.emit('document_progress', {'progress': 100, 'status': 'Error: No articles fetched'})
            return jsonify({"error": "No articles fetched. Check your API key or criteria."}), 404

        socketio.emit('document_progress', {'progress': 20, 'status': 'Articles fetched successfully'})
        
        log_pdf_articles(articles)
        current_date = datetime.now().strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:8]
        
        if output_format == 'epub':
            document_filename = f"Omnivore_{current_date}_{unique_id}.epub"
        else:
            document_filename = f"Omnivore_{current_date}_{unique_id}.pdf"

        socketio.emit('document_progress', {'progress': 30, 'status': f'Starting {output_format.upper()} creation'})

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_document_path = os.path.join(temp_dir, f'temp_omnivore_articles.{output_format}')
            
            if output_format == 'epub':
                document_path = create_epub(articles, current_date, temp_document_path)
            else:
                document_path = create_pdf(articles, current_date, temp_document_path, two_column_layout)
            
            if document_path and os.path.exists(document_path):
                socketio.emit('document_progress', {'progress': 80, 'status': f'{output_format.upper()} created'})

                if output_format == 'pdf':
                    compressed_pdf_path = os.path.join(temp_dir, document_filename)
                    final_document_path = compress_pdf(document_path, compressed_pdf_path)
                else:
                    final_document_path = document_path

                if os.path.exists(final_document_path):
                    logger.info(f"Sending file: {final_document_path}")
                    socketio.emit('document_progress', {'progress': 90, 'status': f'{output_format.upper()} prepared, ready to send'})
                    
                    # Archive articles if requested
                    if archive:
                        socketio.emit('document_progress', {'progress': 95, 'status': 'Archiving articles'})
                        for article in articles:
                            archive_result = archive_article(api_key, article['id'])
                            if archive_result:
                                logger.info(f"Archived article: {article['id']}")
                            else:
                                logger.warning(f"Failed to archive article: {article['id']}")
                    
                    socketio.emit('document_progress', {'progress': 100, 'status': f'{output_format.upper()} ready for download'})
                    return send_file(final_document_path, as_attachment=True, download_name=document_filename, 
                                     mimetype='application/epub+zip' if output_format == 'epub' else 'application/pdf')
                else:
                    logger.error(f"Final document not found at: {final_document_path}")
                    socketio.emit('document_progress', {'progress': 100, 'status': f'Error: Final {output_format.upper()} not found'})
                    return jsonify({"error": f"Final {output_format.upper()} not found"}), 500
            else:
                logger.error(f"Original document not found at: {document_path}")
                socketio.emit('document_progress', {'progress': 100, 'status': f'Error: Failed to create {output_format.upper()}'})
                return jsonify({"error": f"Failed to create {output_format.upper()}"}), 500

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        socketio.emit('document_progress', {'progress': 100, 'status': f'Error: {str(e)}'})
        return jsonify({"error": str(e)}), 500