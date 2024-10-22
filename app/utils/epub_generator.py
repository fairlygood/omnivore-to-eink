import os
from ebooklib import epub
from bs4 import BeautifulSoup
from app.utils.pdf_generator import process_content, fetch_url_wrapper
from flask import current_app
import uuid
from datetime import datetime
from PIL import Image
import io

def create_epub(articles, current_date, epub_path):
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(f'Omnivore Articles {current_date}')
    book.set_language('en')
    book.add_author('Various')

    # Add cover image
    cover_svg_path = os.path.join(current_app.root_path, 'static', 'images', 'cover.svg')
    if os.path.exists(cover_svg_path):
        # Convert SVG to PNG
        from cairosvg import svg2png
        png_data = svg2png(url=cover_svg_path)
        cover_image = Image.open(io.BytesIO(png_data))
        
        # Resize image if necessary
        cover_image.thumbnail((1000, 1000))  # Adjust size as needed
        
        # Save as JPEG
        buffer = io.BytesIO()
        cover_image.save(buffer, 'JPEG')
        buffer.seek(0)
        
        # Add cover to EPUB
        book.set_cover("cover.jpg", buffer.getvalue())

    # Create chapters
    chapters = []
    toc = []
    spine = ['nav']

    # Reset epub_images
    process_content.epub_images = []

    for index, article in enumerate(articles, start=1):
        chapter = epub.EpubHtml(title=article['title'], file_name=f'chapter_{index}.xhtml', lang='en')
        
        # Process content
        processed_content = process_content(article['content'], for_epub=True)
        
        # Create chapter content
        chapter_content = f'''
        <html>
        <head>
            <title>{article['title']}</title>
        </head>
        <body>
            <h1>{article['title']}</h1>
            <p><em>By {article['author'] or 'Unknown'}</em></p>
            {processed_content}
        </body>
        </html>
        '''
        
        chapter.set_content(chapter_content)
        book.add_item(chapter)
        chapters.append(chapter)
        toc.append(epub.Link(f'chapter_{index}.xhtml', article['title'], f'chapter{index}'))
        spine.append(chapter)

    # Add images to the EPUB
    for img_filename, img_data in process_content.epub_images:
        epub_image = epub.EpubImage()
        epub_image.file_name = img_filename
        epub_image.media_type = 'image/jpeg'
        epub_image.content = img_data
        book.add_item(epub_image)

    # Add default NCX and Nav file
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Define Table of Contents
    book.toc = toc

    # Add chapters to the book
    book.spine = spine

    # Write EPUB file
    epub.write_epub(epub_path, book, {})

    return epub_path