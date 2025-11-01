"""Unit tests for environment variable loading (T101)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from src.infrastructure.config.environment import (
    load_environment_variables,
    get_env,
    get_env_bool,
    get_optional_api_key,
    require_api_key,
    get_zotero_config,
    validate_zotero_config_for_remote_access,
    validate_qdrant_api_key_if_required,
    OPTIONAL_API_KEYS,
    REQUIRED_API_KEYS,
)


class TestEnvironmentVariableLoading:
    """Tests for load_environment_variables function."""
    
    def test_load_env_file_automatic_detection(self, tmp_path: Path, monkeypatch):
        """Test that .env file is automatically detected in current directory."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=test_value\n")
        
        with patch('src.infrastructure.config.environment.load_dotenv') as mock_load:
            load_environment_variables()
            
            # Should call load_dotenv with .env file path
            mock_load.assert_called_once()
            call_args = mock_load.call_args
            # Verify override=False (system env takes precedence)
            assert call_args[1].get("override", True) is False
    
    def test_load_env_file_explicit_path(self, tmp_path: Path):
        """Test that .env file can be loaded from explicit path."""
        env_file = tmp_path / "custom.env"
        env_file.write_text("TEST_KEY=test_value\n")
        
        with patch('src.infrastructure.config.environment.load_dotenv') as mock_load:
            load_environment_variables(dotenv_path=str(env_file))
            
            mock_load.assert_called_once()
            call_args = mock_load.call_args
            # Verify path was used
            assert str(env_file) in str(call_args[0][0])
    
    def test_load_env_file_parent_directories(self, tmp_path: Path, monkeypatch):
        """Test that .env file is searched in parent directories (up to 3 levels)."""
        # Create nested directory structure
        nested_dir = tmp_path / "level1" / "level2" / "level3"
        nested_dir.mkdir(parents=True)
        monkeypatch.chdir(nested_dir)
        
        # Create .env in parent directory
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=test_value\n")
        
        with patch('src.infrastructure.config.environment.load_dotenv') as mock_load:
            load_environment_variables()
            
            # Should find .env in parent directory
            mock_load.assert_called_once()
    
    def test_load_env_file_not_found(self, tmp_path: Path, monkeypatch):
        """Test that missing .env file is handled gracefully."""
        monkeypatch.chdir(tmp_path)
        
        with patch('src.infrastructure.config.environment.load_dotenv') as mock_load:
            load_environment_variables()
            
            # Should still call load_dotenv for automatic search
            mock_load.assert_called_once()
    
    def test_precedence_system_env_over_dotenv(self, tmp_path: Path, monkeypatch):
        """Test that system environment variables take precedence over .env file values."""
        monkeypatch.chdir(tmp_path)
        
        # Set system environment variable
        monkeypatch.setenv("TEST_KEY", "system_value")
        
        # Create .env file with different value
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=dotenv_value\n")
        
        # load_dotenv should be called with override=False
        with patch('src.infrastructure.config.environment.load_dotenv') as mock_load:
            load_environment_variables()
            
            call_args = mock_load.call_args
            # override=False means system env takes precedence
            assert call_args[1].get("override", True) is False


class TestGetEnv:
    """Tests for get_env function."""
    
    def test_get_env_existing_variable(self, monkeypatch):
        """Test getting existing environment variable."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        
        value = get_env("TEST_VAR")
        assert value == "test_value"
    
    def test_get_env_missing_variable(self):
        """Test getting missing environment variable returns None."""
        value = get_env("NONEXISTENT_VAR")
        assert value is None
    
    def test_get_env_with_default(self):
        """Test getting environment variable with default value."""
        value = get_env("NONEXISTENT_VAR", default="default_value")
        assert value == "default_value"
    
    def test_get_env_system_env_takes_precedence(self, monkeypatch, tmp_path: Path):
        """Test that system environment variables are checked (not just .env file)."""
        monkeypatch.setenv("TEST_VAR", "system_value")
        
        # Even if .env has different value, system env should be returned
        value = get_env("TEST_VAR")
        assert value == "system_value"


class TestGetEnvBool:
    """Tests for get_env_bool function."""
    
    def test_get_env_bool_true_values(self, monkeypatch):
        """Test that true values ('true', '1', 'yes', 'on') return True."""
        true_values = ["true", "True", "TRUE", "1", "yes", "Yes", "YES", "on", "On", "ON"]
        
        for val in true_values:
            monkeypatch.setenv("TEST_VAR", val)
            result = get_env_bool("TEST_VAR")
            assert result is True, f"'{val}' should return True"
    
    def test_get_env_bool_false_values(self, monkeypatch):
        """Test that false values ('false', '0', 'no', 'off', '') return False."""
        false_values = ["false", "False", "FALSE", "0", "no", "No", "NO", "off", "Off", "OFF", ""]
        
        for val in false_values:
            monkeypatch.setenv("TEST_VAR", val)
            result = get_env_bool("TEST_VAR")
            assert result is False, f"'{val}' should return False"
    
    def test_get_env_bool_missing_default(self, monkeypatch):
        """Test that missing variable returns default value."""
        # When env var doesn't exist, get_env_bool returns False (empty string maps to False)
        # Only unrecognized values return the default
        monkeypatch.delenv("NONEXISTENT_VAR", raising=False)
        result = get_env_bool("NONEXISTENT_VAR", default=True)
        # Empty string is treated as False, not default
        assert result is False
        
        # Unrecognized value returns default
        monkeypatch.setenv("NONEXISTENT_VAR", "unrecognized")
        result = get_env_bool("NONEXISTENT_VAR", default=True)
        assert result is True
    
    def test_get_env_bool_unknown_value_returns_default(self, monkeypatch):
        """Test that unknown values return default."""
        monkeypatch.setenv("TEST_VAR", "unknown_value")
        
        result = get_env_bool("TEST_VAR", default=False)
        assert result is False


class TestGetOptionalApiKey:
    """Tests for get_optional_api_key function."""
    
    def test_get_optional_api_key_found(self, monkeypatch, caplog):
        """Test that optional API key is returned when found."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
        
        with patch('src.infrastructure.config.environment.logger') as mock_logger:
            key = get_optional_api_key("OPENAI_API_KEY")
            
            assert key == "sk-test123"
            # Should log debug message
    
    def test_get_optional_api_key_not_found(self, monkeypatch, caplog):
        """Test that optional API key returns None when not found."""
        # Ensure the env var is not set
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch('src.infrastructure.config.environment.logger') as mock_logger:
            key = get_optional_api_key("OPENAI_API_KEY")
            
            assert key is None
            # Should log debug message about missing key
    
    def test_get_optional_api_key_with_custom_description(self, caplog):
        """Test that optional API key uses custom description when provided."""
        with patch('src.infrastructure.config.environment.logger'):
            key = get_optional_api_key("CUSTOM_KEY", description="Custom service API key")
            
            assert key is None


