"""Tests for the TwitterMixin class."""

import pytest
from unittest.mock import patch, MagicMock

from recon.mixins.twitter import TwitterMixin
from recon.core.framework import FrameworkException


class MockFrameworkWithTwitter(TwitterMixin):
    """Mock class combining TwitterMixin with required Framework methods."""
    
    def __init__(self):
        self._keys = {}
        self._added_keys = {}
        self._errors = []
        self._request_calls = []
    
    def get_key(self, name):
        return self._keys.get(name)
    
    def add_key(self, name, value):
        self._added_keys[name] = value
        self._keys[name] = value
    
    def error(self, msg):
        self._errors.append(msg)
    
    def request(self, method, url, **kwargs):
        self._request_calls.append((method, url, kwargs))
        if hasattr(self, '_mock_responses') and self._mock_responses:
            return self._mock_responses.pop(0)
        return self._mock_response


class TestGetTwitterOauthToken:
    """Tests for the get_twitter_oauth_token method."""
    
    def test_returns_cached_token_if_exists(self):
        """Test that cached token is returned without API call."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'cached_bearer_token'
        
        result = framework.get_twitter_oauth_token()
        
        assert result == 'cached_bearer_token'
        assert len(framework._request_calls) == 0
    
    def test_fetches_token_from_api(self):
        """Test that token is fetched from Twitter API."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'consumer_key'
        framework._keys['twitter_secret'] = 'consumer_secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'new_bearer_token'}
        framework._mock_response = mock_response
        
        result = framework.get_twitter_oauth_token()
        
        assert result == 'new_bearer_token'
        assert len(framework._request_calls) == 1
    
    def test_uses_correct_api_endpoint(self):
        """Test that correct Twitter OAuth URL is used."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'key'
        framework._keys['twitter_secret'] = 'secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_twitter_oauth_token()
        
        method, url, kwargs = framework._request_calls[0]
        assert method == 'POST'
        assert url == 'https://api.twitter.com/oauth2/token'
    
    def test_uses_basic_auth_with_credentials(self):
        """Test that basic auth is used with API credentials."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'my_consumer_key'
        framework._keys['twitter_secret'] = 'my_consumer_secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_twitter_oauth_token()
        
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['auth'] == ('my_consumer_key', 'my_consumer_secret')
    
    def test_sends_correct_headers(self):
        """Test that correct Content-Type header is sent."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'key'
        framework._keys['twitter_secret'] = 'secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_twitter_oauth_token()
        
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['headers']['Content-Type'] == 'application/x-www-form-urlencoded;charset=UTF-8'
    
    def test_sends_client_credentials_grant(self):
        """Test that client_credentials grant type is sent."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'key'
        framework._keys['twitter_secret'] = 'secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_twitter_oauth_token()
        
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['data']['grant_type'] == 'client_credentials'
    
    def test_stores_token_after_fetch(self):
        """Test that fetched token is stored."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'key'
        framework._keys['twitter_secret'] = 'secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'stored_token'}
        framework._mock_response = mock_response
        
        framework.get_twitter_oauth_token()
        
        assert framework._added_keys['twitter_token'] == 'stored_token'
    
    def test_raises_on_error_response(self):
        """Test that errors in response raise exception."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'key'
        framework._keys['twitter_secret'] = 'secret'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'errors': [
                {'message': 'Invalid credentials', 'label': 'authentication_error'}
            ]
        }
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException) as exc_info:
            framework.get_twitter_oauth_token()
        
        assert 'Invalid credentials' in str(exc_info.value)
        assert 'authentication_error' in str(exc_info.value)


