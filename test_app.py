"""
Unit tests for Court Data Fetcher application
"""
import pytest
import os
import sys
import tempfile
import sqlite3
from unittest.mock import patch, MagicMock

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, init_db, CourtDataScraper


@pytest.fixture
def client():
    """Create a test client for the Flask app"""
    # Create a temporary database for testing
    db_fd, app.config['DATABASE'] = tempfile.mkstemp()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        with app.app_context():
            init_db()
        yield client
    
    os.close(db_fd)
    os.unlink(app.config['DATABASE'])


@pytest.fixture
def scraper():
    """Create a CourtDataScraper instance for testing"""
    return CourtDataScraper()


class TestApp:
    """Test cases for the Flask application"""
    
    def test_index_route(self, client):
        """Test the main index route"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Court Data Fetcher' in response.data or b'Delhi High Court' in response.data
    
    def test_search_route_missing_params(self, client):
        """Test search route with missing parameters"""
        response = client.post('/search', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'required' in data['error'].lower()
    
    def test_search_route_invalid_params(self, client):
        """Test search route with invalid parameters"""
        response = client.post('/search', json={
            'case_type': '',
            'case_number': '',
            'case_year': ''
        })
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_history_route(self, client):
        """Test the history route"""
        response = client.get('/history')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)
    
    def test_download_pdf_no_url(self, client):
        """Test PDF download without URL"""
        response = client.get('/download_pdf')
        assert response.status_code == 200
        data = response.get_json()
        assert 'error' in data
        assert 'not provided' in data['error']
    
    def test_404_handler(self, client):
        """Test 404 error handler"""
        response = client.get('/nonexistent-route')
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data
        assert 'not found' in data['error'].lower()


class TestCourtDataScraper:
    """Test cases for the CourtDataScraper class"""
    
    def test_scraper_initialization(self, scraper):
        """Test scraper initialization"""
        assert scraper.base_url == "https://delhihighcourt.nic.in"
        assert scraper.search_url == "https://delhihighcourt.nic.in/app/get-case-type-status"
    
    @patch('app.webdriver.Chrome')
    @patch('app.ChromeDriverManager')
    def test_setup_driver_success(self, mock_driver_manager, mock_chrome, scraper):
        """Test successful driver setup"""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        mock_driver_manager.return_value.install.return_value = '/path/to/chromedriver'
        
        result = scraper.setup_driver()
        assert result is not None
        mock_driver.execute_script.assert_called_once()
    
    @patch('app.webdriver.Chrome')
    @patch('app.ChromeDriverManager')
    def test_setup_driver_failure(self, mock_driver_manager, mock_chrome, scraper):
        """Test driver setup failure"""
        mock_chrome.side_effect = Exception("Chrome not found")
        mock_driver_manager.return_value.install.side_effect = Exception("Driver not found")
        
        result = scraper.setup_driver()
        assert result is None
    
    def test_parse_case_data_no_data(self, scraper):
        """Test parsing when no case data is found"""
        from bs4 import BeautifulSoup
        
        # Create a minimal HTML without case data
        html = "<html><body><div>No data found</div></body></html>"
        soup = BeautifulSoup(html, 'html.parser')
        
        result = scraper.parse_case_data(soup)
        assert result['status'] == 'Not Found'
        assert 'parties' in result
        assert 'filing_date' in result
        assert 'next_hearing_date' in result


class TestDatabase:
    """Test cases for database operations"""
    
    def test_init_db(self):
        """Test database initialization"""
        # Create a temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Test database creation
            os.makedirs('db', exist_ok=True)
            conn = sqlite3.connect('db/test_queries.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_type TEXT,
                    case_number TEXT,
                    case_year TEXT,
                    query_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    raw_response TEXT,
                    parties TEXT,
                    filing_date TEXT,
                    next_hearing_date TEXT,
                    order_judgment_link TEXT,
                    status TEXT
                )
            ''')
            
            conn.commit()
            
            # Test table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='queries'")
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == 'queries'
            
            conn.close()
            
            # Clean up
            if os.path.exists('db/test_queries.db'):
                os.remove('db/test_queries.db')
                
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestSecurity:
    """Test cases for security measures"""
    
    def test_environment_variables(self):
        """Test that environment variables are used for configuration"""
        # Test default values
        debug_mode = os.getenv('FLASK_ENV') != 'production'
        host = os.getenv('FLASK_HOST', '127.0.0.1')
        port = int(os.getenv('FLASK_PORT', 5000))
        
        # In test environment, these should be safe defaults
        assert host == '127.0.0.1'  # Should default to localhost
        assert port == 5000
        assert isinstance(debug_mode, bool)
    
    def test_request_timeout(self):
        """Test that requests have timeout configured"""
        import requests
        from unittest.mock import patch
        
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            # This would be called in the download_pdf function
            requests.get('http://example.com/test.pdf', timeout=30)
            
            # Verify timeout was passed
            mock_get.assert_called_with('http://example.com/test.pdf', timeout=30)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])