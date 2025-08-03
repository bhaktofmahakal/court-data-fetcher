"""
Minimal test suite for CI/CD pipeline
"""
import pytest
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import flask
        import requests
        import selenium
        import bs4
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import required module: {e}")

def test_app_creation():
    """Test that Flask app can be created"""
    try:
        from app import app
        assert app is not None
        assert app.config is not None
    except Exception as e:
        pytest.fail(f"Failed to create Flask app: {e}")

def test_database_directory():
    """Test that database directory can be created"""
    try:
        from app import init_db
        init_db()
        assert os.path.exists('db')
        assert os.path.exists('db/queries.db')
    except Exception as e:
        pytest.fail(f"Failed to initialize database: {e}")

def test_scraper_class():
    """Test that scraper class can be instantiated"""
    try:
        from app import CourtDataScraper
        scraper = CourtDataScraper()
        assert scraper.base_url == "https://delhihighcourt.nic.in"
        assert "get-case-type-status" in scraper.search_url
    except Exception as e:
        pytest.fail(f"Failed to create scraper: {e}")

if __name__ == '__main__':
    pytest.main([__file__, '-v'])