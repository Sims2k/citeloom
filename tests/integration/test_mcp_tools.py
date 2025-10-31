"""Integration tests for MCP tools."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from infrastructure.config.settings import Settings
from infrastructure.mcp.tools import (
    handle_tool_call,
    MCPToolError,
    MCPErrorCode,
)


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Create test settings with a sample project."""
    # Create a temporary citeloom.toml
    config_file = tmp_path / "citeloom.toml"
    config_content = """[project."test/project"]
collection = "proj-test-project"
references_json = "test.json"
embedding_model = "fastembed/all-MiniLM-L6-v2"
hybrid_enabled = true

[qdrant]
url = "http://localhost:6333"
create_fulltext_index = true
"""
    config_file.write_text(config_content)
    
    return Settings.from_toml(config_file)


@pytest.mark.asyncio
async def test_list_projects(test_settings: Settings) -> None:
    """Test list_projects tool."""
    result = await handle_tool_call("list_projects", {}, test_settings)
    result_data = json.loads(result)
    
    assert "projects" in result_data
    assert isinstance(result_data["projects"], list)
    assert len(result_data["projects"]) > 0
    
    project = result_data["projects"][0]
    assert "id" in project
    assert "collection" in project
    assert "embed_model" in project
    assert "hybrid_enabled" in project


@pytest.mark.asyncio
async def test_list_projects_empty() -> None:
    """Test list_projects with empty settings."""
    empty_settings = Settings()
    result = await handle_tool_call("list_projects", {}, empty_settings)
    result_data = json.loads(result)
    
    assert "projects" in result_data
    assert result_data["projects"] == []


@pytest.mark.asyncio
async def test_find_chunks_invalid_project(test_settings: Settings) -> None:
    """Test find_chunks with invalid project."""
    arguments = {
        "project": "nonexistent/project",
        "query": "test query",
    }
    
    result = await handle_tool_call("find_chunks", arguments, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == MCPErrorCode.INVALID_PROJECT


@pytest.mark.asyncio
async def test_query_hybrid_invalid_project(test_settings: Settings) -> None:
    """Test query_hybrid with invalid project."""
    arguments = {
        "project": "nonexistent/project",
        "query": "test query",
    }
    
    result = await handle_tool_call("query_hybrid", arguments, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == MCPErrorCode.INVALID_PROJECT


@pytest.mark.asyncio
async def test_query_hybrid_not_supported(test_settings: Settings) -> None:
    """Test query_hybrid when hybrid is not enabled for project."""
    # Modify test project to disable hybrid
    test_settings.projects["test/project"].hybrid_enabled = False
    
    arguments = {
        "project": "test/project",
        "query": "test query",
    }
    
    result = await handle_tool_call("query_hybrid", arguments, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == MCPErrorCode.HYBRID_NOT_SUPPORTED


@pytest.mark.asyncio
async def test_inspect_collection_invalid_project(test_settings: Settings) -> None:
    """Test inspect_collection with invalid project."""
    arguments = {
        "project": "nonexistent/project",
    }
    
    result = await handle_tool_call("inspect_collection", arguments, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == MCPErrorCode.INVALID_PROJECT


@pytest.mark.asyncio
async def test_store_chunks_invalid_batch_size(test_settings: Settings) -> None:
    """Test store_chunks with invalid batch size."""
    arguments = {
        "project": "test/project",
        "items": [{"id": "chunk-1", "text": "test", "embedding": [0.1] * 384, "metadata": {}}] * 50,  # Too small
    }
    
    result = await handle_tool_call("store_chunks", arguments, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_store_chunks_invalid_project(test_settings: Settings) -> None:
    """Test store_chunks with invalid project."""
    arguments = {
        "project": "nonexistent/project",
        "items": [{"id": "chunk-1", "text": "test", "embedding": [0.1] * 384, "metadata": {}}] * 100,
    }
    
    result = await handle_tool_call("store_chunks", arguments, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == MCPErrorCode.INVALID_PROJECT


@pytest.mark.asyncio
async def test_unknown_tool(test_settings: Settings) -> None:
    """Test unknown tool name."""
    result = await handle_tool_call("unknown_tool", {}, test_settings)
    result_data = json.loads(result)
    
    # Should return error response
    assert "error" in result_data
    assert result_data["error"]["code"] == "UNKNOWN_TOOL"

