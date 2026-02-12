"""Tests for the GithubMixin class."""

import pytest
from unittest.mock import patch, MagicMock

from recon.mixins.github import GithubMixin


class MockFrameworkWithGithub(GithubMixin):
    """Mock class combining GithubMixin with required Framework methods."""
    
    def __init__(self):
        self._keys = {
            'github_api': 'test_github_token',
        }
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


class TestQueryGithubApi:
    """Tests for the query_github_api method."""
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_returns_list_results(self, mock_sleep):
        """Test that list responses are extended to results."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'id': 1, 'name': 'item1'},
            {'id': 2, 'name': 'item2'}
        ]
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        result = framework.query_github_api('/test/endpoint')
        
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 2
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_returns_dict_results(self, mock_sleep):
        """Test that dict responses are appended to results."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': [{'id': 1}], 'total': 1}
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        result = framework.query_github_api('/search/code')
        
        assert len(result) == 1
        assert result[0]['items'] == [{'id': 1}]
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_uses_authorization_header(self, mock_sleep):
        """Test that authorization token is sent in header."""
        framework = MockFrameworkWithGithub()
        framework._keys['github_api'] = 'my_special_token'
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.query_github_api('/test')
        
        assert len(framework._request_calls) == 1
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['headers']['Authorization'] == 'token my_special_token'
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_respects_rate_limit(self, mock_sleep):
        """Test that rate limiting sleep is called."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.query_github_api('/test')
        
        mock_sleep.assert_called_with(2)
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_handles_404_silently(self, mock_sleep):
        """Test that 404 errors don't produce error messages."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        result = framework.query_github_api('/nonexistent')
        
        assert result == []
        assert len(framework._errors) == 0
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_handles_other_errors(self, mock_sleep):
        """Test that non-404 errors produce error messages."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {'message': 'Rate limit exceeded'}
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        result = framework.query_github_api('/test')
        
        assert result == []
        assert len(framework._errors) == 1
        assert 'Rate limit exceeded' in framework._errors[0]
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_paginates_when_next_link_present(self, mock_sleep):
        """Test that pagination follows rel=next links."""
        framework = MockFrameworkWithGithub()
        
        # First page
        response1 = MagicMock()
        response1.status_code = 200
        response1.json.return_value = [{'id': 1}]
        response1.headers = {'link': '<url>; rel="next"'}
        
        # Second page (last)
        response2 = MagicMock()
        response2.status_code = 200
        response2.json.return_value = [{'id': 2}]
        response2.headers = {}
        
        framework._mock_responses = [response1, response2]
        
        result = framework.query_github_api('/test')
        
        assert len(result) == 2
        assert len(framework._request_calls) == 2
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_respects_max_pages_option(self, mock_sleep):
        """Test that max_pages option limits pagination."""
        framework = MockFrameworkWithGithub()
        
        # Response with next link that should be ignored due to max_pages
        response1 = MagicMock()
        response1.status_code = 200
        response1.json.return_value = [{'id': 1}]
        response1.headers = {'link': '<url>; rel="next"'}
        
        framework._mock_responses = [response1]
        
        result = framework.query_github_api('/test', options={'max_pages': 1})
        
        # Should only make 1 request despite next link
        assert len(framework._request_calls) == 1
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_passes_payload_parameters(self, mock_sleep):
        """Test that payload parameters are sent."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.query_github_api('/search/code', payload={'q': 'test query'})
        
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['params']['q'] == 'test query'
        assert kwargs['params']['page'] == 1
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_increments_page_on_pagination(self, mock_sleep):
        """Test that page number increments correctly."""
        # We need to track page values at call time since the payload dict is mutated
        page_values = []
        
        class TrackingFramework(MockFrameworkWithGithub):
            def request(self, method, url, **kwargs):
                # Capture page value at call time
                page_values.append(kwargs.get('params', {}).get('page'))
                self._request_calls.append((method, url, kwargs))
                if hasattr(self, '_mock_responses') and self._mock_responses:
                    return self._mock_responses.pop(0)
                return self._mock_response
        
        framework = TrackingFramework()
        
        response1 = MagicMock()
        response1.status_code = 200
        response1.json.return_value = [{'id': 1}]
        response1.headers = {'link': '<url>; rel="next"'}
        
        response2 = MagicMock()
        response2.status_code = 200
        response2.json.return_value = [{'id': 2}]
        response2.headers = {}
        
        framework._mock_responses = [response1, response2]
        
        framework.query_github_api('/test')
        
        # Check page values were captured correctly
        assert len(page_values) == 2
        assert page_values[0] == 1
        assert page_values[1] == 2