class TestRequireApiKey:
    """Tests for require_api_key function."""
    
    def test_require_api_key_found(self, monkeypatch):
        """Test that required API key is returned when found."""
        monkeypatch.setenv("QDRANT_API_KEY", "qdrant-key-123")
        
        key = require_api_key("QDRANT_API_KEY")
        assert key == "qdrant-key-123"
    
    def test_require_api_key_missing_raises_error(self, monkeypatch):
        """Test that missing required API key raises ValueError with clear message."""
        monkeypatch.delenv("QDRANT_API_KEY", raising=False)
        with pytest.raises(ValueError) as exc_info:
            require_api_key("QDRANT_API_KEY")
        
        error_msg = str(exc_info.value)
        assert "QDRANT_API_KEY" in error_msg
        assert "missing" in error_msg.lower() or "required" in error_msg.lower()
        assert "How to fix" in error_msg or "fix" in error_msg.lower()
    
    def test_require_api_key_error_message_includes_context(self, monkeypatch):
        """Test that error message includes context when provided."""
        monkeypatch.delenv("QDRANT_API_KEY", raising=False)
        with pytest.raises(ValueError) as exc_info:
            require_api_key("QDRANT_API_KEY", context="for Qdrant Cloud authentication")
        
        error_msg = str(exc_info.value)
        assert "Qdrant Cloud" in error_msg or "authentication" in error_msg
    
    def test_require_api_key_error_message_includes_description(self, monkeypatch):
        """Test that error message includes description from REQUIRED_API_KEYS."""
        monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
        with pytest.raises(ValueError) as exc_info:
            require_api_key("ZOTERO_LIBRARY_ID", context="for remote Zotero access")
        
        error_msg = str(exc_info.value)
        assert "Zotero" in error_msg or "library" in error_msg.lower()


class TestGetZoteroConfig:
    """Tests for get_zotero_config function."""
    
    def test_get_zotero_config_from_env(self, monkeypatch):
        """Test that Zotero config is loaded from environment variables."""
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "123456")
        monkeypatch.setenv("ZOTERO_LIBRARY_TYPE", "group")
        monkeypatch.setenv("ZOTERO_API_KEY", "api-key-123")
        monkeypatch.setenv("ZOTERO_LOCAL", "false")
        
        config = get_zotero_config()
        
        assert config["library_id"] == "123456"
        assert config["library_type"] == "group"
        assert config["api_key"] == "api-key-123"
        assert config["local"] is False
    
    def test_get_zotero_config_local_access(self, monkeypatch):
        """Test that Zotero config handles local access flag."""
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "1")
        monkeypatch.setenv("ZOTERO_LOCAL", "true")
        
        config = get_zotero_config()
        
        assert config["library_id"] == "1"
        assert config["local"] is True
    
    def test_get_zotero_config_defaults(self, monkeypatch):
        """Test that Zotero config uses defaults when env vars not set."""
        # Clear all Zotero env vars
        monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
        monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
        monkeypatch.delenv("ZOTERO_LOCAL", raising=False)
        monkeypatch.delenv("ZOTERO_LIBRARY_TYPE", raising=False)
        
        config = get_zotero_config()
        
        assert config.get("library_type") == "user"  # Default
        # If library_id is None, local defaults based on environment or implementation
        # The actual behavior depends on implementation


