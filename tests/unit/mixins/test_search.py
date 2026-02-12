"""Tests for the search mixins (Google, Bing, Shodan)."""

import pytest
from unittest.mock import patch, MagicMock

from recon.mixins.search import (
    GoogleWebMixin, GoogleAPIMixin, BingAPIMixin, ShodanAPIMixin
)
from recon.core.framework import FrameworkException


class MockFrameworkWithSearch:
    """Base mock class for search mixins."""
    
    def __init__(self):
        self._keys = {}
        self._errors = []
        self._verbose_messages = []
        self._request_calls = []
    
    def get_key(self, name):
        return self._keys.get(name)
    
    def error(self, msg):
        self._errors.append(msg)
    
    def verbose(self, msg):
        self._verbose_messages.append(msg)
    
    def request(self, method, url, **kwargs):
        self._request_calls.append((method, url, kwargs))
        if hasattr(self, '_mock_responses') and self._mock_responses:
            return self._mock_responses.pop(0)
        return self._mock_response


class MockGoogleWeb(GoogleWebMixin, MockFrameworkWithSearch):
    """Mock for GoogleWebMixin."""
    pass


class MockGoogleAPI(GoogleAPIMixin, MockFrameworkWithSearch):
    """Mock for GoogleAPIMixin."""
    pass


class MockBingAPI(BingAPIMixin, MockFrameworkWithSearch):
    """Mock for BingAPIMixin."""
    pass


class MockShodanAPI(ShodanAPIMixin, MockFrameworkWithSearch):
    """Mock for ShodanAPIMixin."""
    pass


class TestGoogleWebMixin:
    """Tests for the GoogleWebMixin class."""
    
    def test_search_google_web_logs_verbose(self):
        """Test that search logs verbose message."""
        framework = MockGoogleWeb()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>No results</body></html>'
        framework._mock_response = mock_response
        
        framework.search_google_web('test query')
        
        assert len(framework._verbose_messages) == 1
        assert 'test query' in framework._verbose_messages[0]
    
    def test_search_google_web_uses_correct_url(self):
        """Test that correct Google URL is used."""
        framework = MockGoogleWeb()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>No results</body></html>'
        framework._mock_response = mock_response
        
        framework.search_google_web('test')
        
        _, url, kwargs = framework._request_calls[0]
        assert url == 'https://www.google.com/search'
        assert kwargs['params']['q'] == 'test'
    
    def test_search_google_web_handles_captcha_302(self):
        """Test that 302 redirect (captcha) is handled."""
        framework = MockGoogleWeb()
        
        mock_response = MagicMock()
        mock_response.status_code = 302
        framework._mock_response = mock_response
        
        result = framework.search_google_web('query')
        
        assert result == []
        assert len(framework._errors) == 1
        assert 'CAPTCHA' in framework._errors[0]
    
    def test_search_google_web_handles_unknown_error(self):
        """Test that unknown HTTP errors are handled."""
        framework = MockGoogleWeb()
        
        mock_response = MagicMock()
        mock_response.status_code = 503
        framework._mock_response = mock_response
        
        result = framework.search_google_web('query')
        
        assert result == []
        assert len(framework._errors) == 1
        assert 'unknown error' in framework._errors[0]
    
    def test_search_google_web_extracts_links(self):
        """Test that links are extracted from Google results."""
        framework = MockGoogleWeb()
        
        html_content = '''
        <html>
        <body>
            <a href="/url?q=https://example.com/page1&sa=U">Result 1</a>
            <a href="/url?q=https://example.org/page2&sa=U">Result 2</a>
            <a href="/images?q=test">Image link - should be ignored</a>
        </body>
        </html>
        '''
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        framework._mock_response = mock_response
        
        result = framework.search_google_web('test')
        
        assert 'https://example.com/page1' in result
        assert 'https://example.org/page2' in result
    
    def test_search_google_web_excludes_webcache_links(self):
        """Test that webcache links are excluded."""
        framework = MockGoogleWeb()
        
        html_content = '''
        <html>
        <body>
            <a href="/url?q=https://example.com/page1&sa=U">Result 1</a>
            <a href="/url?q=http://webcache.googleusercontent.com/search?q=cache:123">Cached</a>
        </body>
        </html>
        '''
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html_content
        framework._mock_response = mock_response
        
        result = framework.search_google_web('test')
        
        assert len(result) == 1
        assert 'webcache' not in str(result)
    
    def test_search_google_web_respects_limit(self):
        """Test that page limit is respected."""
        framework = MockGoogleWeb()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html><body>>Next</</body></html>'
        framework._mock_response = mock_response
        
        framework.search_google_web('test', limit=1)
        
        # Should only make 1 request due to limit
        assert len(framework._request_calls) == 1
    
    def test_search_google_web_paginates(self):
        """Test that pagination works when Next link present."""
        framework = MockGoogleWeb()
        
        response1 = MagicMock()
        response1.status_code = 200
        response1.text = '<html><body><a href="/url?q=https://page1.com&">R1</a>>Next</</body></html>'
        
        response2 = MagicMock()
        response2.status_code = 200
        response2.text = '<html><body><a href="/url?q=https://page2.com&">R2</a></body></html>'
        
        framework._mock_responses = [response1, response2]
        
        result = framework.search_google_web('test', limit=0)  # limit=0 means no limit
        
        assert len(framework._request_calls) == 2
    
    def test_search_google_web_sets_custom_user_agent(self):
        """Test that custom Lynx user agent is used."""
        framework = MockGoogleWeb()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '<html></html>'
        framework._mock_response = mock_response
        
        framework.search_google_web('test')
        
        _, _, kwargs = framework._request_calls[0]
        assert 'Lynx' in kwargs['headers']['user-agent']


