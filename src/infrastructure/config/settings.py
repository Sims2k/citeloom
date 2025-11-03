"""Pydantic settings for citeloom.toml configuration."""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .environment import get_env, get_zotero_config, load_environment_variables


class ChunkingSettings(BaseModel):
    """Chunking configuration settings."""
    
    max_tokens: int = 450
    overlap_tokens: int = 60
    heading_context: int = 2
    tokenizer: str = "minilm"


class QdrantSettings(BaseModel):
    """Qdrant connection settings."""
    
    url: str = "http://localhost:6333"
    api_key: str = ""
    timeout_ms: int = 15000
    create_fulltext_index: bool = True
    
    def __init__(self, **data: Any) -> None:
        """Initialize with environment variable precedence."""
        # Ensure environment is loaded
        load_environment_variables()
        
        # Override with environment variables if present (system env > .env > defaults)
        # Environment variables take precedence over TOML values
        env_api_key = get_env("QDRANT_API_KEY")
        if env_api_key is not None:
            data["api_key"] = env_api_key
        elif "api_key" not in data:
            data["api_key"] = ""
        
        env_url = get_env("QDRANT_URL")
        if env_url is not None:
            data["url"] = env_url
        elif "url" not in data:
            data["url"] = "http://localhost:6333"
        
        super().__init__(**data)


class PathsSettings(BaseModel):
    """Path configuration settings."""
    
    raw_dir: str = "assets/raw"
    audit_dir: str = "var/audit"


class ZoteroFulltextSettings(BaseModel):
    """Zotero fulltext configuration settings."""
    
    min_length: int = 100  # Minimum text length for quality validation


class ZoteroWebSettings(BaseModel):
    """Zotero Web API configuration settings."""
    
    library_id: str = ""
    api_key: str = ""
    
    def __init__(self, **data: Any) -> None:
        """Initialize with environment variable precedence."""
        # Ensure environment is loaded
        load_environment_variables()
        
        # Override with environment variables if present (system env > .env > defaults)
        # Environment variables take precedence over TOML values
        env_library_id = get_env("ZOTERO_LIBRARY_ID")
        if env_library_id is not None:
            data["library_id"] = env_library_id
        elif "library_id" not in data:
            data["library_id"] = ""
        
        env_api_key = get_env("ZOTERO_API_KEY")
        if env_api_key is not None:
            data["api_key"] = env_api_key
        elif "api_key" not in data:
            data["api_key"] = ""
        
        super().__init__(**data)


class ZoteroSettings(BaseModel):
    """Zotero integration configuration settings."""
    
    mode: str = "web-first"  # "local-first", "web-first", "auto", "local-only", "web-only"
    db_path: str | None = None  # Optional override for Zotero database path
    storage_dir: str | None = None  # Optional override for Zotero storage directory
    include_annotations: bool = False  # Whether to index PDF annotations
    prefer_zotero_fulltext: bool = True  # Prefer Zotero fulltext when available
    fulltext: ZoteroFulltextSettings = Field(default_factory=ZoteroFulltextSettings)
    web: ZoteroWebSettings = Field(default_factory=ZoteroWebSettings)


class ProjectSettings(BaseModel):
    """Project-specific configuration."""
    
    collection: str
    references_json: Path
    embedding_model: str
    hybrid_enabled: bool = True
    
    @field_validator("references_json", mode="before")
    @classmethod
    def validate_references_path(cls, v: Any) -> Path:
        """Convert string to Path."""
        if isinstance(v, str):
            return Path(v)
        return v


