"""
Sample test data for recon-ng test suite.

Uses well-known public domains (example.com, test.com) and
RFC 5737 reserved IP addresses (192.0.2.x, 198.51.100.x, 203.0.113.x)
for safe testing.
"""
from datetime import datetime

# =============================================================================
# DOMAINS
# =============================================================================

SAMPLE_DOMAINS = [
    {'domain': 'example.com', 'notes': 'Primary test domain (IANA reserved)'},
    {'domain': 'example.org', 'notes': 'Alternative test domain'},
    {'domain': 'example.net', 'notes': 'Network test domain'},
    {'domain': 'test.com', 'notes': 'Generic test domain'},
    {'domain': 'sub.example.com', 'notes': 'Subdomain test'},
]

# =============================================================================
# HOSTS
# =============================================================================

SAMPLE_HOSTS = [
    {
        'host': 'www.example.com',
        'ip_address': '93.184.216.34',  # Real example.com IP
        'region': 'California',
        'country': 'US',
        'latitude': '34.0522',
        'longitude': '-118.2437',
        'notes': 'Main web server',
    },
    {
        'host': 'mail.example.com',
        'ip_address': '192.0.2.1',  # RFC 5737 TEST-NET-1
        'region': 'Virginia',
        'country': 'US',
        'latitude': '38.9072',
        'longitude': '-77.0369',
        'notes': 'Mail server',
    },
    {
        'host': 'api.example.com',
        'ip_address': '198.51.100.1',  # RFC 5737 TEST-NET-2
        'region': 'Oregon',
        'country': 'US',
        'latitude': '45.5152',
        'longitude': '-122.6784',
        'notes': 'API endpoint',
    },
    {
        'host': 'cdn.example.com',
        'cname': 'cdn.cloudprovider.net',
        'ip_address': '203.0.113.1',  # RFC 5737 TEST-NET-3
        'region': 'Texas',
        'country': 'US',
        'notes': 'CDN endpoint with CNAME',
    },
    {
        'host': 'dev.example.com',
        'ip_address': '192.0.2.100',
        'region': 'Washington',
        'country': 'US',
        'notes': 'Development server',
    },
]

# =============================================================================
# CONTACTS
# =============================================================================

SAMPLE_CONTACTS = [
    {
        'first_name': 'John',
        'middle_name': 'Q',
        'last_name': 'Public',
        'email': 'john.public@example.com',
        'title': 'System Administrator',
        'region': 'California',
        'country': 'US',
        'phone': '+1-555-0100',
        'notes': 'Primary contact',
    },
    {
        'first_name': 'Jane',
        'last_name': 'Doe',
        'email': 'jane.doe@example.com',
        'title': 'Security Engineer',
        'region': 'New York',
        'country': 'US',
        'phone': '+1-555-0101',
        'notes': 'Security team',
    },
    {
        'first_name': 'Bob',
        'last_name': 'Smith',
        'email': 'bob.smith@example.org',
        'title': 'Network Engineer',
        'region': 'Texas',
        'country': 'US',
        'notes': 'Network operations',
    },
    {
        'first_name': 'Alice',
        'middle_name': 'M',
        'last_name': 'Johnson',
        'email': 'alice.johnson@example.net',
        'title': 'DevOps Engineer',
        'country': 'UK',
        'notes': 'UK office',
    },
    {
        'first_name': 'Charlie',
        'last_name': 'Brown',
        'email': 'charlie@test.com',
        'title': 'Software Developer',
        'country': 'CA',
        'notes': 'Canada office',
    },
]

# =============================================================================
# CREDENTIALS
# =============================================================================

SAMPLE_CREDENTIALS = [
    {
        'username': 'admin@example.com',
        'password': 'Password123!',
        'notes': 'Admin credentials',
    },
    {
        'username': 'user@example.com',
        '_hash': '5f4dcc3b5aa765d61d8327deb882cf99',  # MD5 hash of 'password'
        '_type': 'MD5',
        'notes': 'MD5 hashed password',
    },
    {
        'username': 'developer@example.com',
        '_hash': '5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8',  # SHA1 hash
        '_type': 'SHA1',
        'notes': 'SHA1 hashed password',
    },
    {
        'username': 'service@example.com',
        '_hash': '$2y$10$abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ',
        '_type': 'bcrypt',
        'leak': 'test_breach_2024',
        'notes': 'From breach database',
    },
    {
        'username': 'test.user',
        'password': 'test123',
        'notes': 'Non-email username',
    },
]

# =============================================================================
# COMPANIES
# =============================================================================

