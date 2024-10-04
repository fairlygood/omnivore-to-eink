import requests
import logging
from flask import current_app

logger = logging.getLogger(__name__)

def get_api_endpoint():
    return current_app.config['API_ENDPOINT']

def fetch_articles(api_key, tag=None, sort="asc", cursor=None):
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
        ) {
          search(
            first: $first
            after: $after
            query: $query
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
                  createdAt
                }
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
            ... on SearchError {
              errorCodes
            }
          }
        }
        """,
        "variables": {
            "after": cursor,
            "first": 100,  # Fetch 100 articles at a time
            "query": query,
        }
    }
    
    all_articles = []
    has_next_page = True
    
    while has_next_page:
        try:
            logger.info(f"Sending request to the Omnivore API")
            response = requests.post(get_api_endpoint(), json=graphql_query, headers=headers)
            logger.info(f"Received response with status code: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                logger.error(f"GraphQL errors: {data['errors']}")
                break
            
            search_result = data["data"]["search"]
            
            if isinstance(search_result, dict) and "errorCodes" in search_result:
                logger.error(f"Search error codes: {search_result['errorCodes']}")
                break
            
            if not isinstance(search_result, dict) or "edges" not in search_result:
                logger.error(f"Unexpected search result structure: {search_result}")
                break
            
            articles = [edge['node'] for edge in search_result['edges']]
            all_articles.extend(articles)
            
            has_next_page = search_result['pageInfo']['hasNextPage']
            cursor = search_result['pageInfo']['endCursor']
            graphql_query['variables']['after'] = cursor
            
        except Exception as e:
            logger.error(f"Error fetching articles: {str(e)}")
            break
    
    logger.info(f"Successfully fetched {len(all_articles)} articles")
    return all_articles, None, False

def fetch_articles_by_ids(api_key, article_slugs):
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    
    query = """
    query GetArticle($username: String!, $slug: String!) {
        article(username: $username, slug: $slug) {
            ... on ArticleSuccess {
                article {
                    id
                    title
                    url
                    author
                    content
                    savedAt
                    createdAt
                    publishedAt
                    slug
                    description
                    wordsCount
                }
            }
            ... on ArticleError {
                errorCodes
            }
        }
    }
    """
    
    articles = []
    for slug in article_slugs:
        variables = {
            "username": "me",  # We use "me" to refer to the current user
            "slug": slug,
        }
        
        try:
            response = requests.post(get_api_endpoint(), json={"query": query, "variables": variables}, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            if "errors" in data:
                logger.error(f"GraphQL errors for slug {slug}: {data['errors']}")
                continue
            
            article_data = data.get("data", {}).get("article", {}).get("article")
            if article_data:
                articles.append(article_data)
            else:
                logger.error(f"No article data found for slug: {slug}")
        except Exception as e:
            logger.error(f"Error fetching article with slug {slug}: {str(e)}")
    
    return articles

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
        response = requests.post(get_api_endpoint(), json=payload, headers=headers)
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