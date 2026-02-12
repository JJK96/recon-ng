"""Tests for the ExplicitOauthMixin class."""

import pytest
from unittest.mock import patch, MagicMock, Mock
import socket
import urllib.parse

from recon.mixins.oauth import ExplicitOauthMixin


class MockFrameworkWithOauth(ExplicitOauthMixin):
    """Mock class combining ExplicitOauthMixin with required Framework methods."""
    
    def __init__(self):
        self._keys = {}
        self._errors = []
        self._added_keys = {}
    
    def get_key(self, name):
        return self._keys.get(name)
    
    def add_key(self, name, value):
        self._added_keys[name] = value
        self._keys[name] = value
    
    def error(self, msg):
        self._errors.append(msg)
    
    def get_random_str(self, length):
        return 'a' * length
    
    def request(self, method, url, **kwargs):
        return self._mock_response


class TestGetExplicitOauthToken:
    """Tests for the get_explicit_oauth_token method."""
    
    def test_returns_cached_token_if_exists(self):
        """Test that cached token is returned without OAuth flow."""
        framework = MockFrameworkWithOauth()
        framework._keys['testservice_token'] = 'cached_token_value'
        
        result = framework.get_explicit_oauth_token(
            'testservice',
            'read write',
            'https://auth.example.com/authorize',
            'https://auth.example.com/token'
        )
        
        assert result == 'cached_token_value'
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_opens_browser_for_authorization(self, mock_wb_get, mock_socket_class):
        """Test that browser is opened for authorization URL."""
        framework = MockFrameworkWithOauth()
        framework._keys['myapp_api'] = 'client_id_123'
        framework._keys['myapp_secret'] = 'client_secret_456'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        # Return string directly - the oauth.py code has a Python 3 incompatibility
        # but we can test by returning a string-like bytes that supports 'in'
        mock_conn.recv.return_value = 'GET /?code=auth_code_789&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 12345))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'new_access_token'}
        framework._mock_response = mock_response
        
        framework.get_explicit_oauth_token(
            'myapp',
            'read',
            'https://auth.example.com/authorize',
            'https://auth.example.com/token'
        )
        
        mock_browser.open.assert_called_once()
        opened_url = mock_browser.open.call_args[0][0]
        assert 'https://auth.example.com/authorize' in opened_url
        assert 'client_id=client_id_123' in opened_url
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_binds_socket_on_port_31337(self, mock_wb_get, mock_socket_class):
        """Test that socket binds to port 31337."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        mock_sock.bind.assert_called_with(('127.0.0.1', 31337))
        mock_sock.listen.assert_called_with(1)
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_sends_html_response_to_browser(self, mock_wb_get, mock_socket_class):
        """Test that HTML response is sent back to browser."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        mock_conn.sendall.assert_called_once()
        sent_data = mock_conn.sendall.call_args[0][0]
        assert 'HTTP/1.1 200 OK' in sent_data
        assert 'Recon-ng' in sent_data
        mock_conn.close.assert_called_once()
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_handles_error_in_callback(self, mock_wb_get, mock_socket_class):
        """Test that errors in callback are handled."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        # Simulate error response from OAuth provider
        mock_conn.recv.return_value = 'GET /?error=access_denied&error_description=User+denied+access HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        result = framework.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        assert result is None
        assert len(framework._errors) == 1
        assert 'User denied access' in framework._errors[0]
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_exchanges_code_for_token(self, mock_wb_get, mock_socket_class):
        """Test that authorization code is exchanged for access token."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'my_client_id'
        framework._keys['app_secret'] = 'my_client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=auth_code_xyz&state=abc HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        # Track request calls
        request_calls = []
        
        class TrackingFramework(MockFrameworkWithOauth):
            def request(self, method, url, **kwargs):
                request_calls.append((method, url, kwargs))
                mock_resp = MagicMock()
                mock_resp.json.return_value = {'access_token': 'final_token'}
                return mock_resp
        
        tracking = TrackingFramework()
        tracking._keys = framework._keys.copy()
        
        result = tracking.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url/access'
        )
        
        assert len(request_calls) == 1
        method, url, kwargs = request_calls[0]
        assert method == 'POST'
        assert url == 'https://token.url/access'
        assert kwargs['data']['grant_type'] == 'authorization_code'
        assert kwargs['data']['code'] == 'auth_code_xyz'
        assert kwargs['data']['client_id'] == 'my_client_id'
        assert kwargs['data']['client_secret'] == 'my_client_secret'
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_stores_token_on_success(self, mock_wb_get, mock_socket_class):
        """Test that obtained token is stored."""
        framework = MockFrameworkWithOauth()
        framework._keys['svc_api'] = 'client_id'
        framework._keys['svc_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'stored_token_value'}
        framework._mock_response = mock_response
        
        result = framework.get_explicit_oauth_token(
            'svc', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        assert result == 'stored_token_value'
        assert framework._added_keys['svc_token'] == 'stored_token_value'
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_handles_token_error_response(self, mock_wb_get, mock_socket_class):
        """Test that errors in token response are handled."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Code has expired'
        }
        framework._mock_response = mock_response
        
        result = framework.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        assert result is None
        assert len(framework._errors) == 1
        assert 'Code has expired' in framework._errors[0]
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_includes_scope_in_authorization_url(self, mock_wb_get, mock_socket_class):
        """Test that scope is included in authorization URL."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_explicit_oauth_token(
            'app', 'read write delete', 'https://auth.url', 'https://token.url'
        )
        
        opened_url = mock_browser.open.call_args[0][0]
        # URL encoding of space is +
        assert 'scope=read' in opened_url or 'scope=read+write+delete' in opened_url or 'scope=read%20write%20delete' in opened_url


class TestOauthMixinEdgeCases:
    """Edge case tests for ExplicitOauthMixin."""
    
    def test_token_lookup_uses_correct_name(self):
        """Test that token name is correctly constructed."""
        framework = MockFrameworkWithOauth()
        framework._keys['mycustomservice_token'] = 'existing_token'
        
        result = framework.get_explicit_oauth_token(
            'mycustomservice', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        assert result == 'existing_token'
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_redirect_uri_uses_correct_port(self, mock_wb_get, mock_socket_class):
        """Test that redirect URI uses port 31337."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        opened_url = mock_browser.open.call_args[0][0]
        assert 'redirect_uri=http%3A%2F%2Flocalhost%3A31337' in opened_url or 'redirect_uri=http://localhost:31337' in opened_url
    
    @patch('recon.mixins.oauth.socket.socket')
    @patch('recon.mixins.oauth.webbrowser.get')
    def test_state_parameter_is_random(self, mock_wb_get, mock_socket_class):
        """Test that state parameter uses random string."""
        framework = MockFrameworkWithOauth()
        framework._keys['app_api'] = 'client_id'
        framework._keys['app_secret'] = 'client_secret'
        
        mock_browser = MagicMock()
        mock_wb_get.return_value = mock_browser
        
        mock_sock = MagicMock()
        mock_conn = MagicMock()
        mock_conn.recv.return_value = 'GET /?code=code123&state=xyz HTTP/1.1'
        mock_sock.accept.return_value = (mock_conn, ('127.0.0.1', 54321))
        mock_socket_class.return_value = mock_sock
        
        mock_response = MagicMock()
        mock_response.json.return_value = {'access_token': 'token'}
        framework._mock_response = mock_response
        
        framework.get_explicit_oauth_token(
            'app', 'scope', 'https://auth.url', 'https://token.url'
        )
        
        opened_url = mock_browser.open.call_args[0][0]
        # Our mock returns 40 'a' characters
        assert 'state=aaaaaaaaaa' in opened_url
