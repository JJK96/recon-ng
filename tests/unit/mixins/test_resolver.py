"""
Unit tests for the ResolverMixin class.

Tests DNS resolver configuration and behavior.
"""
import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from recon.mixins.resolver import ResolverMixin
from recon.core.framework import Options


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def resolver_mixin():
    """Create a class that uses ResolverMixin for testing."""
    
    class TestResolver(ResolverMixin):
        def __init__(self):
            self._global_options = Options()
            self._global_options.init_option('nameserver', '8.8.8.8', True, 'default nameserver')
    
    return TestResolver()


@pytest.fixture
def resolver_with_custom_ns():
    """Create a resolver mixin with custom nameserver."""
    
    class TestResolver(ResolverMixin):
        def __init__(self, nameserver):
            self._global_options = Options()
            self._global_options.init_option('nameserver', nameserver, True, 'default nameserver')
    
    return TestResolver


# =============================================================================
# GET RESOLVER TESTS
# =============================================================================

@pytest.mark.unit
class TestGetResolver:
    """Tests for get_resolver method."""
    
    def test_get_resolver_returns_resolver_object(self, resolver_mixin):
        """Test get_resolver returns a dns.resolver.Resolver object."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result = resolver_mixin.get_resolver()
            
            # Should have called Resolver with configure=False
            mock_resolver_class.assert_called_once_with(configure=False)
    
    def test_get_resolver_sets_nameservers(self, resolver_mixin):
        """Test get_resolver sets nameservers from global options."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result = resolver_mixin.get_resolver()
            
            # Should set nameservers to the configured value
            assert mock_resolver.nameservers == ['8.8.8.8']
    
    def test_get_resolver_sets_lifetime(self, resolver_mixin):
        """Test get_resolver sets lifetime to 3 seconds."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result = resolver_mixin.get_resolver()
            
            # Should set lifetime to 3
            assert mock_resolver.lifetime == 3
    
    def test_get_resolver_with_custom_nameserver(self, resolver_with_custom_ns):
        """Test get_resolver uses custom nameserver from options."""
        instance = resolver_with_custom_ns('1.1.1.1')
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result = instance.get_resolver()
            
            # Should set nameservers to the custom value
            assert mock_resolver.nameservers == ['1.1.1.1']
    
    def test_get_resolver_with_multiple_calls(self, resolver_mixin):
        """Test get_resolver can be called multiple times."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result1 = resolver_mixin.get_resolver()
            result2 = resolver_mixin.get_resolver()
            
            # Should create new resolver each time
            assert mock_resolver_class.call_count == 2
    
    def test_get_resolver_different_nameservers(self, resolver_with_custom_ns):
        """Test get_resolver works with different nameserver formats."""
        test_cases = [
            '8.8.8.8',          # Google DNS
            '1.1.1.1',          # Cloudflare DNS
            '9.9.9.9',          # Quad9 DNS
            '208.67.222.222',   # OpenDNS
            '192.168.1.1',      # Local DNS
        ]
        
        for nameserver in test_cases:
            instance = resolver_with_custom_ns(nameserver)
            
            with patch('dns.resolver.Resolver') as mock_resolver_class:
                mock_resolver = MagicMock()
                mock_resolver_class.return_value = mock_resolver
                
                result = instance.get_resolver()
                
                assert mock_resolver.nameservers == [nameserver]


# =============================================================================
# INTEGRATION-STYLE TESTS (with real dns module)
# =============================================================================

@pytest.mark.unit
class TestResolverIntegration:
    """Integration-style tests that use real dns module (mocked network)."""
    
    def test_resolver_can_be_used_for_query(self, resolver_mixin):
        """Test that returned resolver can be used for DNS queries."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            # Setup mock response
            mock_answer = MagicMock()
            mock_resolver.resolve.return_value = mock_answer
            
            resolver = resolver_mixin.get_resolver()
            result = resolver.resolve('example.com', 'A')
            
            mock_resolver.resolve.assert_called_once_with('example.com', 'A')
    
    def test_resolver_handles_timeout(self, resolver_mixin):
        """Test resolver behavior with timeout (lifetime setting)."""
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            resolver = resolver_mixin.get_resolver()
            
            # Lifetime should be set to 3 seconds
            assert resolver.lifetime == 3


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

@pytest.mark.unit
class TestResolverEdgeCases:
    """Edge case tests for resolver mixin."""
    
    def test_resolver_with_ipv6_nameserver(self, resolver_with_custom_ns):
        """Test resolver with IPv6 nameserver address."""
        instance = resolver_with_custom_ns('2001:4860:4860::8888')
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result = instance.get_resolver()
            
            assert mock_resolver.nameservers == ['2001:4860:4860::8888']
    
    def test_resolver_with_empty_nameserver(self, resolver_with_custom_ns):
        """Test resolver behavior with empty nameserver."""
        instance = resolver_with_custom_ns('')
        
        with patch('dns.resolver.Resolver') as mock_resolver_class:
            mock_resolver = MagicMock()
            mock_resolver_class.return_value = mock_resolver
            
            result = instance.get_resolver()
            
            # Should still set the nameservers list (even if empty)
            assert mock_resolver.nameservers == ['']
