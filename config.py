import os
import logging

class Config:
    # The domain where the application is hosted
    DOMAIN = "https://DOMAIN.COM"
    
    # API endpoint
    API_ENDPOINT = "https://api-prod.omnivore.app/api/graphql"
    
    # Output directory for generated PDFs
    OUTPUT_DIR = os.path.abspath("output")

    # Logging config
    LOG_LEVEL = logging.WARNING
    
    # Font directory
    FONT_DIR = os.path.abspath(os.path.join("app", "static", "fonts"))
    
    # Static files directory
    STATIC_DIR = os.path.abspath(os.path.join("app", "static"))

    # Flask-Limiter configurations
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_STORAGE_URI = "memory://"
    
    # Other configurations...
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    DEBUG = True
    LOG_LEVEL = logging.INFO

class ProductionConfig(Config):
    # Production-specific settings
    pass
    LOG_LEVEL = logging.ERROR
    
class TestingConfig(Config):
    TESTING = True

# You can add more configuration classes as needed

# Set the active configuration
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config():
    return config[os.environ.get('FLASK_ENV', 'default')]