class TestGoogleAPIMixin:
    """Tests for the GoogleAPIMixin class."""
    
    def test_search_google_api_uses_correct_url(self):
        """Test that correct API URL is used."""
        framework = MockGoogleAPI()
        framework._keys['google_api'] = 'test_api_key'
        framework._keys['google_cse'] = 'test_cse_id'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        framework._mock_response = mock_response
        
        framework.search_google_api('test query')
        
        _, url, kwargs = framework._request_calls[0]
        assert url == 'https://www.googleapis.com/customsearch/v1'
        assert kwargs['params']['key'] == 'test_api_key'
        assert kwargs['params']['cx'] == 'test_cse_id'
        assert kwargs['params']['q'] == 'test query'
    
    def test_search_google_api_logs_verbose(self):
        """Test that verbose message is logged."""
        framework = MockGoogleAPI()
        framework._keys['google_api'] = 'key'
        framework._keys['google_cse'] = 'cse'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        framework._mock_response = mock_response
        
        framework.search_google_api('my query')
        
        assert len(framework._verbose_messages) == 1
        assert 'my query' in framework._verbose_messages[0]
    
    def test_search_google_api_returns_items(self):
        """Test that items are returned from API response."""
        framework = MockGoogleAPI()
        framework._keys['google_api'] = 'key'
        framework._keys['google_cse'] = 'cse'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'items': [
                {'title': 'Result 1', 'link': 'https://example.com'},
                {'title': 'Result 2', 'link': 'https://test.com'}
            ]
        }
        framework._mock_response = mock_response
        
        result = framework.search_google_api('query')
        
        assert len(result) == 2
        assert result[0]['title'] == 'Result 1'
    
    def test_search_google_api_raises_on_invalid_json(self):
        """Test that exception is raised on invalid JSON."""
        framework = MockGoogleAPI()
        framework._keys['google_api'] = 'key'
        framework._keys['google_cse'] = 'cse'
        
        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.text = 'Invalid response'
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException) as exc_info:
            framework.search_google_api('query')
        
        assert 'Invalid JSON' in str(exc_info.value)
    
    def test_search_google_api_paginates(self):
        """Test that API paginates using nextPage."""
        framework = MockGoogleAPI()
        framework._keys['google_api'] = 'key'
        framework._keys['google_cse'] = 'cse'
        
        response1 = MagicMock()
        response1.json.return_value = {
            'items': [{'id': 1}],
            'queries': {
                'nextPage': [{'startIndex': 11}]
            }
        }
        
        response2 = MagicMock()
        response2.json.return_value = {
            'items': [{'id': 2}]
        }
        
        framework._mock_responses = [response1, response2]
        
        result = framework.search_google_api('query', limit=0)
        
        assert len(result) == 2
        assert len(framework._request_calls) == 2
    
    def test_search_google_api_respects_limit(self):
        """Test that limit stops pagination."""
        framework = MockGoogleAPI()
        framework._keys['google_api'] = 'key'
        framework._keys['google_cse'] = 'cse'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'items': [{'id': 1}],
            'queries': {'nextPage': [{'startIndex': 11}]}
        }
        framework._mock_response = mock_response
        
        framework.search_google_api('query', limit=1)
        
        assert len(framework._request_calls) == 1


