"""Environment variable loading from .env files with precedence support."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def load_environment_variables(dotenv_path: Path | str | None = None) -> None:
    """
    Load environment variables from .env file with automatic detection.
    
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
                break
        
        # If no .env found, dotenv will search automatically
        if dotenv_path is None:
            load_dotenv(override=False)
            return
    
    dotenv_path = Path(dotenv_path)
    if dotenv_path.exists():
        load_dotenv(dotenv_path, override=False)


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


# Auto-load on import (common pattern for environment modules)
load_environment_variables()