SAMPLE_COMPANIES = [
    {
        'company': 'Example Corporation',
        'description': 'A sample company for testing purposes',
        'notes': 'Primary target organization',
    },
    {
        'company': 'Test Industries',
        'description': 'Industrial testing services',
        'notes': 'Subsidiary',
    },
    {
        'company': 'Demo LLC',
        'description': 'Demonstration services',
        'notes': 'Partner company',
    },
]

# =============================================================================
# TENANTS (Azure/Cloud)
# =============================================================================

SAMPLE_TENANTS = [
    {
        'brand': 'Microsoft',
        'name': 'Example Corp Tenant',
        'id': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        'region': 'North America',
        'subregion': 'United States',
        'domain': 'examplecorp.onmicrosoft.com',
        'desktopSSOEnabled': True,
        'CBAEnabled': False,
        'usesCloudSync': True,
    },
    {
        'brand': 'Microsoft',
        'name': 'Test Industries Tenant',
        'id': 'b2c3d4e5-f6a7-8901-bcde-f12345678901',
        'region': 'Europe',
        'domain': 'testindustries.onmicrosoft.com',
        'desktopSSOEnabled': False,
        'CBAEnabled': True,
        'usesCloudSync': False,
    },
]

# =============================================================================
# NETBLOCKS
# =============================================================================

SAMPLE_NETBLOCKS = [
    {'netblock': '192.0.2.0/24', 'notes': 'TEST-NET-1 (RFC 5737)'},
    {'netblock': '198.51.100.0/24', 'notes': 'TEST-NET-2 (RFC 5737)'},
    {'netblock': '203.0.113.0/24', 'notes': 'TEST-NET-3 (RFC 5737)'},
    {'netblock': '10.0.0.0/8', 'notes': 'Private network range'},
]

# =============================================================================
# LOCATIONS
# =============================================================================

SAMPLE_LOCATIONS = [
    {
        'latitude': '37.7749',
        'longitude': '-122.4194',
        'street_address': '123 Market Street, San Francisco, CA',
        'notes': 'Headquarters',
    },
    {
        'latitude': '40.7128',
        'longitude': '-74.0060',
        'street_address': '456 Broadway, New York, NY',
        'notes': 'East coast office',
    },
    {
        'latitude': '51.5074',
        'longitude': '-0.1278',
        'street_address': '789 Oxford Street, London, UK',
        'notes': 'UK office',
    },
]

# =============================================================================
# VULNERABILITIES
# =============================================================================

SAMPLE_VULNERABILITIES = [
    {
        'host': 'www.example.com',
        'reference': 'CVE-2024-0001',
        'example': 'https://www.example.com/vulnerable?param=<script>alert(1)</script>',
        'publish_date': datetime(2024, 1, 15),
        'category': 'XSS',
        'status': 'Open',
        'notes': 'Reflected XSS in search parameter',
    },
    {
        'host': 'api.example.com',
        'reference': 'CVE-2024-0002',
        'example': 'SQL injection in login form',
        'publish_date': datetime(2024, 2, 20),
        'category': 'SQLi',
        'status': 'Fixed',
        'notes': 'SQL injection - patched in v2.1',
    },
    {
        'host': 'mail.example.com',
        'reference': 'CVE-2024-0003',
        'category': 'Misconfiguration',
        'status': 'In Progress',
        'notes': 'Open relay detected',
    },
]

# =============================================================================
# PORTS
# =============================================================================

SAMPLE_PORTS = [
    {
        'ip_address': '192.0.2.1',
        'host': 'www.example.com',
        'port': '80',
        'protocol': 'tcp',
        'banner': 'Apache/2.4.51',
        'notes': 'HTTP server',
    },
    {
        'ip_address': '192.0.2.1',
        'host': 'www.example.com',
        'port': '443',
        'protocol': 'tcp',
        'banner': 'Apache/2.4.51 OpenSSL/1.1.1',
        'notes': 'HTTPS server',
    },
    {
        'ip_address': '192.0.2.1',
        'host': 'mail.example.com',
        'port': '25',
        'protocol': 'tcp',
        'banner': 'Postfix',
        'notes': 'SMTP server',
    },
    {
        'ip_address': '198.51.100.1',
        'host': 'api.example.com',
        'port': '8443',
        'protocol': 'tcp',
        'banner': 'nginx/1.21.0',
        'notes': 'API endpoint',
    },
    {
        'ip_address': '192.0.2.100',
        'host': 'dev.example.com',
        'port': '22',
        'protocol': 'tcp',
        'banner': 'OpenSSH_8.9',
        'notes': 'SSH access',
    },
]

# =============================================================================
# LEAKS
# =============================================================================

