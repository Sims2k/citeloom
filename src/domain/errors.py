"""Domain errors for chunk retrieval operations."""


class EmbeddingModelMismatch(Exception):
    """
    Raised when embedding model doesn't match project's stored model.
    
    Attributes:
        project_id: Project identifier
        expected_model: Expected embedding model
        provided_model: Provided embedding model
        collection_name: Collection name (optional, for enhanced error messages)
    """
    
    def __init__(
        self,
        project_id: str,
        expected_model: str,
        provided_model: str,
        collection_name: str | None = None,
    ) -> None:
        self.project_id = project_id
        self.expected_model = expected_model
        self.provided_model = provided_model
        self.collection_name = collection_name
        
        # Build friendly, actionable error message
        collection_info = f"Collection '{collection_name}'" if collection_name else f"Project '{project_id}'"
        message = (
            f"{collection_info} is bound to embedding model '{expected_model}'. "
            f"You requested '{provided_model}'. "
            f"Use `citeloom ingest run --project {project_id} --embedding-model {expected_model}` "
            f"to switch back to the bound model, or use `--force-rebuild` flag to migrate to the new model."
        )
        super().__init__(message)


class ProjectNotFound(Exception):
    """
    Raised when project identifier doesn't exist.
    
    Attributes:
        project_id: Non-existent project identifier
    """
    
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Project '{project_id}' not found")


class HybridNotSupported(Exception):
    """
    Raised when hybrid search is requested but not enabled for project.
    
    Attributes:
        project_id: Project identifier
        reason: Why hybrid is not supported
    """
    
    def __init__(self, project_id: str, reason: str) -> None:
        self.project_id = project_id
        self.reason = reason
        super().__init__(f"Hybrid search not supported for project '{project_id}': {reason}")


class MetadataMissing(Exception):
    """
    Raised when citation metadata cannot be resolved (non-blocking warning).
    
    Attributes:
        doc_id: Document identifier
        hint: Actionable hint for resolution
    """
    
    def __init__(self, doc_id: str, hint: str) -> None:
        self.doc_id = doc_id
        self.hint = hint
        super().__init__(f"Metadata not found for document '{doc_id}': {hint}")


class ChunkingError(Exception):
    """
    Raised when chunking fails.
    
    Attributes:
        message: Error message
        reason: Detailed reason for failure (optional)
    """
    
    def __init__(self, message: str, reason: str | None = None) -> None:
        self.message = message
        self.reason = reason
        super().__init__(f"{message}: {reason}" if reason else message)


class ZoteroDatabaseLockedError(Exception):
    """
    Raised when Zotero database is locked and cannot be accessed.
    
    Attributes:
        db_path: Path to Zotero database file
        hint: Actionable hint for resolution
    """
    
    def __init__(self, db_path: str, hint: str | None = None) -> None:
        self.db_path = db_path
        self.hint = hint
        msg = f"Zotero database is locked: {db_path}"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class ZoteroDatabaseNotFoundError(Exception):
    """
    Raised when Zotero database file does not exist.
    
    Attributes:
        db_path: Path to Zotero database file that was not found
        hint: Actionable hint for resolution
    """
    
    def __init__(self, db_path: str, hint: str | None = None) -> None:
        self.db_path = db_path
        self.hint = hint
        msg = f"Zotero database not found: {db_path}"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class ZoteroProfileNotFoundError(Exception):
    """
    Raised when Zotero profile directory cannot be found.
    
    Attributes:
        profile_dir: Expected profile directory path
        hint: Actionable hint for resolution
    """
    
    def __init__(self, profile_dir: str, hint: str | None = None) -> None:
        self.profile_dir = profile_dir
        self.hint = hint
        msg = f"Zotero profile not found: {profile_dir}"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class ZoteroPathResolutionError(Exception):
    """
    Raised when attachment path cannot be resolved from Zotero database.
    
    Attributes:
        attachment_key: Zotero attachment key
        link_mode: Link mode from database (0=imported, 1=linked)
        hint: Actionable hint for resolution
    """
    
    def __init__(self, attachment_key: str, link_mode: int | None = None, hint: str | None = None) -> None:
        self.attachment_key = attachment_key
        self.link_mode = link_mode
        self.hint = hint
        msg = f"Cannot resolve path for attachment: {attachment_key}"
        if link_mode is not None:
            msg += f" (linkMode={link_mode})"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class ZoteroFulltextNotFoundError(Exception):
    """
    Raised when fulltext is not available for a Zotero attachment.
    
    Attributes:
        attachment_key: Zotero attachment key
        hint: Actionable hint for resolution
    """
    
    def __init__(self, attachment_key: str, hint: str | None = None) -> None:
        self.attachment_key = attachment_key
        self.hint = hint
        msg = f"Zotero fulltext not found for attachment: {attachment_key}"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class ZoteroFulltextQualityError(Exception):
    """
    Raised when Zotero fulltext exists but fails quality validation.
    
    Attributes:
        attachment_key: Zotero attachment key
        reason: Reason for quality failure
        hint: Actionable hint for resolution
    """
    
    def __init__(self, attachment_key: str, reason: str, hint: str | None = None) -> None:
        self.attachment_key = attachment_key
        self.reason = reason
        self.hint = hint
        msg = f"Zotero fulltext quality check failed for attachment {attachment_key}: {reason}"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)


class ZoteroAnnotationNotFoundError(Exception):
    """
    Raised when annotations cannot be fetched for a Zotero attachment.
    
    Attributes:
        attachment_key: Zotero attachment key
        hint: Actionable hint for resolution
    """
    
    def __init__(self, attachment_key: str, hint: str | None = None) -> None:
        self.attachment_key = attachment_key
        self.hint = hint
        msg = f"Annotations not found for attachment: {attachment_key}"
        if hint:
            msg += f". {hint}"
        super().__init__(msg)