class TestBingAPIMixin:
    """Tests for the BingAPIMixin class."""
    
    def test_search_bing_api_uses_correct_url(self):
        """Test that correct Bing API URL is used."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'bing_key'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'webPages': {'value': [], 'totalEstimatedMatches': 0}}
        framework._mock_response = mock_response
        
        framework.search_bing_api('test')
        
        _, url, kwargs = framework._request_calls[0]
        assert url == 'https://api.bing.microsoft.com/v7.0/search'
        assert kwargs['headers']['Ocp-Apim-Subscription-Key'] == 'bing_key'
    
    def test_search_bing_api_logs_verbose(self):
        """Test that verbose message is logged."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'webPages': {'value': [], 'totalEstimatedMatches': 0}}
        framework._mock_response = mock_response
        
        framework.search_bing_api('my query')
        
        assert 'my query' in framework._verbose_messages[0]
    
    def test_search_bing_api_returns_results(self):
        """Test that web page results are returned."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'webPages': {
                'value': [{'name': 'Result 1'}, {'name': 'Result 2'}],
                'totalEstimatedMatches': 100
            }
        }
        framework._mock_response = mock_response
        
        result = framework.search_bing_api('query', limit=1)
        
        assert len(result) == 2
        assert result[0]['name'] == 'Result 1'
    
    def test_search_bing_api_raises_on_invalid_json(self):
        """Test that exception is raised on invalid JSON."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = None
        mock_response.text = 'Invalid'
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException):
            framework.search_bing_api('query')
    
    def test_search_bing_api_raises_on_401(self):
        """Test that exception is raised on 401 error."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'invalid_key'
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'error': {
                'code': '401',
                'message': 'Access denied'
            }
        }
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException) as exc_info:
            framework.search_bing_api('query')
        
        assert 'Access denied' in str(exc_info.value)
    
    def test_search_bing_api_returns_early_on_no_webpages(self):
        """Test that empty results are returned when no webPages."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No webPages key
        framework._mock_response = mock_response
        
        result = framework.search_bing_api('no results query')
        
        assert result == []
    
    def test_search_bing_api_paginates(self):
        """Test that pagination works with offset."""
        framework = MockBingAPI()
        framework._keys['bing_api'] = 'key'
        
        response1 = MagicMock()
        response1.status_code = 200
        response1.json.return_value = {
            'webPages': {
                'value': [{'id': i} for i in range(50)],
                'totalEstimatedMatches': 100
            }
        }
        
        response2 = MagicMock()
        response2.status_code = 200
        response2.json.return_value = {
            'webPages': {
                'value': [{'id': i} for i in range(50, 100)],
                'totalEstimatedMatches': 100
            }
        }
        
        # Add a third response to handle the termination check
        response3 = MagicMock()
        response3.status_code = 200
        response3.json.return_value = {
            'webPages': {
                'value': [],
                'totalEstimatedMatches': 100
            }
        }
        
        framework._mock_responses = [response1, response2, response3]
        
        result = framework.search_bing_api('query', limit=2)
        
        # With limit=2, should stop after 2 pages
        assert len(framework._request_calls) == 2
        assert len(result) == 100