class TestSearchTwitterApi:
    """Tests for the search_twitter_api method."""
    
    def test_uses_bearer_token(self):
        """Test that bearer token is used in authorization header."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'my_bearer_token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'statuses': [],
            'search_metadata': {}
        }
        framework._mock_response = mock_response
        
        framework.search_twitter_api({'q': 'test'})
        
        _, _, kwargs = framework._request_calls[0]
        assert kwargs['headers']['Authorization'] == 'Bearer my_bearer_token'
    
    def test_uses_correct_api_endpoint(self):
        """Test that correct search API URL is used."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'statuses': [], 'search_metadata': {}}
        framework._mock_response = mock_response
        
        framework.search_twitter_api({'q': 'test'})
        
        _, url, _ = framework._request_calls[0]
        assert url == 'https://api.twitter.com/1.1/search/tweets.json'
    
    def test_returns_statuses(self):
        """Test that statuses are returned from response."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'statuses': [
                {'id': 1, 'text': 'Tweet 1'},
                {'id': 2, 'text': 'Tweet 2'}
            ],
            'search_metadata': {}
        }
        framework._mock_response = mock_response
        
        result = framework.search_twitter_api({'q': 'test'})
        
        assert len(result) == 2
        assert result[0]['text'] == 'Tweet 1'
    
    def test_raises_on_error_in_response(self):
        """Test that error key in response raises exception."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'error': 'Rate limit exceeded'
        }
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException) as exc_info:
            framework.search_twitter_api({'q': 'test'})
        
        assert 'Rate limit exceeded' in str(exc_info.value)
    
    def test_raises_on_errors_in_response(self):
        """Test that errors key in response raises exception."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'errors': [{'code': 88, 'message': 'Rate limit exceeded'}]
        }
        framework._mock_response = mock_response
        
        with pytest.raises(FrameworkException):
            framework.search_twitter_api({'q': 'test'})
    
    @patch('recon.mixins.twitter.time.sleep')
    def test_rate_limits_when_limit_true(self, mock_sleep):
        """Test that rate limiting sleep is called when limit=True."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'statuses': [], 'search_metadata': {}}
        framework._mock_response = mock_response
        
        framework.search_twitter_api({'q': 'test'}, limit=True)
        
        mock_sleep.assert_called_with(2)
    
    def test_no_rate_limit_when_limit_false(self):
        """Test that no sleep when limit=False."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'statuses': [], 'search_metadata': {}}
        framework._mock_response = mock_response
        
        with patch('recon.mixins.twitter.time.sleep') as mock_sleep:
            framework.search_twitter_api({'q': 'test'}, limit=False)
            mock_sleep.assert_not_called()
    
    def test_paginates_using_next_results(self):
        """Test that pagination follows next_results link."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        response1 = MagicMock()
        response1.json.return_value = {
            'statuses': [{'id': 1}],
            'search_metadata': {
                'next_results': '?max_id=12345&q=test'
            }
        }
        
        response2 = MagicMock()
        response2.json.return_value = {
            'statuses': [{'id': 2}],
            'search_metadata': {}
        }
        
        framework._mock_responses = [response1, response2]
        
        result = framework.search_twitter_api({'q': 'test'})
        
        assert len(result) == 2
        assert len(framework._request_calls) == 2
    
    def test_sets_max_id_on_pagination(self):
        """Test that max_id is set from next_results on pagination."""
        # Track params at call time
        params_at_call = []
        
        class TrackingFramework(MockFrameworkWithTwitter):
            def request(self, method, url, **kwargs):
                # Copy the params dict to capture state at call time
                params_at_call.append(dict(kwargs.get('params', {})))
                self._request_calls.append((method, url, kwargs))
                if hasattr(self, '_mock_responses') and self._mock_responses:
                    return self._mock_responses.pop(0)
                return self._mock_response
        
        framework = TrackingFramework()
        framework._keys['twitter_token'] = 'token'
        
        response1 = MagicMock()
        response1.json.return_value = {
            'statuses': [{'id': 1}],
            'search_metadata': {
                'next_results': '?max_id=98765&q=test'
            }
        }
        
        response2 = MagicMock()
        response2.json.return_value = {
            'statuses': [{'id': 2}],
            'search_metadata': {}
        }
        
        framework._mock_responses = [response1, response2]
        
        framework.search_twitter_api({'q': 'test'})
        
        # Second request should have max_id
        assert len(params_at_call) == 2
        assert params_at_call[1].get('max_id') == '98765'


class TestTwitterMixinEdgeCases:
    """Edge case tests for TwitterMixin."""
    
    def test_token_fetch_then_search(self):
        """Test full flow of fetching token then searching."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_api'] = 'api_key'
        framework._keys['twitter_secret'] = 'api_secret'
        
        # First call fetches token
        token_response = MagicMock()
        token_response.json.return_value = {'access_token': 'fetched_token'}
        
        # Second call is search
        search_response = MagicMock()
        search_response.json.return_value = {
            'statuses': [{'text': 'Found tweet'}],
            'search_metadata': {}
        }
        
        framework._mock_responses = [token_response, search_response]
        
        result = framework.search_twitter_api({'q': 'test'})
        
        # Should have made 2 requests (token + search)
        assert len(framework._request_calls) == 2
        assert len(result) == 1
        assert result[0]['text'] == 'Found tweet'
    
    def test_empty_statuses_returned(self):
        """Test that empty statuses list is returned for no results."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'statuses': [],
            'search_metadata': {}
        }
        framework._mock_response = mock_response
        
        result = framework.search_twitter_api({'q': 'nonexistent'})
        
        assert result == []
    
    def test_multiple_pages_accumulate_results(self):
        """Test that results from multiple pages are accumulated."""
        framework = MockFrameworkWithTwitter()
        framework._keys['twitter_token'] = 'token'
        
        responses = []
        for i in range(3):
            resp = MagicMock()
            resp.json.return_value = {
                'statuses': [{'id': i}],
                'search_metadata': {
                    'next_results': f'?max_id={1000-i}&q=test'
                } if i < 2 else {}
            }
            responses.append(resp)
        
        framework._mock_responses = responses
        
        result = framework.search_twitter_api({'q': 'test'})
        
        assert len(result) == 3
        assert [r['id'] for r in result] == [0, 1, 2]