class TestSearchGithubApi:
    """Tests for the search_github_api method."""
    
    @patch('recon.mixins.github.time.sleep')
    def test_search_logs_verbose_message(self, mock_sleep):
        """Test that search logs a verbose message."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.search_github_api('test query')
        
        assert len(framework._verbose_messages) == 1
        assert 'test query' in framework._verbose_messages[0]
    
    @patch('recon.mixins.github.time.sleep')
    def test_search_uses_code_endpoint(self, mock_sleep):
        """Test that search uses /search/code endpoint."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.search_github_api('query')
        
        _, url, kwargs = framework._request_calls[0]
        assert '/search/code' in url
        assert kwargs['params']['q'] == 'query'
    
    @patch('recon.mixins.github.time.sleep')
    def test_search_flattens_items_from_results(self, mock_sleep):
        """Test that items are extracted and flattened from search results."""
        framework = MockFrameworkWithGithub()
        
        response1 = MagicMock()
        response1.status_code = 200
        response1.json.return_value = {
            'items': [{'id': 1}, {'id': 2}]
        }
        response1.headers = {'link': '<url>; rel="next"'}
        
        response2 = MagicMock()
        response2.status_code = 200
        response2.json.return_value = {
            'items': [{'id': 3}]
        }
        response2.headers = {}
        
        framework._mock_responses = [response1, response2]
        
        result = framework.search_github_api('test')
        
        # Should flatten the nested items lists
        assert len(result) == 3
        assert result[0]['id'] == 1
        assert result[1]['id'] == 2
        assert result[2]['id'] == 3
    
    @patch('recon.mixins.github.time.sleep')
    def test_search_returns_empty_list_on_no_results(self, mock_sleep):
        """Test that empty results return empty list."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        result = framework.search_github_api('no results query')
        
        assert result == []


class TestGithubMixinEdgeCases:
    """Edge case tests for GithubMixin."""
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_with_empty_payload(self, mock_sleep):
        """Test query with empty payload."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        result = framework.query_github_api('/test', payload={})
        
        assert result == []
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['params']['page'] == 1
    
    @patch('recon.mixins.github.time.sleep')
    def test_query_constructs_correct_url(self, mock_sleep):
        """Test that base URL is correctly combined with endpoint."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.query_github_api('/users/test/repos')
        
        _, url, _ = framework._request_calls[0]
        assert url == 'https://api.github.com/users/test/repos'
    
    @patch('recon.mixins.github.time.sleep')
    def test_pagination_with_max_pages_none(self, mock_sleep):
        """Test that max_pages=None allows unlimited pagination."""
        framework = MockFrameworkWithGithub()
        
        # Create 3 pages of results
        responses = []
        for i in range(3):
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = [{'id': i}]
            if i < 2:
                resp.headers = {'link': '<url>; rel="next"'}
            else:
                resp.headers = {}
            responses.append(resp)
        
        framework._mock_responses = responses
        
        result = framework.query_github_api('/test', options={'max_pages': None})
        
        assert len(result) == 3
        assert len(framework._request_calls) == 3
    
    @patch('recon.mixins.github.time.sleep')
    def test_search_with_special_characters(self, mock_sleep):
        """Test search with special characters in query."""
        framework = MockFrameworkWithGithub()
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'items': []}
        mock_response.headers = {}
        framework._mock_response = mock_response
        
        framework.search_github_api('repo:owner/name path:*.py "password"')
        
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['params']['q'] == 'repo:owner/name path:*.py "password"'
