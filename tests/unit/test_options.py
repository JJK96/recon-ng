"""
Unit tests for recon.core.framework.Options class.

Tests the Options dictionary class with:
- Key transformation (uppercase)
- Value auto-conversion
- Required/description metadata
- Serialization
"""
import pytest

from recon.core.framework import Options


class TestOptionsBasics:
    """Basic Options class tests."""
    
    def test_create_empty_options(self):
        """Test creating empty Options object."""
        opts = Options()
        assert len(opts) == 0
    
    def test_set_and_get(self):
        """Test setting and getting values."""
        opts = Options()
        opts['test'] = 'value'
        assert opts['TEST'] == 'value'
    
    def test_key_transformation_uppercase(self):
        """Test keys are transformed to uppercase."""
        opts = Options()
        opts['lowercase'] = 'value1'
        opts['UPPERCASE'] = 'value2'
        opts['MixedCase'] = 'value3'
        
        assert 'LOWERCASE' in opts
        assert 'UPPERCASE' in opts
        assert 'MIXEDCASE' in opts
        
        # Access works regardless of case
        assert opts['lowercase'] == 'value1'
        assert opts['LOWERCASE'] == 'value1'
        assert opts['LowerCase'] == 'value1'
    
    def test_delete_key(self):
        """Test deleting keys."""
        opts = Options()
        opts.init_option('test', 'value', True, 'desc')
        
        del opts['test']
        
        assert 'TEST' not in opts
        assert 'TEST' not in opts.required
        assert 'TEST' not in opts.description


class TestOptionsAutoConversion:
    """Tests for Options value auto-conversion."""
    
    def test_none_value(self):
        """Test None value handling."""
        opts = Options()
        opts['test'] = None
        assert opts['TEST'] is None
    
    def test_boolean_true(self):
        """Test boolean True conversion."""
        opts = Options()
        opts['test'] = True
        assert opts['TEST'] is True
        
        opts['test2'] = 'true'
        assert opts['TEST2'] is True
        
        opts['test3'] = 'True'
        assert opts['TEST3'] is True
        
        opts['test4'] = 'TRUE'
        assert opts['TEST4'] is True
    
    def test_boolean_false(self):
        """Test boolean False conversion."""
        opts = Options()
        opts['test'] = False
        assert opts['TEST'] is False
        
        opts['test2'] = 'false'
        assert opts['TEST2'] is False
        
        opts['test3'] = 'False'
        assert opts['TEST3'] is False
    
    def test_integer_conversion(self):
        """Test integer conversion."""
        opts = Options()
        opts['test'] = '42'
        assert opts['TEST'] == 42
        assert isinstance(opts['TEST'], int)
        
        opts['test2'] = '-10'
        assert opts['TEST2'] == -10
    
    def test_float_conversion(self):
        """Test float conversion."""
        opts = Options()
        opts['test'] = '3.14'
        assert opts['TEST'] == 3.14
        assert isinstance(opts['TEST'], float)
        
        opts['test2'] = '-2.5'
        assert opts['TEST2'] == -2.5
    
    def test_string_none_variants(self):
        """Test string representations of None."""
        opts = Options()
        
        opts['test1'] = 'none'
        assert opts['TEST1'] is None
        
        opts['test2'] = 'None'
        assert opts['TEST2'] is None
        
        opts['test3'] = "''"
        assert opts['TEST3'] is None
        
        opts['test4'] = '""'
        assert opts['TEST4'] is None
    
    def test_string_preserved(self):
        """Test strings that should not be converted."""
        opts = Options()
        opts['test'] = 'hello world'
        assert opts['TEST'] == 'hello world'
        
        opts['test2'] = 'notanumber'
        assert opts['TEST2'] == 'notanumber'
    
    def test_numeric_string_with_leading_zeros(self):
        """Test numeric strings with leading zeros."""
        opts = Options()
        # These could be interpreted as octal, but should be decimal
        opts['test'] = '007'
        assert opts['TEST'] == 7


class TestOptionsInitOption:
    """Tests for init_option method."""
    
    def test_init_option_basic(self):
        """Test basic option initialization."""
        opts = Options()
        opts.init_option('name', 'value', True, 'A test option')
        
        assert opts['NAME'] == 'value'
        assert opts.required['NAME'] is True
        assert opts.description['NAME'] == 'A test option'
    
    def test_init_option_defaults(self):
        """Test init_option with default values."""
        opts = Options()
        opts.init_option('name')
        
        assert opts['NAME'] is None
        assert opts.required['NAME'] is False
        assert opts.description['NAME'] == ''
    
    def test_init_option_not_required(self):
        """Test init_option with required=False."""
        opts = Options()
        opts.init_option('name', 'value', False, 'Optional option')
        
        assert opts.required['NAME'] is False
    
    def test_init_option_with_conversion(self):
        """Test init_option performs value conversion."""
        opts = Options()
        opts.init_option('port', '8080', True, 'Port number')
        
        assert opts['PORT'] == 8080
        assert isinstance(opts['PORT'], int)
    
    def test_multiple_options(self):
        """Test initializing multiple options."""
        opts = Options()
        opts.init_option('host', 'localhost', True, 'Host name')
        opts.init_option('port', 8080, True, 'Port number')
        opts.init_option('debug', False, False, 'Debug mode')
        
        assert len(opts) == 3
        assert opts['HOST'] == 'localhost'
        assert opts['PORT'] == 8080
        assert opts['DEBUG'] is False