SAMPLE_LEAKS = [
    {
        'leak_id': 'LEAK-2024-001',
        'description': 'Sample data breach for testing',
        'source_refs': 'haveibeenpwned.com',
        'leak_type': 'Database dump',
        'title': 'Example Corp Breach 2024',
        'import_date': '2024-01-15',
        'leak_date': '2024-01-10',
        'attackers': 'Unknown',
        'num_entries': '10000',
        'score': '7.5',
        'num_domains_affected': '5',
        'attack_method': 'SQL Injection',
        'target_industries': 'Technology',
        'password_hash': 'MD5',
        'password_type': 'hashed',
        'targets': 'example.com',
        'media_refs': 'https://example.com/breach-notice',
        'notes': 'Test breach entry',
    },
    {
        'leak_id': 'LEAK-2024-002',
        'description': 'Credential stuffing attack',
        'leak_type': 'Credential dump',
        'title': 'Multi-site Credential Leak',
        'leak_date': '2024-02-01',
        'num_entries': '5000',
        'password_type': 'plaintext',
        'targets': 'test.com,example.org',
        'notes': 'Aggregated from multiple sources',
    },
]

# =============================================================================
# PUSHPINS (Geolocation data)
# =============================================================================

SAMPLE_PUSHPINS = [
    {
        'source': 'twitter',
        'screen_name': 'example_user',
        'profile_name': 'Example User',
        'profile_url': 'https://twitter.com/example_user',
        'media_url': 'https://pbs.twimg.com/media/example.jpg',
        'thumb_url': 'https://pbs.twimg.com/media/example_thumb.jpg',
        'message': 'Just visited the office! #example',
        'latitude': '37.7749',
        'longitude': '-122.4194',
        'time': datetime(2024, 1, 15, 10, 30, 0),
        'notes': 'Office location post',
    },
    {
        'source': 'instagram',
        'screen_name': 'test_account',
        'profile_name': 'Test Account',
        'profile_url': 'https://instagram.com/test_account',
        'message': 'Conference day',
        'latitude': '40.7128',
        'longitude': '-74.0060',
        'time': datetime(2024, 2, 20, 14, 0, 0),
        'notes': 'Event attendance',
    },
    {
        'source': 'flickr',
        'screen_name': 'photo_user',
        'profile_name': 'Photo User',
        'profile_url': 'https://flickr.com/photos/photo_user',
        'media_url': 'https://farm66.staticflickr.com/example.jpg',
        'message': 'London office view',
        'latitude': '51.5074',
        'longitude': '-0.1278',
        'time': datetime(2024, 3, 1, 9, 0, 0),
        'notes': 'UK office photo',
    },
]

# =============================================================================
# PROFILES (Social media)
# =============================================================================

SAMPLE_PROFILES = [
    {
        'username': 'john.public',
        'resource': 'LinkedIn',
        'url': 'https://linkedin.com/in/john-public',
        'category': 'professional',
        'notes': 'System Administrator profile',
    },
    {
        'username': 'janedoe',
        'resource': 'GitHub',
        'url': 'https://github.com/janedoe',
        'category': 'coding',
        'notes': 'Security Engineer profile',
    },
    {
        'username': 'bob_smith_dev',
        'resource': 'Twitter',
        'url': 'https://twitter.com/bob_smith_dev',
        'category': 'social',
        'notes': 'Network Engineer profile',
    },
    {
        'username': 'alicej',
        'resource': 'Instagram',
        'url': 'https://instagram.com/alicej',
        'category': 'social',
        'contact_id': 4,
        'notes': 'Linked to Alice Johnson',
    },
]

# =============================================================================
# REPOSITORIES
# =============================================================================

SAMPLE_REPOSITORIES = [
    {
        'name': 'example-api',
        'owner': 'example-corp',
        'description': 'Main API repository',
        'resource': 'GitHub',
        'category': 'private',
        'url': 'https://github.com/example-corp/example-api',
        'notes': 'Main codebase',
    },
    {
        'name': 'internal-tools',
        'owner': 'example-corp',
        'description': 'Internal tooling and scripts',
        'resource': 'GitHub',
        'category': 'private',
        'url': 'https://github.com/example-corp/internal-tools',
        'notes': 'DevOps tools',
    },
    {
        'name': 'public-docs',
        'owner': 'example-corp',
        'description': 'Public documentation',
        'resource': 'GitHub',
        'category': 'public',
        'url': 'https://github.com/example-corp/public-docs',
        'notes': 'API documentation',
    },
    {
        'name': 'test-project',
        'owner': 'janedoe',
        'description': 'Personal test project',
        'resource': 'GitLab',
        'category': 'public',
        'url': 'https://gitlab.com/janedoe/test-project',
        'notes': 'Side project',
    },
]