class TestShodanAPIMixin:
    """Tests for the ShodanAPIMixin class."""
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_uses_correct_url(self, mock_sleep):
        """Test that correct Shodan API URL is used."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'shodan_key'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'matches': []}
        framework._mock_response = mock_response
        
        framework.search_shodan_api('test')
        
        _, url, kwargs = framework._request_calls[0]
        assert url == 'https://api.shodan.io/shodan/host/search'
        assert kwargs['params']['key'] == 'shodan_key'
        assert kwargs['params']['query'] == 'test'
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_logs_verbose(self, mock_sleep):
        """Test that verbose message is logged."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'matches': []}
        framework._mock_response = mock_response
        
        framework.search_shodan_api('my query')
        
        assert 'my query' in framework._verbose_messages[0]
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_returns_matches(self, mock_sleep):
        """Test that matches are returned."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'matches': [
                {'ip_str': '1.2.3.4', 'port': 80},
                {'ip_str': '5.6.7.8', 'port': 443}
            ]
        }
        framework._mock_response = mock_response
        
        result = framework.search_shodan_api('query', limit=1)
        
        assert len(result) == 2
        assert result[0]['ip_str'] == '1.2.3.4'
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_raises_on_invalid_json(self, mock_sleep):
        """Test that exception is raised on invalid JSON."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.text = 'Invalid'
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException):
            framework.search_shodan_api('query')
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_raises_on_error(self, mock_sleep):
        """Test that API errors are raised as exceptions."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'error': 'Invalid API key'}
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException) as exc_info:
            framework.search_shodan_api('query')
        
        assert 'Invalid API key' in str(exc_info.value)
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_stops_on_empty_matches(self, mock_sleep):
        """Test that pagination stops when no more matches."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'key'
        
        response1 = MagicMock()
        response1.json.return_value = {'matches': [{'id': 1}]}
        
        response2 = MagicMock()
        response2.json.return_value = {'matches': []}
        
        framework._mock_responses = [response1, response2]
        
        result = framework.search_shodan_api('query', limit=0)
        
        assert len(result) == 1
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_respects_rate_limit(self, mock_sleep):
        """Test that 1 second sleep is called for rate limiting."""
        framework = MockShodanAPI()
        framework._keys['shodan_api'] = 'key'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'matches': []}
        framework._mock_response = mock_response
        
        framework.search_shodan_api('query')
        
        mock_sleep.assert_called_with(1)
    
    @patch('recon.mixins.search.time.sleep')
    def test_search_shodan_api_paginates_with_page(self, mock_sleep):
        """Test that pagination increments page number."""
        page_values = []
        
        class TrackingShodan(MockShodanAPI):
            def request(self, method, url, **kwargs):
                page_values.append(kwargs.get('params', {}).get('page'))
                self._request_calls.append((method, url, kwargs))
                if hasattr(self, '_mock_responses') and self._mock_responses:
                    return self._mock_responses.pop(0)
                return self._mock_response
        
        framework = TrackingShodan()
        framework._keys['shodan_api'] = 'key'
        
        response1 = MagicMock()
        response1.json.return_value = {'matches': [{'id': 1}]}
        
        response2 = MagicMock()
        response2.json.return_value = {'matches': [{'id': 2}]}
        
        response3 = MagicMock()
        response3.json.return_value = {'matches': []}
        
        framework._mock_responses = [response1, response2, response3]
        
        framework.search_shodan_api('query', limit=0)
        
        # First call has no page param, subsequent calls have page=2, page=3, etc.
        assert page_values[0] is None  # First request, no page param
        assert page_values[1] == 2     # Second request
