class MCPToolError(Exception):
    """Base exception for MCP tool failures."""


class SearchError(MCPToolError):
    """Raised when web search fails."""


class FetchError(MCPToolError):
    """Raised when static URL fetching fails."""


class BrowserError(MCPToolError):
    """Raised when browser-based fetching fails."""


class LocalFileError(MCPToolError):
    """Raised when local file access fails."""


class GitHubSearchError(MCPToolError):
    """Raised when GitHub search fails."""


class FileReaderError(MCPToolError):
    """Raised when document or image reading fails."""


class PaperError(MCPToolError):
    """Raised when paper search or reading fails."""


class ModelScopeError(MCPToolError):
    """Raised when ModelScope resource search fails."""


class HuggingFaceError(MCPToolError):
    """Raised when Hugging Face resource search fails."""


class PermissionDeniedError(MCPToolError):
    """Raised when a URL is blocked by permission policy."""