class TestOptionsSerialization:
    """Tests for Options serialization."""
    
    def test_serialize_empty(self):
        """Test serializing empty Options."""
        opts = Options()
        result = opts.serialize()
        assert result == []
    
    def test_serialize_single_option(self):
        """Test serializing single option."""
        opts = Options()
        opts.init_option('test', 'value', True, 'Test option')
        
        result = opts.serialize()
        
        assert len(result) == 1
        assert result[0]['name'] == 'TEST'
        assert result[0]['value'] == 'value'
        assert result[0]['required'] is True
        assert result[0]['description'] == 'Test option'
    
    def test_serialize_multiple_options(self):
        """Test serializing multiple options."""
        opts = Options()
        opts.init_option('host', 'localhost', True, 'Host name')
        opts.init_option('port', 8080, True, 'Port number')
        opts.init_option('debug', False, False, 'Debug mode')
        
        result = opts.serialize()
        
        assert len(result) == 3
        
        # Convert to dict for easier assertion
        result_dict = {opt['name']: opt for opt in result}
        
        assert result_dict['HOST']['value'] == 'localhost'
        assert result_dict['PORT']['value'] == 8080
        assert result_dict['DEBUG']['value'] is False
    
    def test_serialize_preserves_types(self):
        """Test serialization preserves value types."""
        opts = Options()
        opts.init_option('string', 'text', False, '')
        opts.init_option('integer', 42, False, '')
        opts.init_option('float', 3.14, False, '')
        opts.init_option('boolean', True, False, '')
        opts.init_option('none', None, False, '')
        
        result = opts.serialize()
        result_dict = {opt['name']: opt['value'] for opt in result}
        
        assert isinstance(result_dict['STRING'], str)
        assert isinstance(result_dict['INTEGER'], int)
        assert isinstance(result_dict['FLOAT'], float)
        assert isinstance(result_dict['BOOLEAN'], bool)
        assert result_dict['NONE'] is None


class TestOptionsBoolify:
    """Tests for _boolify method."""
    
    def test_boolify_true_lowercase(self):
        """Test boolify with 'true'."""
        opts = Options()
        assert opts._boolify('true') is True
    
    def test_boolify_false_lowercase(self):
        """Test boolify with 'false'."""
        opts = Options()
        assert opts._boolify('false') is False
    
    def test_boolify_case_insensitive(self):
        """Test boolify is case insensitive."""
        opts = Options()
        assert opts._boolify('TRUE') is True
        assert opts._boolify('FALSE') is False
        assert opts._boolify('True') is True
        assert opts._boolify('False') is False
    
    def test_boolify_invalid_raises(self):
        """Test boolify raises on invalid input."""
        opts = Options()
        with pytest.raises(KeyError):
            opts._boolify('yes')
        with pytest.raises(KeyError):
            opts._boolify('no')
        with pytest.raises(KeyError):
            opts._boolify('1')


class TestOptionsEdgeCases:
    """Edge case tests for Options."""
    
    def test_overwrite_option(self):
        """Test overwriting an existing option."""
        opts = Options()
        opts.init_option('test', 'value1', True, 'desc1')
        opts['test'] = 'value2'
        
        assert opts['TEST'] == 'value2'
        # Metadata should remain
        assert opts.required['TEST'] is True
        assert opts.description['TEST'] == 'desc1'
    
    def test_reinit_option(self):
        """Test re-initializing an option."""
        opts = Options()
        opts.init_option('test', 'value1', True, 'desc1')
        opts.init_option('test', 'value2', False, 'desc2')
        
        assert opts['TEST'] == 'value2'
        assert opts.required['TEST'] is False
        assert opts.description['TEST'] == 'desc2'
    
    def test_special_characters_in_value(self):
        """Test values with special characters."""
        opts = Options()
        opts['test'] = 'hello\nworld'
        assert opts['TEST'] == 'hello\nworld'
        
        opts['test2'] = 'path/to/file'
        assert opts['TEST2'] == 'path/to/file'
    
    def test_unicode_values(self):
        """Test unicode values."""
        opts = Options()
        opts['test'] = 'hello 世界'
        assert opts['TEST'] == 'hello 世界'
    
    def test_empty_string_value(self):
        """Test empty string values."""
        opts = Options()
        opts['test'] = ''
        # Empty string should NOT be converted to None
        assert opts['TEST'] == ''
    
    def test_dict_inheritance(self):
        """Test Options inherits from dict properly."""
        opts = Options()
        opts.init_option('a', 1, False, '')
        opts.init_option('b', 2, False, '')
        
        # Test dict methods
        assert len(opts) == 2
        assert set(opts.keys()) == {'A', 'B'}
        assert 1 in opts.values()
        assert 2 in opts.values()
        
        # Test iteration
        for key in opts:
            assert key in ['A', 'B']
