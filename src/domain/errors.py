"""Domain errors for chunk retrieval operations."""


class EmbeddingModelMismatch(Exception):
    """
    Raised when embedding model doesn't match project's stored model.
    
    Attributes:
        project_id: Project identifier
        expected_model: Expected embedding model
        provided_model: Provided embedding model
    """
    
    def __init__(self, project_id: str, expected_model: str, provided_model: str) -> None:
        self.project_id = project_id
        self.expected_model = expected_model
        self.provided_model = provided_model
        super().__init__(
            f"Embedding model mismatch for project '{project_id}': "
            f"expected '{expected_model}', provided '{provided_model}'"
        )


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
