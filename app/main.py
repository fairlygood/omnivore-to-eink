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
    
    if not api_key:
        return jsonify({"error": "API key is required"}), 400

    articles, _, _ = fetch_articles(api_key, tag=tag, sort=sort)
    
    # Only limit to 10 for index page
    if page_type == 'index':
        articles = articles[:10]
    
    return jsonify({
        "articles": articles
    })

@bp.route('/generate_pdf', methods=['POST'])
@limiter.limit("10 per hour")
def generate_pdf():
    try:
        api_key = request.json.get('api_key')
        article_slugs = request.json.get('article_slugs', [])
        archive = request.json.get('archive', False)
        two_column_layout = request.json.get('two_column_layout', False)

        if not api_key:
            logger.warning("API key not provided")
            return jsonify({"error": "API key is required"}), 400

        if len(article_slugs) > 10:
            logger.warning("Too many articles selected")
            return jsonify({"error": "You can only select up to 10 articles"}), 400

        articles = fetch_articles_by_ids(api_key, article_slugs)

        if not articles:
            logger.warning("No articles fetched. Check your API key or criteria.")
            return jsonify({"error": "No articles fetched. Check your API key or criteria."}), 404

        log_pdf_articles(articles)
        current_date = datetime.now().strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:8]
        pdf_filename = f"Omnivore_{current_date}_{unique_id}.pdf"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_pdf_path = os.path.join(temp_dir, 'temp_omnivore_articles.pdf')
            pdf_path = create_pdf(articles, current_date, temp_pdf_path, two_column_layout)
            
            if pdf_path and os.path.exists(pdf_path):
                compressed_pdf_path = os.path.join(temp_dir, pdf_filename)
                final_pdf_path = compress_pdf(pdf_path, compressed_pdf_path)

                if os.path.exists(final_pdf_path):
                    logger.info(f"Sending file: {final_pdf_path}")
                    
                    # Archive articles if requested
                    if archive:
                        for article in articles:
                            archive_result = archive_article(api_key, article['id'])
                            if archive_result:
                                logger.info(f"Archived article: {article['id']}")
                            else:
                                logger.warning(f"Failed to archive article: {article['id']}")
                    
                    return send_file(final_pdf_path, as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
                else:
                    logger.error(f"Compressed PDF not found at: {final_pdf_path}")
                    return jsonify({"error": "Compressed PDF not found"}), 500
            else:
                logger.error(f"Original PDF not found at: {pdf_path}")
                return jsonify({"error": "Failed to create PDF"}), 500

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return jsonify({"error": str(e)}), 500