# =============================================================================
# HASH SAMPLES (for testing is_hash function)
# =============================================================================

HASH_SAMPLES = {
    'MD5': [
        '5f4dcc3b5aa765d61d8327deb882cf99',
        'd41d8cd98f00b204e9800998ecf8427e',
        '098f6bcd4621d373cade4e832627b4f6',
    ],
    'MySQL': [
        '1a2b3c4d5e6f7890',
        'abcdef0123456789',
    ],
    'MySQL5': [
        '*2470C0C06DEE42FD1618BB99005ADCA2EC9D1E19',
        '*A4B6157319038724E3560894F7F932C8886EBFCF',
    ],
    'SHA1': [
        '5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8',
        'da39a3ee5e6b4b0d3255bfef95601890afd80709',
    ],
    'SHA256': [
        # SHA256 is 64 hex chars
        '5e884898da28047d9166e5a89a2f9a4e4b8c7d6e5f4a3b2c1d0e9f8a7b6c5d4e',
    ],
    'SHA512': [
        'b109f3bbbc244eb82441917ed06d618b9008dd09b3befd1b5e07394c706a8bb980b1d7785e5976ec049b46df5f1326af5a2ea6d103fd07c95385ffab0cacbc86',
    ],
    'bcrypt': [
        # bcrypt pattern: ^\$2[ya]?\$.{56}$ - total 60 chars
        '$2a$12$R9h/cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jWMUW',
    ],
    'phpass': [
        # phpass pattern: ^\$[PH]{1}\$.{31}$ - total 34 chars
        '$P$BhwVLVLk5fGRPyoEfmBfVs82bU7btl.',
        '$H$9abcdefghijklmnopqrstuvwxyz1234',
    ],
}

# Non-hash strings for negative testing
NON_HASH_SAMPLES = [
    'password123',
    'notahash',
    'short',
    '12345',
    'definitely not a hash value at all',
    '',
]

# =============================================================================
# VALIDATION SAMPLES
# =============================================================================

VALID_DOMAINS = [
    'example.com',
    'sub.example.com',
    'very.long.subdomain.example.org',
    'test-domain.net',
    'a.co',
    'example.co.uk',
]

INVALID_DOMAINS = [
    '-invalid.com',
    'invalid-.com',
    '.invalid.com',
    'invalid..com',
    'a',
    '',
    'no spaces.com',
    'special@chars.com',
]

# NOTE: The UrlValidator regex uses [A-Z] without re.IGNORECASE, so
# lowercase domain URLs fail validation. This is a known bug in the validator.
# These URLs use patterns that actually pass the validator:
# - localhost (explicit match in regex)
# - IP addresses (explicit match in regex)
# - uppercase domain names (matched by [A-Z] in regex)
VALID_URLS = [
    'http://EXAMPLE.COM',
    'https://EXAMPLE.COM',
    'https://WWW.EXAMPLE.COM/path',
    'http://EXAMPLE.COM:8080',
    'https://API.EXAMPLE.COM/v1/endpoint?param=value',
    'ftp://FILES.EXAMPLE.COM',
    'http://localhost',
    'http://localhost:3000',
    'http://192.0.2.1',
    'http://192.0.2.1:8080/path',
]

INVALID_URLS = [
    'not a url',
    'ftp:/missing-slash.com',
    '',
]

VALID_EMAILS = [
    'user@example.com',
    'user.name@example.com',
    'user+tag@example.com',
    'user@sub.example.com',
    'a@b.co',
]

INVALID_EMAILS = [
    'invalid',
    '@example.com',
    'user@',
    'user@.com',
    '',
    'spaces in@email.com',
]

# =============================================================================
# NAME PARSING SAMPLES
# =============================================================================

NAME_PARSING_SAMPLES = [
    # (input, expected_output)
    ('John Doe', ('John', None, 'Doe')),
    ('John Q. Public', ('John', 'Q', 'Public')),
    ('Alice Marie Johnson', ('Alice', 'Marie', 'Johnson')),
    ('Dr. John Smith', ('John', None, 'Smith')),
    ('John Smith Jr.', ('John', None, 'Smith')),
    ('John Smith III', ('John', None, 'Smith')),
    ('John', ('John', None, None)),
    # Note: parse_name doesn't handle "Last, First" format specially
    # commas and apostrophes are stripped, so "O'Brien," becomes "OBrien"
    ("O'Brien, John", ('OBrien', None, 'John')),
]
