# Environment Variable Configuration Guide

**Purpose**: Configure CiteLoom using environment variables for API keys, Zotero integration, and other sensitive settings.

**Last Updated**: 2025-10-31

## Overview

CiteLoom supports environment-based configuration to keep secrets out of version-controlled files. Environment variables take precedence over `.env` file values, which in turn override `citeloom.toml` defaults.

**Precedence Order**:
1. System environment variables (highest priority)
2. `.env` file values
3. `citeloom.toml` defaults (lowest priority)

## Setup `.env` File

Create a `.env` file in the project root (this file is automatically ignored by Git):

```bash
# Copy from template if available
cp .env.example .env  # Or create manually
```

## Optional API Keys

These keys are optional - CiteLoom will degrade gracefully if they're missing:

### OpenAI API Key

```bash
# Optional: For OpenAI embeddings (falls back to FastEmbed if not set)
OPENAI_API_KEY=sk-...
```

**When to use**: If you prefer OpenAI embeddings over FastEmbed default.

**Fallback**: FastEmbed (BAAI/bge-small-en-v1.5) is used if `OPENAI_API_KEY` is not set.

### Custom Configuration Path

```bash
# Optional: Override default citeloom.toml path
CITELOOM_CONFIG=./custom-config.toml
```

**When to use**: Multiple projects or custom configuration locations.

## Required API Keys (Context-Dependent)

These keys are required when specific conditions are met:

### Qdrant API Key

```bash
# Required for Qdrant Cloud, optional for local Qdrant
QDRANT_API_KEY=your-qdrant-cloud-api-key
QDRANT_URL=https://your-cluster.qdrant.io
```

**When required**: Using Qdrant Cloud (URL contains `cloud.qdrant.io`)

**When optional**: Using local Qdrant (`http://localhost:6333`)

**Error message**: If missing when required, CiteLoom will show:
```
Required API key 'QDRANT_API_KEY' is missing (for Qdrant Cloud authentication).
  How to fix: Set QDRANT_API_KEY in your environment or add it to a .env file.
  Example: QDRANT_API_KEY=your-qdrant-cloud-api-key
```

### Qdrant URL

```bash
# Optional: Override Qdrant URL from citeloom.toml
QDRANT_URL=http://localhost:6333
```

## Zotero Configuration

CiteLoom supports both remote and local Zotero access for metadata resolution.

### Remote Zotero Access (Recommended for Production)

**Required environment variables:**

```bash
ZOTERO_LIBRARY_ID=123456
ZOTERO_LIBRARY_TYPE=user  # or 'group' for group libraries
ZOTERO_API_KEY=your-zotero-api-key
ZOTERO_LOCAL=false  # or omit for remote access
```

**Getting your Zotero API key:**
1. Go to [Zotero Settings > Feeds/API](https://www.zotero.org/settings/keys)
2. Create a new private key with library read permissions
3. Copy the API key and add to `.env`

**Getting your Library ID:**
- User library: Your user ID is in your profile URL: `https://www.zotero.org/users/{USER_ID}/`
- Group library: Group ID is in the group URL: `https://www.zotero.org/groups/{GROUP_ID}/`

### Local Zotero Access (For Development)

**Required environment variables:**

```bash
ZOTERO_LIBRARY_ID=1  # Typically '1' for user library in local mode
ZOTERO_LOCAL=true
# ZOTERO_API_KEY not required for local access
```

**Prerequisites:**
- Zotero must be running with local HTTP API enabled
- Better BibTeX extension installed (optional, for citekey extraction)

**When to use**: Local development when Zotero is running on the same machine.

### Zotero Configuration in Code

You can also pass Zotero configuration programmatically:

```python
zotero_config = {
    "library_id": "123456",
    "library_type": "user",  # or "group"
    "api_key": "your-api-key",  # Required for remote
    "local": False  # True for local access
}
```

**Precedence**: Code config > Environment variables > `.env` file > `citeloom.toml`

## Better BibTeX Integration (Optional)

Better BibTeX enables citekey extraction for more reliable citation matching.

**Automatic Detection**: CiteLoom automatically detects if Better BibTeX is running:
- Port 23119: Zotero
- Port 24119: Juris-M

**No configuration needed**: Better BibTeX JSON-RPC API is accessed automatically when available.

**Fallback**: If Better BibTeX is not running, citekeys are extracted from Zotero item `extra` field.

## Complete Example `.env` File

```bash
# Qdrant Configuration (if using Qdrant Cloud)
QDRANT_API_KEY=your-qdrant-cloud-api-key
QDRANT_URL=https://your-cluster.qdrant.io

# Zotero Configuration (Remote Access)
ZOTERO_LIBRARY_ID=123456
ZOTERO_LIBRARY_TYPE=user
ZOTERO_API_KEY=your-zotero-api-key

# Optional: OpenAI Embeddings
OPENAI_API_KEY=sk-...

# Optional: Custom Config Path
CITELOOM_CONFIG=./citeloom.toml
```

## Validation

CiteLoom validates environment configuration when needed:

**Validate configuration:**
```bash
uv run citeloom validate
```

This command checks:
- Tokenizer-to-embedding alignment
- Vector database connectivity
- Collection presence and model locks
- Payload indexes
- Zotero library connectivity (if configured)

**Clear error messages**: If required keys are missing, CiteLoom provides actionable error messages with:
- What key is missing
- Why it's needed
- How to fix it

## Troubleshooting

### Environment Variables Not Loading

**Problem**: Changes to `.env` file not taking effect

**Solutions**:
1. **Check file location**: `.env` must be in project root (same directory as `citeloom.toml`)
2. **Restart application**: Restart CLI or MCP server after changes
3. **Check precedence**: System environment variables override `.env` values
4. **Verify syntax**: No quotes around values, no spaces around `=`

**Example (correct)**:
```bash
ZOTERO_API_KEY=abc123
```

**Example (incorrect)**:
```bash
ZOTERO_API_KEY = "abc123"  # Wrong: spaces and quotes
```

### Zotero Connection Errors

**Problem**: `Zotero API error during metadata resolution`

**Solutions**:
1. **Remote access**: Verify `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` are correct
2. **Local access**: Ensure Zotero is running with local HTTP API enabled
3. **Network issues**: Check firewall/network settings for remote access
4. **Non-blocking**: Metadata resolution errors are non-blocking - documents will still be ingested

### Qdrant Authentication Errors

**Problem**: `QDRANT_API_KEY is required for Qdrant Cloud authentication`

**Solutions**:
1. **For Qdrant Cloud**: Set `QDRANT_API_KEY` in `.env` or environment
2. **For local Qdrant**: API key is optional - remove from `.env` if not needed
3. **Check URL**: Ensure `QDRANT_URL` points to correct cluster

## Security Best Practices

1. **Never commit `.env` files**: Already in `.gitignore`
2. **Use environment variables in CI/CD**: Set secrets in CI/CD platform, not in files
3. **Rotate API keys regularly**: Update keys in environment or `.env` file
4. **Limit API key permissions**: For Zotero, create keys with minimum required permissions

## Next Steps

- Review [Setup Guide](setup-guide.md) for initial configuration
- Check [FastMCP Configuration](#) for MCP server setup
- Explore [Architecture Documentation](../.specify/memory/constitution.md) for design details