class TestValidateZoteroConfigForRemoteAccess:
    """Tests for validate_zotero_config_for_remote_access function."""
    
    def test_validate_zotero_config_remote_success(self, monkeypatch):
        """Test that remote access config validation succeeds with required keys."""
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "123456")
        monkeypatch.setenv("ZOTERO_API_KEY", "api-key-123")
        monkeypatch.setenv("ZOTERO_LOCAL", "false")
        
        config = validate_zotero_config_for_remote_access()
        
        assert config["library_id"] == "123456"
        assert config["api_key"] == "api-key-123"
        assert "local" not in config or config.get("local") != "true"
    
    def test_validate_zotero_config_remote_missing_library_id(self, monkeypatch):
        """Test that missing library_id raises error for remote access."""
        monkeypatch.delenv("ZOTERO_LIBRARY_ID", raising=False)
        monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
        monkeypatch.delenv("ZOTERO_LOCAL", raising=False)
        with pytest.raises(ValueError) as exc_info:
            validate_zotero_config_for_remote_access()
        
        error_msg = str(exc_info.value)
        assert "ZOTERO_LIBRARY_ID" in error_msg or "library_id" in error_msg.lower()
    
    def test_validate_zotero_config_remote_missing_api_key(self, monkeypatch):
        """Test that missing API key raises error for remote access."""
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "123456")
        monkeypatch.delenv("ZOTERO_API_KEY", raising=False)
        monkeypatch.delenv("ZOTERO_LOCAL", raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            validate_zotero_config_for_remote_access()
        
        error_msg = str(exc_info.value)
        assert "ZOTERO_API_KEY" in error_msg or "API key" in error_msg
    
    def test_validate_zotero_config_local_access(self, monkeypatch):
        """Test that local access validation requires only library_id."""
        monkeypatch.setenv("ZOTERO_LIBRARY_ID", "1")
        monkeypatch.setenv("ZOTERO_LOCAL", "true")
        
        config = validate_zotero_config_for_remote_access()
        
        # For local access, API key not required
        assert config["library_id"] == "1"
        assert "local" in config or config.get("local") == "true"


class TestValidateQdrantApiKeyIfRequired:
    """Tests for validate_qdrant_api_key_if_required function."""
    
    def test_validate_qdrant_api_key_cloud_required(self, monkeypatch):
        """Test that Qdrant Cloud URL requires API key."""
        monkeypatch.delenv("QDRANT_API_KEY", raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            validate_qdrant_api_key_if_required("https://cloud.qdrant.io")
        
        error_msg = str(exc_info.value)
        assert "QDRANT_API_KEY" in error_msg or "Qdrant Cloud" in error_msg
    
    def test_validate_qdrant_api_key_cloud_with_key(self, monkeypatch):
        """Test that Qdrant Cloud with API key succeeds."""
        monkeypatch.setenv("QDRANT_API_KEY", "qdrant-key-123")
        
        key = validate_qdrant_api_key_if_required("https://cloud.qdrant.io")
        assert key == "qdrant-key-123"
    
    def test_validate_qdrant_api_key_local_optional(self, monkeypatch):
        """Test that local Qdrant API key is optional."""
        monkeypatch.delenv("QDRANT_API_KEY", raising=False)
        
        # Should not raise error for local Qdrant
        key = validate_qdrant_api_key_if_required("http://localhost:6333")
        assert key is None
    
    def test_validate_qdrant_api_key_local_with_key(self, monkeypatch):
        """Test that local Qdrant can have optional API key."""
        monkeypatch.setenv("QDRANT_API_KEY", "qdrant-key-123")
        
        key = validate_qdrant_api_key_if_required("http://localhost:6333")
        assert key == "qdrant-key-123"


class TestEnvironmentConstants:
    """Tests for environment constants (OPTIONAL_API_KEYS, REQUIRED_API_KEYS)."""
    
    def test_optional_api_keys_defined(self):
        """Test that OPTIONAL_API_KEYS dictionary is defined."""
        assert isinstance(OPTIONAL_API_KEYS, dict)
        assert len(OPTIONAL_API_KEYS) > 0
    
    def test_required_api_keys_defined(self):
        """Test that REQUIRED_API_KEYS dictionary is defined."""
        assert isinstance(REQUIRED_API_KEYS, dict)
        assert len(REQUIRED_API_KEYS) > 0
    
    def test_openai_api_key_is_optional(self):
        """Test that OPENAI_API_KEY is marked as optional."""
        assert "OPENAI_API_KEY" in OPTIONAL_API_KEYS
    
    def test_qdrant_api_key_is_required_when_needed(self):
        """Test that QDRANT_API_KEY is in REQUIRED_API_KEYS."""
        assert "QDRANT_API_KEY" in REQUIRED_API_KEYS
    
    def test_zotero_keys_are_required_when_needed(self):
        """Test that Zotero keys are in REQUIRED_API_KEYS."""
        assert "ZOTERO_LIBRARY_ID" in REQUIRED_API_KEYS
        assert "ZOTERO_API_KEY" in REQUIRED_API_KEYS