class Settings(BaseModel):
    """Main settings loaded from citeloom.toml."""
    
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    zotero: ZoteroSettings = Field(default_factory=ZoteroSettings)
    projects: dict[str, ProjectSettings] = Field(default_factory=dict)
    
    @classmethod
    def from_toml(cls, toml_path: Path | str = "citeloom.toml") -> "Settings":
        """
        Load settings from citeloom.toml file with environment variable precedence.
        
        Environment variables (system env > .env file) override TOML values.
        
        Args:
            toml_path: Path to citeloom.toml file
        
        Returns:
            Settings instance with loaded configuration
        """
        # Load environment variables first (respects precedence: system env > .env)
        load_environment_variables()
        
        toml_path = Path(toml_path)
        
        if not toml_path.exists():
            # Return defaults if file doesn't exist
            return cls()
        
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        
        # Extract chunking settings
        chunking_data = data.get("chunking", {})
        chunking = ChunkingSettings(**chunking_data)
        
        # Extract Qdrant settings
        qdrant_data = data.get("qdrant", {})
        qdrant = QdrantSettings(**qdrant_data)
        
        # Extract paths settings
        paths_data = data.get("paths", {})
        paths = PathsSettings(**paths_data)
        
        # Extract Zotero settings
        zotero_data = data.get("zotero", {})
        zotero_fulltext_data = zotero_data.get("fulltext", {})
        zotero_web_data = zotero_data.get("web", {})
        zotero = ZoteroSettings(
            mode=zotero_data.get("mode", "web-first"),
            db_path=zotero_data.get("db_path"),
            storage_dir=zotero_data.get("storage_dir"),
            include_annotations=zotero_data.get("include_annotations", False),
            prefer_zotero_fulltext=zotero_data.get("prefer_zotero_fulltext", True),
            fulltext=ZoteroFulltextSettings(**zotero_fulltext_data),
            web=ZoteroWebSettings(**zotero_web_data),
        )
        
        # Extract project settings
        projects: dict[str, ProjectSettings] = {}
        # Handle nested project structure: [project."id"] creates data['project']['id']
        if "project" in data and isinstance(data["project"], dict):
            for project_id, project_data in data["project"].items():
                if isinstance(project_data, dict):
                    projects[project_id] = ProjectSettings(**project_data)
        # Handle legacy format or direct "project." keys (for backwards compatibility)
        for key, value in data.items():
            if key.startswith("project.") and isinstance(value, dict):
                # Extract project ID from key like "project.\"citeloom/clean-arch\""
                project_id = key.replace("project.", "").strip('"')
                projects[project_id] = ProjectSettings(**value)
            elif key == "project" and isinstance(value, dict) and "id" in value:
                # Handle single project block (legacy format)
                project_id = value.get("id", "default")
                projects[project_id] = ProjectSettings(**value)
        
        return cls(
            chunking=chunking,
            qdrant=qdrant,
            paths=paths,
            zotero=zotero,
            projects=projects,
        )
    
    def get_project(self, project_id: str) -> ProjectSettings:
        """
        Get project settings by ID.
        
        Args:
            project_id: Project identifier
        
        Returns:
            ProjectSettings for the project
        
        Raises:
            KeyError: If project not found
        """
        if project_id not in self.projects:
            available = ", ".join(self.projects.keys())
            raise KeyError(
                f"Project '{project_id}' not found. Available projects: {available}"
            )
        return self.projects[project_id]
    
    def get_zotero_config(self) -> dict[str, Any]:
        """
        T095: Get Zotero configuration from environment variables.
        
        Returns Zotero configuration loaded from environment variables.
        This method uses environment variable precedence (system env > .env file).
        
        Configuration keys:
        - ZOTERO_LIBRARY_ID: Zotero library ID
        - ZOTERO_LIBRARY_TYPE: 'user' or 'group' (defaults to 'user')
        - ZOTERO_API_KEY: API key for remote access (optional)
        - ZOTERO_LOCAL: Boolean flag for local access (defaults to False)
        
        Returns:
            Dict with Zotero configuration. Keys:
            - library_id: str | None
            - library_type: str (defaults to 'user')
            - api_key: str | None (for remote access)
            - local: bool (defaults to False)
        
        Example:
            >>> settings = Settings.from_toml()
            >>> zotero_config = settings.get_zotero_config()
            >>> # Use zotero_config with ZoteroPyzoteroResolver
        """
        # Ensure environment is loaded
        load_environment_variables()
        
        # Get Zotero config from environment
        return get_zotero_config()

