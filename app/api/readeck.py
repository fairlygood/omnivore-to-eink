import requests
import logging

logger = logging.getLogger(__name__)

def fetch_articles(api_url, api_key, tag=None, sort="asc", cursor=None, socketio=None, emit_progress=False):
    if not api_url.endswith("/api"):
        api_url = api_url.rstrip("/") + "/api"
    
    logger.debug(f"Using Readeck API URL: {api_url}")

    """
    Fetch all articles from Readeck with full content, optionally filtered by tag.
    Uses pagination via offset/limit.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    limit = 50  # Safe default based on curl testing
    offset = 0
    all_articles = []

    try:
        if emit_progress and socketio:
            socketio.emit('pdf_progress', {'progress': 5, 'status': 'Fetching article list'})

        while True:
            params = {
                "is_archived": "false",  # must be string
                "limit": limit,
                "offset": offset,
                "sort": sort,
            }
            if tag:
                params["labels"] = tag

            logger.info(f"Fetching bookmarks: offset={offset}, limit={limit}")
            response = requests.get(f"{api_url}/bookmarks", headers=headers, params=params)
            response.raise_for_status()
            bookmarks = response.json() 
            logger.info(f"Fetched {len(bookmarks)} bookmarks from Readeck")

            if not bookmarks:
                break

            for item in bookmarks:
                article_id = item.get("id")
                try:
                    detail_resp = requests.get(f"{api_url}/bookmarks/{article_id}", headers=headers)
                    detail_resp.raise_for_status()
                    detail = detail_resp.json()

                    article = {
                        "id": detail.get("id"),
                        "title": detail.get("title", "Untitled"),
                        "url": detail.get("url"),
                        "author": detail.get("author", "Unknown"),
                        "createdAt": detail.get("created_at"),
                        "content": detail.get("content", ""),
                        "tags": detail.get("labels", []),
                    }
                    all_articles.append(article)

                    if emit_progress and socketio and len(all_articles) % 5 == 0:
                        socketio.emit('pdf_progress', {
                            'progress': 5 + int(len(all_articles) / 5),
                            'status': f'Fetched {len(all_articles)} articles'
                        })

                except Exception as e:
                    logger.error(f"Error fetching full content for article {article_id}: {str(e)}")

            offset += limit

        if emit_progress and socketio:
            socketio.emit('pdf_progress', {'progress': 90, 'status': 'Finished fetching articles'})

    except Exception as e:
        logger.error(f"Error during article fetch: {str(e)}")
        if emit_progress and socketio:
            socketio.emit('pdf_progress', {'progress': 100, 'status': f'Error: {str(e)}'})

    return all_articles, None, False

def fetch_articles_by_ids(api_url, api_key, article_ids):
    if not api_url.endswith("/api"):
        api_url = api_url.rstrip("/") + "/api"
    logger.debug(f"Using Readeck API URL: {api_url}")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    articles = []
    for article_id in article_ids:
        if not article_id:
            logger.warning("Skipping empty article ID")
            continue

        try:
            # First fetch metadata
            meta_resp = requests.get(f"{api_url}/bookmarks/{article_id}", headers=headers)
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            # Then fetch full article HTML
            article_url = meta.get("resources", {}).get("article", {}).get("src")
            if not article_url:
                logger.warning(f"No article content URL found for {article_id}")
                continue

            content_resp = requests.get(article_url, headers=headers)
            content_resp.raise_for_status()
            html_content = content_resp.text

            article = {
                "id": meta.get("id"),
                "title": meta.get("title", "Untitled"),
                "url": meta.get("url"),
                "author": ", ".join(meta.get("authors", [])) or "Unknown",
                "createdAt": meta.get("created"),
                "content": html_content,
                "tags": meta.get("labels", []),
            }
            articles.append(article)

        except Exception as e:
            logger.error(f"Error fetching article {article_id}: {str(e)}")

    return articles


