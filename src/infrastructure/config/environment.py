"""Environment variable loading from .env files with precedence support."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Optional API keys (gracefully degrade when missing)
OPTIONAL_API_KEYS = {
    "OPENAI_API_KEY": "OpenAI embeddings (falls back to FastEmbed default)",
    "CITELOOM_CONFIG": "Custom configuration file path (defaults to citeloom.toml)",
}

# Required API keys (context-dependent: required when specific conditions are met)
REQUIRED_API_KEYS = {
    "QDRANT_API_KEY": "Qdrant API key (required when Qdrant authentication is enabled)",
    "ZOTERO_LIBRARY_ID": "Zotero library ID (required for remote Zotero access)",
    "ZOTERO_API_KEY": "Zotero API key (required for remote Zotero access when ZOTERO_LOCAL is false)",
}


def load_environment_variables(dotenv_path: Path | str | None = None) -> None:
    """
    Load environment variables from .env file with automatic detection.
    
    T090: python-dotenv loading with automatic .env file detection.
    T091: Precedence logic - system env > .env file values (via override=False).
    
    Environment variables from system environment take precedence over .env file values.
    This function uses python-dotenv's load_dotenv() which respects existing environment
    variables by default (override=False).
    
    Args:
        dotenv_path: Optional path to .env file. If None, searches for .env file in:
                     - Current working directory
                     - Parent directories (up to 3 levels)
    """
    if dotenv_path is None:
        # Auto-detect .env file (search current dir and up to 3 parent dirs)
        current = Path.cwd()
        search_paths = [
            current / ".env",
            current.parent / ".env",
            current.parent.parent / ".env",
            current.parent.parent.parent / ".env",
        ]
        
        # Use first found .env file
        for path in search_paths:
            if path.exists():
                dotenv_path = path
                logger.debug(f"Loading .env file from: {path}")
                break
        
        # If no .env found, dotenv will search automatically
        if dotenv_path is None:
            load_dotenv(override=False)
            return
    
    dotenv_path = Path(dotenv_path)
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)
        logger.debug(f"Loaded .env file from: {dotenv_path}")
    else:
        logger.debug(f".env file not found at: {dotenv_path}")


def get_env(key: str, default: str | None = None) -> str | None:
    """
    Get environment variable value.
    
    Checks system environment variables (which take precedence over .env file).
    
    Args:
        key: Environment variable name
        default: Default value if not found
    
    Returns:
        Environment variable value or default
    """
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    """
    Get boolean environment variable.
    
    Accepts: 'true', '1', 'yes', 'on' (case-insensitive) → True
            'false', '0', 'no', 'off', '' (case-insensitive) → False
    
    Args:
        key: Environment variable name
        default: Default value if not found
    
    Returns:
        Boolean value
    """
    value = os.getenv(key, "").lower().strip()
    if value in ("true", "1", "yes", "on"):
        return True
    if value in ("false", "0", "no", "off", ""):
        return False
    return default


def get_optional_api_key(key: str, description: str | None = None) -> str | None:
    """
    T092: Get optional API key with graceful degradation.
    
    Returns the API key if present, None otherwise. Logs a debug message if missing.
    Optional keys are allowed to be absent and the system should degrade gracefully.
    
    Args:
        key: Environment variable name for the API key
        description: Optional description of what the key is used for
    
    Returns:
        API key value if present, None otherwise
    """
    value = get_env(key)
    if value:
        logger.debug(f"Optional API key {key} found")
        return value
    
    desc = description or OPTIONAL_API_KEYS.get(key, "optional service")
    logger.debug(f"Optional API key {key} not found ({desc}). System will use defaults.")
    return None


def require_api_key(
    key: str,
    context: str | None = None,
    description: str | None = None,
) -> str:
    """
    T093: Require API key with clear error message.
    
    Raises ValueError with clear guidance if the key is missing.
    Required keys must be present for specific operations.
    
    Args:
        key: Environment variable name for the API key
        context: Optional context describing when this key is required
        description: Optional description of what the key is used for
    
    Returns:
        API key value (never None)
    
    Raises:
        ValueError: If the API key is missing, with clear error message and guidance
    """
    value = get_env(key)
    if value:
        return value
    
    # Build clear error message
    desc = description or REQUIRED_API_KEYS.get(key, "required service")
    context_msg = f" ({context})" if context else ""
    
    error_msg = (
        f"Required API key '{key}' is missing{context_msg}.\n"
        f"  Description: {desc}\n"
        f"  How to fix: Set {key} in your environment or add it to a .env file in the project root.\n"
        f"  Example: {key}=your-api-key-here"
    )
    
    logger.error(error_msg)
    raise ValueError(error_msg)


def get_zotero_config() -> dict[str, str | bool]:
    """
    T094: Get Zotero configuration from environment variables.
    
    Returns a configuration dict with Zotero settings loaded from environment:
    - ZOTERO_LIBRARY_ID: Zotero library ID
    - ZOTERO_LIBRARY_TYPE: 'user' or 'group' (defaults to 'user')
    - ZOTERO_API_KEY: API key for remote access
    - ZOTERO_LOCAL: Boolean flag for local access (defaults to False)
    
    Returns:
        Dict with keys: library_id, library_type, api_key (optional), local
    """
    config: dict[str, str | bool] = {}
    
    library_id = get_env("ZOTERO_LIBRARY_ID")
    if library_id:
        config["library_id"] = library_id
    
    library_type = get_env("ZOTERO_LIBRARY_TYPE") or "user"
    config["library_type"] = library_type
    
    api_key = get_env("ZOTERO_API_KEY")
    if api_key:
        config["api_key"] = api_key
    
    config["local"] = get_env_bool("ZOTERO_LOCAL", False)
    
    return config


def validate_zotero_config_for_remote_access() -> dict[str, str]:
    """
    T093: Validate Zotero configuration for remote access with clear error messages.
    
    Raises ValueError if required keys are missing for remote access.
    
    Returns:
        Dict with library_id, library_type, api_key (guaranteed to be present)
    
    Raises:
        ValueError: If ZOTERO_LIBRARY_ID or ZOTERO_API_KEY is missing for remote access
    """
    use_local = get_env_bool("ZOTERO_LOCAL", False)
    
    if use_local:
        # Local access doesn't require API key
        library_id = get_env("ZOTERO_LIBRARY_ID")
        if library_id:
            return {
                "library_id": library_id,
                "library_type": get_env("ZOTERO_LIBRARY_TYPE") or "user",
                "local": "true",
            }
        else:
            raise ValueError(
                "Zotero local access requires ZOTERO_LIBRARY_ID.\n"
                "  How to fix: Set ZOTERO_LIBRARY_ID in your environment or add it to a .env file.\n"
                "  Example: ZOTERO_LIBRARY_ID=1 ZOTERO_LOCAL=true"
            )
    
    # Remote access requires both library_id and api_key
    library_id = require_api_key(
        "ZOTERO_LIBRARY_ID",
        context="for remote Zotero access",
        description="Zotero library ID (required for remote access)",
    )
    
    api_key = require_api_key(
        "ZOTERO_API_KEY",
        context="for remote Zotero access",
        description="Zotero API key (required for remote access when ZOTERO_LOCAL is false)",
    )
    
    return {
        "library_id": library_id,
        "library_type": get_env("ZOTERO_LIBRARY_TYPE") or "user",
        "api_key": api_key,
    }


def validate_qdrant_api_key_if_required(qdrant_url: str) -> str | None:
    """
    T093: Validate Qdrant API key if authentication is required.
    
    Qdrant API key is required when using Qdrant Cloud (URL contains 'cloud.qdrant.io')
    or when explicitly configured. For local Qdrant, API key is optional.
    
    Args:
        qdrant_url: Qdrant server URL
    
    Returns:
        API key value if present/required, None if not required
    
    Raises:
        ValueError: If QDRANT_API_KEY is missing when authentication is required
    """
    api_key = get_env("QDRANT_API_KEY")
    
    # Qdrant Cloud requires authentication
    if "cloud.qdrant.io" in qdrant_url.lower():
        if not api_key:
            raise ValueError(
                "QDRANT_API_KEY is required for Qdrant Cloud authentication.\n"
                "  How to fix: Set QDRANT_API_KEY in your environment or add it to a .env file.\n"
                "  Example: QDRANT_API_KEY=your-qdrant-cloud-api-key"
            )
        return api_key
    
    # Local Qdrant: API key is optional
    if api_key:
        logger.debug("QDRANT_API_KEY found (optional for local Qdrant)")
    
    return api_key


# Auto-load on import (common pattern for environment modules)
load_environment_variables()

