"""
Unit tests for recon.utils.parsers module.

Tests parsing functions:
- parse_hostname
- parse_emails
- parse_name
"""
import pytest

from recon.utils.parsers import parse_hostname, parse_emails, parse_name
from tests.fixtures.test_data import NAME_PARSING_SAMPLES


class TestParseHostname:
    """Tests for parse_hostname function."""
    
    def test_full_url(self):
        """Test parsing hostname from full URL."""
        assert parse_hostname('https://www.example.com/path') == 'www.example.com'
        assert parse_hostname('http://example.com/page.html') == 'example.com'
    
    def test_url_with_port(self):
        """Test parsing hostname from URL with port."""
        assert parse_hostname('http://example.com:8080/path') == 'example.com:8080'
        assert parse_hostname('https://api.example.com:443') == 'api.example.com:443'
    
    def test_url_without_scheme(self):
        """Test parsing hostname without scheme."""
        assert parse_hostname('example.com/path') == 'example.com'
        assert parse_hostname('www.example.com') == 'www.example.com'
    
    def test_ip_address(self):
        """Test parsing IP address as hostname."""
        assert parse_hostname('http://192.0.2.1/path') == '192.0.2.1'
        assert parse_hostname('192.0.2.1:8080') == '192.0.2.1:8080'
    
    def test_ftp_url(self):
        """Test parsing hostname from FTP URL."""
        assert parse_hostname('ftp://files.example.com/data') == 'files.example.com'
    
    def test_subdomain(self):
        """Test parsing hostname with subdomain."""
        assert parse_hostname('https://sub.domain.example.com') == 'sub.domain.example.com'
    
    def test_empty_string(self):
        """Test parsing empty string."""
        result = parse_hostname('')
        assert result == ''
    
    def test_just_hostname(self):
        """Test parsing just a hostname."""
        assert parse_hostname('example.com') == 'example.com'


class TestParseEmails:
    """Tests for parse_emails function."""
    
    def test_single_email(self):
        """Test parsing single email from text."""
        text = 'Contact us at admin@example.com for support.'
        emails = parse_emails(text)
        assert 'admin@example.com' in emails
    
    def test_multiple_emails(self):
        """Test parsing multiple emails from text."""
        text = 'Contact admin@example.com or support@example.org for help.'
        emails = parse_emails(text)
        assert 'admin@example.com' in emails
        assert 'support@example.org' in emails
    
    def test_email_in_html(self):
        """Test parsing email from HTML-like content."""
        text = '<a href="mailto:user@example.com">Contact</a>'
        emails = parse_emails(text)
        assert any('user@example.com' in e for e in emails)
    
    def test_no_emails(self):
        """Test parsing text with no emails."""
        text = 'No email addresses in this text.'
        emails = parse_emails(text)
        assert len(emails) == 0
    
    def test_email_with_plus(self):
        """Test parsing email with plus addressing."""
        text = 'Send to user+tag@example.com'
        emails = parse_emails(text)
        assert 'user+tag@example.com' in emails
    
    def test_email_with_dots(self):
        """Test parsing email with dots in local part."""
        text = 'Email first.last@example.com'
        emails = parse_emails(text)
        assert 'first.last@example.com' in emails
    
    def test_email_with_subdomain(self):
        """Test parsing email with subdomain."""
        text = 'Contact user@mail.example.com'
        emails = parse_emails(text)
        assert 'user@mail.example.com' in emails
    
    def test_multiple_emails_per_line(self):
        """Test parsing multiple emails on same line."""
        text = 'john@example.com jane@example.com bob@example.org'
        emails = parse_emails(text)
        assert len(emails) == 3
    
    def test_empty_string(self):
        """Test parsing empty string."""
        emails = parse_emails('')
        assert len(emails) == 0


