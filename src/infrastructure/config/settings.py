"""Pydantic settings for citeloom.toml configuration."""

import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class PathsSettings(BaseModel):
    """Path configuration settings."""
    
    raw_dir: str = "assets/raw"
    audit_dir: str = "var/audit"


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
    projects: dict[str, ProjectSettings] = Field(default_factory=dict)
    
    @classmethod
    def from_toml(cls, toml_path: Path | str = "citeloom.toml") -> "Settings":
        """
        Load settings from citeloom.toml file.
        
        Args:
            toml_path: Path to citeloom.toml file
        
        Returns:
            Settings instance with loaded configuration
        """
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
        
        # Extract project settings
        projects: dict[str, ProjectSettings] = {}
        for key, value in data.items():
            if key.startswith("project.") and isinstance(value, dict):
                # Extract project ID from key like "project.\"citeloom/clean-arch\""
                project_id = key.replace("project.", "").strip('"')
                projects[project_id] = ProjectSettings(**value)
            elif key == "project" and isinstance(value, dict):
                # Handle single project block (legacy format)
                project_id = value.get("id", "default")
                projects[project_id] = ProjectSettings(**value)
        
        return cls(
            chunking=chunking,
            qdrant=qdrant,
            paths=paths,
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

