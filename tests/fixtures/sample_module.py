"""
Sample test module for recon-ng framework testing.

This module demonstrates and exercises all framework functionality:
- Database inserts for all entity types
- HTTP request methods
- Mixin usage (resolver, threads, etc.)
- Module lifecycle hooks (pre/run/post)
- Options management
- Input validation

---
name: Comprehensive Test Module
author: Test Suite
version: 1.0
description: A comprehensive test module that exercises all framework functionality
query: SELECT domain FROM domains WHERE domain IS NOT NULL
options:
  - ['test_option', 'default_value', False, 'A test option']
  - ['count', 5, True, 'Number of iterations']
---
"""
from recon.core.module import BaseModule
from datetime import datetime


class Module(BaseModule):
    """Comprehensive test module exercising all framework features."""
    
    meta = {
        'name': 'Comprehensive Test Module',
        'author': 'Test Suite',
        'version': '1.0',
        'description': 'A comprehensive test module that exercises all framework functionality',
        'query': 'SELECT domain FROM domains WHERE domain IS NOT NULL',
        'options': [
            ('test_option', 'default_value', False, 'A test option'),
            ('count', 5, True, 'Number of iterations'),
        ],
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pre_called = False
        self.run_called = False
        self.post_called = False
        self.processed_items = []
    
    def module_pre(self):
        """Pre-run hook - called before module_run.
        
        Used for setup, validation, or returning data to module_run.
        """
        self.pre_called = True
        self.output('Module pre-run hook executed')
        
        # Return configuration data to be passed to module_run
        config = {
            'test_option': self.options.get('TEST_OPTION', 'default_value'),
            'count': self.options.get('COUNT', 5),
            'start_time': datetime.now(),
        }
        return config
    
    def module_run(self, domains, config=None):
        """Main module execution.
        
        Args:
            domains: List of domains from the source query
            config: Configuration dict from module_pre (optional)
        """
        self.run_called = True
        config = config or {}
        
        self.output(f'Processing {len(domains)} domains')
        self.output(f'Test option: {config.get("test_option", "N/A")}')
        
        for domain in domains:
            self._process_domain(domain)
    
    def _process_domain(self, domain):
        """Process a single domain, demonstrating various framework features."""
        self.processed_items.append(domain)
        self.verbose(f'Processing domain: {domain}')
        
        # Demonstrate database inserts for various entity types
        self._insert_sample_data(domain)
    
    def _insert_sample_data(self, domain):
        """Insert sample data demonstrating all entity types."""
        
        # Insert host
        self.insert_hosts(
            host=f'www.{domain}',
            ip_address='192.0.2.1',
            region='Test Region',
            country='US',
            notes=f'Discovered from {domain}',
            mute=True
        )
        
        # Insert contact
        self.insert_contacts(
            first_name='Test',
            last_name='User',
            email=f'test@{domain}',
            title='Test Contact',
            notes='Auto-generated test contact',
            mute=True
        )
        
        # Insert credentials
        self.insert_credentials(
            username=f'admin@{domain}',
            password='testpassword',
            notes='Test credentials',
            mute=True
        )
        
        # Insert company
        self.insert_companies(
            company=f'{domain.split(".")[0].title()} Corp',
            description=f'Company associated with {domain}',
            notes='Test company',
            mute=True
        )
        
        # Insert netblock
        self.insert_netblocks(
            netblock='192.0.2.0/24',
            notes=f'Netblock for {domain}',
            mute=True
        )
        
        # Insert location
        self.insert_locations(
            latitude='37.7749',
            longitude='-122.4194',
            street_address=f'123 {domain} Street',
            notes='Test location',
            mute=True
        )
        
        # Insert port
        self.insert_ports(
            ip_address='192.0.2.1',
            host=f'www.{domain}',
            port='443',
            protocol='tcp',
            banner='Test Server',
            notes='Test port',
            mute=True
        )
        
        # Insert profile
        self.insert_profiles(
            username=f'{domain.split(".")[0]}_user',
            resource='GitHub',
            url=f'https://github.com/{domain.split(".")[0]}',
            category='coding',
            notes='Test profile',
            mute=True
        )
        
        # Insert repository
        self.insert_repositories(
            name=f'{domain.split(".")[0]}-repo',
            owner=f'{domain.split(".")[0]}_user',
            description=f'Repository for {domain}',
            resource='GitHub',
            category='public',
            url=f'https://github.com/{domain.split(".")[0]}/{domain.split(".")[0]}-repo',
            notes='Test repository',
            mute=True
        )
    
    def module_post(self):
        """Post-run hook - called after module_run completes."""
        self.post_called = True
        self.output('Module post-run hook executed')
        self.output(f'Processed {len(self.processed_items)} items')
        
        # Log summary
        self.alert(f'Module completed successfully')


class TestableModule(Module):
    """Extended test module with additional testing methods."""
    
    def test_output_methods(self):
        """Test all output methods."""
        self.output('Standard output')
        self.alert('Alert output')
        self.verbose('Verbose output')
        self.debug('Debug output')
        self.error('Error output')
    
    def test_utility_methods(self):
        """Test utility methods."""
        # HTML escaping
        escaped = self.html_escape('<script>alert("xss")</script>')
        unescaped = self.html_unescape('&lt;script&gt;')
        
        # ASCII sanitization
        sanitized = self.ascii_sanitize('Hello\x00World')
        
        # CIDR to list
        ips = self.cidr_to_list('192.0.2.0/30')
        
        # Hosts to domains
        domains = self.hosts_to_domains(['www.example.com', 'mail.example.com'])
        
        return {
            'escaped': escaped,
            'unescaped': unescaped,
            'sanitized': sanitized,
            'ips': ips,
            'domains': domains,
        }
    
    def test_cookie_creation(self):
        """Test cookie creation."""
        cookie = self.make_cookie(
            name='session',
            value='abc123',
            domain='example.com',
            path='/'
        )
        return cookie
    
    def test_database_queries(self):
        """Test database query methods."""
        # Get all tables
        tables = self.get_tables()
        
        # Get columns for a table
        columns = self.get_columns('domains')
        
        # Run a custom query
        results = self.query('SELECT COUNT(*) FROM domains')
        
        return {
            'tables': tables,
            'columns': columns,
            'domain_count': results[0][0] if results else 0,
        }
