"""
Integration tests for database operations.

Tests all 14 entity types with insert and query operations:
- domains
- companies
- tenants
- netblocks
- locations
- vulnerabilities
- ports
- hosts
- contacts
- credentials
- leaks
- pushpins
- profiles
- repositories
"""
import pytest
from datetime import datetime

from tests.fixtures.test_data import (
    SAMPLE_DOMAINS, SAMPLE_HOSTS, SAMPLE_CONTACTS,
    SAMPLE_CREDENTIALS, SAMPLE_COMPANIES, SAMPLE_NETBLOCKS,
    SAMPLE_LOCATIONS, SAMPLE_VULNERABILITIES, SAMPLE_PORTS,
    SAMPLE_LEAKS, SAMPLE_PUSHPINS, SAMPLE_PROFILES,
    SAMPLE_REPOSITORIES, SAMPLE_TENANTS
)


@pytest.mark.integration
class TestDomainsEntity:
    """Tests for domains entity."""
    
    def test_insert_domain(self, mock_framework):
        """Test inserting a domain."""
        result = mock_framework.insert_domains(
            domain='example.com',
            notes='Test domain',
            mute=True
        )
        assert result == 1
    
    def test_insert_duplicate_domain(self, mock_framework):
        """Test duplicate domain is not inserted."""
        mock_framework.insert_domains(domain='example.com', mute=True)
        result = mock_framework.insert_domains(domain='example.com', mute=True)
        assert result == 0
    
    def test_query_domains(self, mock_framework):
        """Test querying domains."""
        mock_framework.insert_domains(domain='query-test.com', mute=True)
        result = mock_framework.query(
            "SELECT domain FROM domains WHERE domain = 'query-test.com'"
        )
        assert len(result) == 1
        assert result[0][0] == 'query-test.com'
    
    def test_insert_multiple_domains(self, mock_framework):
        """Test inserting multiple domains from sample data."""
        for domain_data in SAMPLE_DOMAINS:
            mock_framework.insert_domains(**domain_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM domains')
        assert result[0][0] >= len(SAMPLE_DOMAINS)


@pytest.mark.integration
class TestHostsEntity:
    """Tests for hosts entity."""
    
    def test_insert_host(self, mock_framework):
        """Test inserting a host."""
        result = mock_framework.insert_hosts(
            host='www.example.com',
            ip_address='192.0.2.1',
            region='California',
            country='US',
            mute=True
        )
        assert result == 1
    
    def test_insert_host_with_cname(self, mock_framework):
        """Test inserting a host with CNAME."""
        result = mock_framework.insert_hosts(
            host='cdn.example.com',
            cname='cdn.provider.net',
            ip_address='192.0.2.2',
            mute=True
        )
        assert result == 1
        
        # Verify CNAME was stored
        query_result = mock_framework.query(
            "SELECT cname FROM hosts WHERE host = 'cdn.example.com'"
        )
        assert query_result[0][0] == 'cdn.provider.net'
    
    def test_insert_host_with_geolocation(self, mock_framework):
        """Test inserting a host with geolocation data."""
        result = mock_framework.insert_hosts(
            host='geo.example.com',
            ip_address='192.0.2.3',
            latitude='37.7749',
            longitude='-122.4194',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_hosts(self, mock_framework):
        """Test inserting multiple hosts from sample data."""
        for host_data in SAMPLE_HOSTS:
            mock_framework.insert_hosts(**host_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM hosts')
        assert result[0][0] >= len(SAMPLE_HOSTS)


@pytest.mark.integration
class TestContactsEntity:
    """Tests for contacts entity."""
    
    def test_insert_contact(self, mock_framework):
        """Test inserting a contact."""
        result = mock_framework.insert_contacts(
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            title='Engineer',
            mute=True
        )
        assert result == 1
    
    def test_insert_contact_with_middle_name(self, mock_framework):
        """Test inserting a contact with middle name."""
        result = mock_framework.insert_contacts(
            first_name='John',
            middle_name='Q',
            last_name='Public',
            email='john.q.public@example.com',
            mute=True
        )
        assert result == 1
    
    def test_insert_contact_with_phone(self, mock_framework):
        """Test inserting a contact with phone number."""
        result = mock_framework.insert_contacts(
            first_name='Jane',
            last_name='Smith',
            phone='+1-555-0100',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_contacts(self, mock_framework):
        """Test inserting multiple contacts from sample data."""
        for contact_data in SAMPLE_CONTACTS:
            mock_framework.insert_contacts(**contact_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM contacts')
        assert result[0][0] >= len(SAMPLE_CONTACTS)


@pytest.mark.integration
class TestCredentialsEntity:
    """Tests for credentials entity."""
    
    def test_insert_credential_with_password(self, mock_framework):
        """Test inserting a credential with password."""
        result = mock_framework.insert_credentials(
            username='admin@example.com',
            password='secret123',
            mute=True
        )
        assert result == 1
    
    def test_insert_credential_with_hash(self, mock_framework):
        """Test inserting a credential with hash."""
        result = mock_framework.insert_credentials(
            username='user@example.com',
            _hash='5f4dcc3b5aa765d61d8327deb882cf99',
            _type='MD5',
            mute=True
        )
        assert result == 1
    
    def test_credential_auto_hash_detection(self, mock_framework):
        """Test auto-detection of hash in password field."""
        # MD5 hash in password field should be detected
        mock_framework.insert_credentials(
            username='hash-detect@example.com',
            password='5f4dcc3b5aa765d61d8327deb882cf99',
            mute=True
        )
        
        result = mock_framework.query(
            "SELECT hash, type, password FROM credentials WHERE username = 'hash-detect@example.com'"
        )
        assert result[0][0] == '5f4dcc3b5aa765d61d8327deb882cf99'
        assert result[0][1] == 'MD5'
        assert result[0][2] is None  # Password should be None
    
    def test_email_username_creates_contact(self, mock_framework):
        """Test email username creates contact entry."""
        mock_framework.insert_credentials(
            username='contact-test@example.com',
            password='password',
            mute=True
        )
        
        # Check if contact was created
        result = mock_framework.query(
            "SELECT email FROM contacts WHERE email = 'contact-test@example.com'"
        )
        assert len(result) == 1
    
    def test_insert_multiple_credentials(self, mock_framework):
        """Test inserting multiple credentials from sample data."""
        for cred_data in SAMPLE_CREDENTIALS:
            mock_framework.insert_credentials(**cred_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM credentials')
        assert result[0][0] >= len(SAMPLE_CREDENTIALS)


@pytest.mark.integration
class TestCompaniesEntity:
    """Tests for companies entity."""
    
    def test_insert_company(self, mock_framework):
        """Test inserting a company."""
        result = mock_framework.insert_companies(
            company='Example Corp',
            description='A test company',
            notes='Primary target',
            mute=True
        )
        assert result == 1
    
    def test_insert_duplicate_company(self, mock_framework):
        """Test duplicate company not inserted."""
        mock_framework.insert_companies(company='Unique Corp', mute=True)
        result = mock_framework.insert_companies(company='Unique Corp', mute=True)
        assert result == 0
    
    def test_insert_multiple_companies(self, mock_framework):
        """Test inserting multiple companies from sample data."""
        for company_data in SAMPLE_COMPANIES:
            mock_framework.insert_companies(**company_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM companies')
        assert result[0][0] >= len(SAMPLE_COMPANIES)


@pytest.mark.integration
class TestTenantsEntity:
    """Tests for tenants entity (Azure/Cloud)."""
    
    def test_insert_tenant(self, mock_framework):
        """Test inserting a tenant."""
        result = mock_framework.insert_tenants(
            brand='Microsoft',
            name='Test Tenant',
            id='abc123-def456',
            region='North America',
            domain='testtenant.onmicrosoft.com',
            mute=True
        )
        assert result == 1
    
    def test_insert_tenant_with_all_fields(self, mock_framework):
        """Test inserting a tenant with all fields."""
        result = mock_framework.insert_tenants(
            brand='Microsoft',
            name='Full Tenant',
            id='full-tenant-id',
            region='Europe',
            subregion='Western Europe',
            domain='fulltenant.onmicrosoft.com',
            desktopSSOEnabled=True,
            CBAEnabled=False,
            usesCloudSync=True,
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_tenants(self, mock_framework):
        """Test inserting multiple tenants from sample data."""
        for tenant_data in SAMPLE_TENANTS:
            mock_framework.insert_tenants(**tenant_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM tenants')
        assert result[0][0] >= len(SAMPLE_TENANTS)


@pytest.mark.integration
class TestNetblocksEntity:
    """Tests for netblocks entity."""
    
    def test_insert_netblock(self, mock_framework):
        """Test inserting a netblock."""
        result = mock_framework.insert_netblocks(
            netblock='192.0.2.0/24',
            notes='Test netblock',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_netblocks(self, mock_framework):
        """Test inserting multiple netblocks from sample data."""
        for netblock_data in SAMPLE_NETBLOCKS:
            mock_framework.insert_netblocks(**netblock_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM netblocks')
        assert result[0][0] >= len(SAMPLE_NETBLOCKS)


@pytest.mark.integration
class TestLocationsEntity:
    """Tests for locations entity."""
    
    def test_insert_location(self, mock_framework):
        """Test inserting a location."""
        result = mock_framework.insert_locations(
            latitude='37.7749',
            longitude='-122.4194',
            street_address='123 Main St',
            notes='Headquarters',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_locations(self, mock_framework):
        """Test inserting multiple locations from sample data."""
        for location_data in SAMPLE_LOCATIONS:
            mock_framework.insert_locations(**location_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM locations')
        assert result[0][0] >= len(SAMPLE_LOCATIONS)


@pytest.mark.integration
class TestVulnerabilitiesEntity:
    """Tests for vulnerabilities entity."""
    
    def test_insert_vulnerability(self, mock_framework):
        """Test inserting a vulnerability."""
        result = mock_framework.insert_vulnerabilities(
            host='www.example.com',
            reference='CVE-2024-0001',
            category='XSS',
            status='Open',
            mute=True
        )
        assert result == 1
    
    def test_insert_vulnerability_with_date(self, mock_framework):
        """Test inserting a vulnerability with publish date."""
        result = mock_framework.insert_vulnerabilities(
            host='api.example.com',
            reference='CVE-2024-0002',
            publish_date=datetime(2024, 1, 15),
            category='SQLi',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_vulnerabilities(self, mock_framework):
        """Test inserting multiple vulnerabilities from sample data."""
        for vuln_data in SAMPLE_VULNERABILITIES:
            mock_framework.insert_vulnerabilities(**vuln_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM vulnerabilities')
        assert result[0][0] >= len(SAMPLE_VULNERABILITIES)


@pytest.mark.integration
class TestPortsEntity:
    """Tests for ports entity."""
    
    def test_insert_port(self, mock_framework):
        """Test inserting a port."""
        result = mock_framework.insert_ports(
            ip_address='192.0.2.1',
            host='www.example.com',
            port='443',
            protocol='tcp',
            banner='Apache/2.4',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_ports(self, mock_framework):
        """Test inserting multiple ports from sample data."""
        for port_data in SAMPLE_PORTS:
            mock_framework.insert_ports(**port_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM ports')
        assert result[0][0] >= len(SAMPLE_PORTS)


@pytest.mark.integration
class TestLeaksEntity:
    """Tests for leaks entity."""
    
    def test_insert_leak(self, mock_framework):
        """Test inserting a leak."""
        result = mock_framework.insert_leaks(
            leak_id='LEAK-001',
            title='Test Breach',
            description='A test data breach',
            leak_type='Database dump',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_leaks(self, mock_framework):
        """Test inserting multiple leaks from sample data."""
        for leak_data in SAMPLE_LEAKS:
            mock_framework.insert_leaks(**leak_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM leaks')
        assert result[0][0] >= len(SAMPLE_LEAKS)


@pytest.mark.integration
class TestPushpinsEntity:
    """Tests for pushpins entity (geolocation data)."""
    
    def test_insert_pushpin(self, mock_framework):
        """Test inserting a pushpin."""
        result = mock_framework.insert_pushpins(
            source='twitter',
            screen_name='test_user',
            profile_name='Test User',
            message='Test post',
            latitude='37.7749',
            longitude='-122.4194',
            time=datetime(2024, 1, 15, 10, 30, 0),
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_pushpins(self, mock_framework):
        """Test inserting multiple pushpins from sample data."""
        for pushpin_data in SAMPLE_PUSHPINS:
            mock_framework.insert_pushpins(**pushpin_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM pushpins')
        assert result[0][0] >= len(SAMPLE_PUSHPINS)


@pytest.mark.integration
class TestProfilesEntity:
    """Tests for profiles entity."""
    
    def test_insert_profile(self, mock_framework):
        """Test inserting a profile."""
        result = mock_framework.insert_profiles(
            username='john_doe',
            resource='LinkedIn',
            url='https://linkedin.com/in/john-doe',
            category='professional',
            mute=True
        )
        assert result == 1
    
    def test_insert_profile_with_contact_id(self, mock_framework):
        """Test inserting a profile linked to contact."""
        # First insert a contact
        mock_framework.insert_contacts(
            first_name='Jane',
            last_name='Smith',
            mute=True
        )
        
        result = mock_framework.insert_profiles(
            username='jane_smith',
            resource='GitHub',
            url='https://github.com/janesmith',
            contact_id=1,
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_profiles(self, mock_framework):
        """Test inserting multiple profiles from sample data."""
        for profile_data in SAMPLE_PROFILES:
            mock_framework.insert_profiles(**profile_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM profiles')
        assert result[0][0] >= len(SAMPLE_PROFILES)


@pytest.mark.integration
class TestRepositoriesEntity:
    """Tests for repositories entity."""
    
    def test_insert_repository(self, mock_framework):
        """Test inserting a repository."""
        result = mock_framework.insert_repositories(
            name='example-repo',
            owner='example-org',
            description='An example repository',
            resource='GitHub',
            category='public',
            url='https://github.com/example-org/example-repo',
            mute=True
        )
        assert result == 1
    
    def test_insert_multiple_repositories(self, mock_framework):
        """Test inserting multiple repositories from sample data."""
        for repo_data in SAMPLE_REPOSITORIES:
            mock_framework.insert_repositories(**repo_data, mute=True)
        
        result = mock_framework.query('SELECT COUNT(*) FROM repositories')
        assert result[0][0] >= len(SAMPLE_REPOSITORIES)


@pytest.mark.integration
class TestDatabaseIntegration:
    """Cross-entity integration tests."""
    
    def test_populated_database_fixture(self, populated_database):
        """Test the populated_database fixture works."""
        fw = populated_database
        
        # Check all entity types have data
        for table in ['domains', 'hosts', 'contacts', 'credentials',
                      'companies', 'netblocks', 'locations', 'vulnerabilities',
                      'ports', 'leaks', 'pushpins', 'profiles', 'repositories',
                      'tenants']:
            result = fw.query(f'SELECT COUNT(*) FROM {table}')
            assert result[0][0] > 0, f"Table {table} is empty"
    
    def test_cross_table_query(self, populated_database):
        """Test querying across tables."""
        fw = populated_database
        
        # Get hosts with their domains
        result = fw.query('''
            SELECT h.host, d.domain 
            FROM hosts h 
            JOIN domains d ON h.host LIKE '%' || d.domain
            LIMIT 5
        ''')
        # May or may not have matches depending on test data
        assert isinstance(result, list)
    
    def test_module_field_tracking(self, mock_framework):
        """Test that module field is populated."""
        mock_framework.insert_domains(domain='module-test.com', mute=True)
        
        result = mock_framework.query(
            "SELECT module FROM domains WHERE domain = 'module-test.com'"
        )
        # Module should be tracked (test module name)
        assert result[0][0] is not None
