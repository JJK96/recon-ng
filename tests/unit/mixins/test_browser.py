"""Tests for the BrowserMixin class."""

import pytest
from unittest.mock import patch, MagicMock
import socket

from recon.mixins.browser import BrowserMixin


class MockFrameworkWithBrowser(BrowserMixin):
    """Mock class combining BrowserMixin with required Framework methods."""
    
    def __init__(self, user_agent='Test-Agent', verbosity=0, proxy=None, timeout=10):
        self._global_options = {
            'user-agent': user_agent,
            'verbosity': verbosity,
            'proxy': proxy,
            'timeout': timeout,
        }


class TestGetBrowser:
    """Tests for the get_browser method."""
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_returns_browser_object(self, mock_browser_class):
        """Test that get_browser returns a mechanize.Browser instance."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser()
        result = framework.get_browser()
        
        assert result == mock_browser
        mock_browser_class.assert_called_once()
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_sets_user_agent(self, mock_browser_class):
        """Test that get_browser configures the user-agent header."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(user_agent='Custom-Agent/1.0')
        framework.get_browser()
        
        assert mock_browser.addheaders == [('User-agent', 'Custom-Agent/1.0')]
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_no_debug_when_verbosity_low(self, mock_browser_class):
        """Test that debug options are not set when verbosity is below 2."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(verbosity=1)
        framework.get_browser()
        
        mock_browser.set_debug_http.assert_not_called()
        mock_browser.set_debug_redirects.assert_not_called()
        mock_browser.set_debug_responses.assert_not_called()
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_enables_debug_when_verbosity_2(self, mock_browser_class):
        """Test that debug options are set when verbosity >= 2."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(verbosity=2)
        framework.get_browser()
        
        mock_browser.set_debug_http.assert_called_once_with(True)
        mock_browser.set_debug_redirects.assert_called_once_with(True)
        mock_browser.set_debug_responses.assert_called_once_with(True)
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_enables_debug_when_verbosity_3(self, mock_browser_class):
        """Test that debug options are set when verbosity is 3 or higher."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(verbosity=3)
        framework.get_browser()
        
        mock_browser.set_debug_http.assert_called_once_with(True)
        mock_browser.set_debug_redirects.assert_called_once_with(True)
        mock_browser.set_debug_responses.assert_called_once_with(True)
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_no_proxy_when_not_set(self, mock_browser_class):
        """Test that proxy is not set when global option is None."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(proxy=None)
        framework.get_browser()
        
        mock_browser.set_proxies.assert_not_called()
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_sets_proxy(self, mock_browser_class):
        """Test that proxy is configured when global option is set."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(proxy='http://proxy.example.com:8080')
        framework.get_browser()
        
        mock_browser.set_proxies.assert_called_once_with({
            'http': 'http://proxy.example.com:8080',
            'https': 'http://proxy.example.com:8080'
        })
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_disables_robots(self, mock_browser_class):
        """Test that robots.txt handling is disabled."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser()
        framework.get_browser()
        
        mock_browser.set_handle_robots.assert_called_once_with(False)
    
    @patch('recon.mixins.browser.socket.setdefaulttimeout')
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_sets_timeout(self, mock_browser_class, mock_settimeout):
        """Test that socket timeout is set from global options."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(timeout=30)
        framework.get_browser()
        
        mock_settimeout.assert_called_once_with(30)
    
    @patch('recon.mixins.browser.socket.setdefaulttimeout')
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_full_configuration(self, mock_browser_class, mock_settimeout):
        """Test get_browser with all options configured."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(
            user_agent='Full-Test-Agent/2.0',
            verbosity=2,
            proxy='http://fulltest.proxy:3128',
            timeout=60
        )
        result = framework.get_browser()
        
        # Verify all configurations
        assert result == mock_browser
        assert mock_browser.addheaders == [('User-agent', 'Full-Test-Agent/2.0')]
        mock_browser.set_debug_http.assert_called_once_with(True)
        mock_browser.set_debug_redirects.assert_called_once_with(True)
        mock_browser.set_debug_responses.assert_called_once_with(True)
        mock_browser.set_proxies.assert_called_once_with({
            'http': 'http://fulltest.proxy:3128',
            'https': 'http://fulltest.proxy:3128'
        })
        mock_browser.set_handle_robots.assert_called_once_with(False)
        mock_settimeout.assert_called_once_with(60)


class TestBrowserMixinIntegration:
    """Integration tests for BrowserMixin with real mechanize (if available)."""
    
    @pytest.mark.skipif(True, reason="Requires real mechanize library")
    def test_browser_can_open_url(self):
        """Test that the browser can actually open a URL."""
        pass  # Placeholder for actual integration test


class TestBrowserMixinEdgeCases:
    """Edge case tests for BrowserMixin."""
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_with_empty_user_agent(self, mock_browser_class):
        """Test browser with empty user agent string."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(user_agent='')
        framework.get_browser()
        
        assert mock_browser.addheaders == [('User-agent', '')]
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_with_zero_timeout(self, mock_browser_class):
        """Test browser with zero timeout."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        with patch('recon.mixins.browser.socket.setdefaulttimeout') as mock_settimeout:
            framework = MockFrameworkWithBrowser(timeout=0)
            framework.get_browser()
            
            mock_settimeout.assert_called_once_with(0)
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_with_verbosity_exactly_2(self, mock_browser_class):
        """Test that verbosity of exactly 2 triggers debug mode."""
        mock_browser = MagicMock()
        mock_browser_class.return_value = mock_browser
        
        framework = MockFrameworkWithBrowser(verbosity=2)
        framework.get_browser()
        
        # Debug should be enabled at exactly verbosity 2
        mock_browser.set_debug_http.assert_called_once_with(True)
    
    @patch('recon.mixins.browser.mechanize.Browser')
    def test_get_browser_multiple_calls(self, mock_browser_class):
        """Test that multiple calls create new browser instances."""
        mock_browser1 = MagicMock()
        mock_browser2 = MagicMock()
        mock_browser_class.side_effect = [mock_browser1, mock_browser2]
        
        framework = MockFrameworkWithBrowser()
        result1 = framework.get_browser()
        result2 = framework.get_browser()
        
        assert result1 == mock_browser1
        assert result2 == mock_browser2
        assert mock_browser_class.call_count == 2