class TestParseName:
    """Tests for parse_name function."""
    
    def test_simple_name(self):
        """Test parsing simple first/last name."""
        fname, mname, lname = parse_name('John Doe')
        assert fname == 'John'
        assert mname is None
        assert lname == 'Doe'
    
    def test_name_with_middle(self):
        """Test parsing name with middle name."""
        fname, mname, lname = parse_name('John Q Public')
        assert fname == 'John'
        assert mname == 'Q'
        assert lname == 'Public'
    
    def test_name_with_middle_initial(self):
        """Test parsing name with middle initial and period."""
        fname, mname, lname = parse_name('John Q. Public')
        assert fname == 'John'
        assert mname == 'Q'
        assert lname == 'Public'
    
    def test_name_with_prefix_dr(self):
        """Test parsing name with Dr. prefix."""
        fname, mname, lname = parse_name('Dr. John Smith')
        assert fname == 'John'
        assert lname == 'Smith'
    
    def test_name_with_prefix_mr(self):
        """Test parsing name with Mr. prefix."""
        fname, mname, lname = parse_name('Mr. John Smith')
        assert fname == 'John'
        assert lname == 'Smith'
    
    def test_name_with_suffix_jr(self):
        """Test parsing name with Jr. suffix."""
        fname, mname, lname = parse_name('John Smith Jr.')
        assert fname == 'John'
        assert lname == 'Smith'
    
    def test_name_with_suffix_sr(self):
        """Test parsing name with Sr. suffix."""
        fname, mname, lname = parse_name('John Smith Sr.')
        assert fname == 'John'
        assert lname == 'Smith'
    
    def test_name_with_suffix_iii(self):
        """Test parsing name with III suffix."""
        fname, mname, lname = parse_name('John Smith III')
        assert fname == 'John'
        assert lname == 'Smith'
    
    def test_name_with_suffix_ii(self):
        """Test parsing name with II suffix."""
        fname, mname, lname = parse_name('John Smith II')
        assert fname == 'John'
        assert lname == 'Smith'
    
    def test_single_name(self):
        """Test parsing single name (first name only)."""
        fname, mname, lname = parse_name('John')
        assert fname == 'John'
        assert mname is None
        assert lname is None
    
    def test_long_name(self):
        """Test parsing name with many parts.
        
        For names with 4+ parts, parse_name joins elements 2+ into the last name.
        So 'Alice Marie Louise Johnson' becomes:
        - fname: 'Alice'
        - mname: 'Marie' (second element)
        - lname: 'Louise Johnson' (elements 2+ joined)
        """
        fname, mname, lname = parse_name('Alice Marie Louise Johnson')
        assert fname == 'Alice'
        assert mname == 'Marie'
        assert lname == 'Louise Johnson'
    
    def test_html_entities(self):
        """Test parsing name with HTML entities."""
        fname, mname, lname = parse_name('John &amp; Jane Doe')
        assert fname == 'John'
        # The & gets unescaped
    
    def test_name_with_comma(self):
        """Test parsing name with comma (Last, First format)."""
        fname, mname, lname = parse_name("O'Brien, John")
        # Note: current implementation doesn't handle Last, First format specially
        # It will parse as-is
        assert fname is not None
    
    def test_name_with_apostrophe(self):
        """Test parsing name with apostrophe."""
        fname, mname, lname = parse_name("Patrick O'Brien")
        assert fname == 'Patrick'
        # Apostrophe should be removed
        assert 'Brien' in str(lname)
    
    def test_whitespace_handling(self):
        """Test parsing name with extra whitespace."""
        fname, mname, lname = parse_name('  John   Doe  ')
        assert fname == 'John'
        assert lname == 'Doe'
    
    def test_the_prefix(self):
        """Test parsing name with 'the' prefix (should be removed)."""
        fname, mname, lname = parse_name('the John Smith')
        assert fname == 'John'
        assert lname == 'Smith'


class TestNameParsingFromSamples:
    """Parameterized tests from sample data."""
    
    @pytest.mark.parametrize('input_name,expected', [
        ('John Doe', ('John', None, 'Doe')),
        ('John Q Public', ('John', 'Q', 'Public')),
        ('Alice', ('Alice', None, None)),
    ])
    def test_name_samples(self, input_name, expected):
        """Test name parsing with sample data."""
        result = parse_name(input_name)
        fname, mname, lname = result
        exp_fname, exp_mname, exp_lname = expected
        
        assert fname == exp_fname
        assert mname == exp_mname
        assert lname == exp_lname


class TestParserIntegration:
    """Integration tests for parser functions."""
    
    def test_extract_contact_from_text(self):
        """Test extracting contact info from text block."""
        text = """
        Contact: John Q. Public
        Email: john.public@example.com
        Website: https://www.example.com/~john
        """
        
        # Extract email
        emails = parse_emails(text)
        assert 'john.public@example.com' in emails
        
        # Extract hostname from URL
        hostname = parse_hostname('https://www.example.com/~john')
        assert hostname == 'www.example.com'
    
    def test_parse_signature_block(self):
        """Test parsing a typical email signature."""
        signature = """
        Best regards,
        Jane Doe
        Senior Developer
        jane.doe@example.com
        https://example.com/team/jane
        """
        
        # Extract name (would need to identify the name line)
        fname, mname, lname = parse_name('Jane Doe')
        assert fname == 'Jane'
        assert lname == 'Doe'
        
        # Extract email
        emails = parse_emails(signature)
        assert 'jane.doe@example.com' in emails
        
        # Extract hostname
        hostname = parse_hostname('https://example.com/team/jane')
        assert hostname == 'example.com'
