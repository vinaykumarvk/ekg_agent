#!/usr/bin/env python3
"""
Production startup script for EKG Agent
Handles environment validation and graceful startup
"""

import os
import sys
import logging
from pathlib import Path

def validate_environment():
    """Validate required environment variables"""
    required_vars = ['OPENAI_API_KEY']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Validate OpenAI API key format
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key.startswith('sk-'):
        print("❌ Invalid OpenAI API key format")
        sys.exit(1)
    
    print("✅ Environment validation passed")

def setup_logging():
    """Configure production logging"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    logger = logging.getLogger("ekg_agent")
    logger.info(f"Starting EKG Agent with log level: {log_level}")
    return logger

def create_cache_directory():
    """Ensure cache directory exists"""
    cache_dir = os.getenv('CACHE_DIR', '/tmp/ekg_cache')
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    print(f"✅ Cache directory ready: {cache_dir}")

def main():
    """Main startup function"""
    print("🚀 Starting EKG Agent Production Server")
    
    # Validate environment
    validate_environment()
    
    # Setup logging
    logger = setup_logging()
    
    # Create cache directory
    create_cache_directory()
    
    # Import and start the application
    try:
        import uvicorn
        from api.main import app
        
        port = int(os.getenv('PORT', 8080))
        host = os.getenv('HOST', '0.0.0.0')
        
        logger.info(f"Starting server on {host}:{port}")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level=os.getenv('LOG_LEVEL', 'info').lower(),
            access_log=True,
            server_header=False,
            date_header=False
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
