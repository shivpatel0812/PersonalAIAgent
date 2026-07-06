"""Google Drive tools - allows the agent to access and manage Google Drive files."""

from typing import Any
from pydantic import BaseModel
import io

from app.ai.tools.base import Tool, ToolParameter
from app.google.oauth import load_credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


class DriveFile(BaseModel):
    """Represents a Google Drive file."""
    id: str
    name: str
    mime_type: str
    created_time: str
    modified_time: str
    size: str | None = None
    web_view_link: str | None = None
    is_folder: bool = False


class ListDriveFilesResult(BaseModel):
    """Result of listing Drive files."""
    success: bool
    files: list[DriveFile] = []
    count: int
    message: str


class ListDriveFilesTool(Tool):
    """Tool for listing files in Google Drive."""

    @property
    def name(self) -> str:
        return "list_drive_files"

    @property
    def description(self) -> str:
        return "list files and folders in Google Drive with optional search query"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of files to return (default: 10)",
                "required": False,
            },
            {
                "name": "query",
                "type": "string",
                "description": "search query (e.g., 'name contains \"report\"', 'mimeType=\"application/pdf\"')",
                "required": False,
            },
            {
                "name": "folder_id",
                "type": "string",
                "description": "list files in specific folder by folder ID (optional)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ListDriveFilesResult:
        """
        List files in Google Drive.

        Args:
            max_results: Maximum number of files (default 10)
            query: Drive search query (optional)
            folder_id: Specific folder ID to list (optional)

        Returns:
            ListDriveFilesResult with list of files
        """
        max_results = kwargs.get("max_results", 10)
        query = kwargs.get("query", "").strip()
        folder_id = kwargs.get("folder_id", "").strip()

        credentials = load_credentials()
        if not credentials:
            return ListDriveFilesResult(
                success=False,
                count=0,
                message="Google Drive is not connected. Please connect your Google account first."
            )

        try:
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)

            # Build query
            search_query = query if query else ""
            if folder_id:
                search_query = f"'{folder_id}' in parents"
                if query:
                    search_query += f" and ({query})"

            # List files
            results = service.files().list(
                pageSize=max_results,
                q=search_query if search_query else None,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)",
                orderBy="modifiedTime desc"
            ).execute()

            files = results.get('files', [])

            drive_files = []
            for file in files:
                is_folder = file['mimeType'] == 'application/vnd.google-apps.folder'
                size = file.get('size', 'N/A') if not is_folder else None

                drive_files.append(DriveFile(
                    id=file['id'],
                    name=file['name'],
                    mime_type=file['mimeType'],
                    created_time=file['createdTime'],
                    modified_time=file['modifiedTime'],
                    size=size,
                    web_view_link=file.get('webViewLink'),
                    is_folder=is_folder
                ))

            msg = f"Found {len(drive_files)} file(s)"
            if folder_id:
                msg += f" in folder"
            if query:
                msg += f" matching '{query}'"

            return ListDriveFilesResult(
                success=True,
                files=drive_files,
                count=len(drive_files),
                message=msg
            )

        except Exception as e:
            return ListDriveFilesResult(
                success=False,
                count=0,
                message=f"Failed to list Drive files: {str(e)}"
            )


class ReadDriveFileResult(BaseModel):
    """Result of reading a Drive file."""
    success: bool
    file_id: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    content: str | None = None
    message: str


class ReadDriveFileTool(Tool):
    """Tool for reading content from Google Drive files."""

    @property
    def name(self) -> str:
        return "read_drive_file"

    @property
    def description(self) -> str:
        return "read the content of a text file from Google Drive (supports Docs, text files, etc.)"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "file_id",
                "type": "string",
                "description": "the ID of the file to read (get from list_drive_files)",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> ReadDriveFileResult:
        """
        Read content from a Drive file.

        Args:
            file_id: The ID of the file to read

        Returns:
            ReadDriveFileResult with file content
        """
        file_id = kwargs.get("file_id", "").strip()

        if not file_id:
            raise ValueError("File ID is required")

        credentials = load_credentials()
        if not credentials:
            return ReadDriveFileResult(
                success=False,
                message="Google Drive is not connected. Please connect your Google account first."
            )

        try:
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)

            # Get file metadata
            file_metadata = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()

            mime_type = file_metadata['mimeType']
            file_name = file_metadata['name']

            # Handle Google Docs
            if mime_type == 'application/vnd.google-apps.document':
                # Export as plain text
                request = service.files().export_media(fileId=file_id, mimeType='text/plain')
                content_bytes = io.BytesIO()
                downloader = MediaIoBaseDownload(content_bytes, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                content = content_bytes.getvalue().decode('utf-8')

            # Handle plain text files
            elif mime_type.startswith('text/') or mime_type == 'application/json':
                request = service.files().get_media(fileId=file_id)
                content_bytes = io.BytesIO()
                downloader = MediaIoBaseDownload(content_bytes, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                content = content_bytes.getvalue().decode('utf-8')

            else:
                return ReadDriveFileResult(
                    success=False,
                    file_id=file_id,
                    file_name=file_name,
                    mime_type=mime_type,
                    message=f"Unsupported file type: {mime_type}. Only text files and Google Docs are supported."
                )

            return ReadDriveFileResult(
                success=True,
                file_id=file_id,
                file_name=file_name,
                mime_type=mime_type,
                content=content[:10000],  # Limit to 10k chars
                message=f"✅ Read {len(content)} characters from '{file_name}'"
            )

        except Exception as e:
            return ReadDriveFileResult(
                success=False,
                file_id=file_id,
                message=f"Failed to read file: {str(e)}"
            )


class SearchDriveFilesResult(BaseModel):
    """Result of searching Drive files."""
    success: bool
    files: list[DriveFile] = []
    count: int
    query: str
    message: str


class SearchDriveFilesTool(Tool):
    """Tool for searching files in Google Drive."""

    @property
    def name(self) -> str:
        return "search_drive_files"

    @property
    def description(self) -> str:
        return "search for files in Google Drive by name, content, or type"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "search_term",
                "type": "string",
                "description": "term to search for in file names and content",
                "required": True,
            },
            {
                "name": "max_results",
                "type": "integer",
                "description": "maximum number of results (default: 10)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> SearchDriveFilesResult:
        """
        Search for files in Drive.

        Args:
            search_term: Term to search for
            max_results: Maximum results (default 10)

        Returns:
            SearchDriveFilesResult with matching files
        """
        search_term = kwargs.get("search_term", "").strip()
        max_results = kwargs.get("max_results", 10)

        if not search_term:
            raise ValueError("Search term is required")

        credentials = load_credentials()
        if not credentials:
            return SearchDriveFilesResult(
                success=False,
                count=0,
                query=search_term,
                message="Google Drive is not connected. Please connect your Google account first."
            )

        try:
            service = build("drive", "v3", credentials=credentials, cache_discovery=False)

            # Build search query - search in name and full text
            query = f"(name contains '{search_term}' or fullText contains '{search_term}') and trashed=false"

            results = service.files().list(
                pageSize=max_results,
                q=query,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)",
                orderBy="modifiedTime desc"
            ).execute()

            files = results.get('files', [])

            drive_files = []
            for file in files:
                is_folder = file['mimeType'] == 'application/vnd.google-apps.folder'
                size = file.get('size', 'N/A') if not is_folder else None

                drive_files.append(DriveFile(
                    id=file['id'],
                    name=file['name'],
                    mime_type=file['mimeType'],
                    created_time=file['createdTime'],
                    modified_time=file['modifiedTime'],
                    size=size,
                    web_view_link=file.get('webViewLink'),
                    is_folder=is_folder
                ))

            return SearchDriveFilesResult(
                success=True,
                files=drive_files,
                count=len(drive_files),
                query=search_term,
                message=f"Found {len(drive_files)} file(s) matching '{search_term}'"
            )

        except Exception as e:
            return SearchDriveFilesResult(
                success=False,
                count=0,
                query=search_term,
                message=f"Failed to search Drive: {str(e)}"
            )


class CreateDocResult(BaseModel):
    """Result of creating a Google Doc."""
    success: bool
    doc_id: str | None = None
    doc_url: str | None = None
    title: str | None = None
    message: str


class CreateGoogleDocTool(Tool):
    """Tool for creating new Google Docs."""

    @property
    def name(self) -> str:
        return "create_google_doc"

    @property
    def description(self) -> str:
        return "create a new Google Doc with specified title and content"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "title",
                "type": "string",
                "description": "title of the new document",
                "required": True,
            },
            {
                "name": "content",
                "type": "string",
                "description": "initial content for the document (optional)",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> CreateDocResult:
        """
        Create a new Google Doc.

        Args:
            title: Document title
            content: Initial content (optional)

        Returns:
            CreateDocResult with new document details
        """
        title = kwargs.get("title", "").strip()
        content = kwargs.get("content", "")

        if not title:
            raise ValueError("Document title is required")

        credentials = load_credentials()
        if not credentials:
            return CreateDocResult(
                success=False,
                message="Google Docs is not connected. Please connect your Google account first."
            )

        try:
            # Create the document
            docs_service = build("docs", "v1", credentials=credentials, cache_discovery=False)

            doc = docs_service.documents().create(body={'title': title}).execute()
            doc_id = doc['documentId']

            # Add content if provided
            if content:
                requests = [
                    {
                        'insertText': {
                            'location': {'index': 1},
                            'text': content
                        }
                    }
                ]
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()

            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

            return CreateDocResult(
                success=True,
                doc_id=doc_id,
                doc_url=doc_url,
                title=title,
                message=f"✅ Created Google Doc '{title}': {doc_url}"
            )

        except Exception as e:
            return CreateDocResult(
                success=False,
                message=f"Failed to create document: {str(e)}"
            )


class UpdateDocResult(BaseModel):
    """Result of updating a Google Doc."""
    success: bool
    doc_id: str | None = None
    doc_url: str | None = None
    message: str


class UpdateGoogleDocTool(Tool):
    """Tool for updating/editing existing Google Docs."""

    @property
    def name(self) -> str:
        return "update_google_doc"

    @property
    def description(self) -> str:
        return "update or edit an existing Google Doc by appending, replacing, or inserting text"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "doc_id",
                "type": "string",
                "description": "the ID of the document to update (get from list_drive_files or search)",
                "required": True,
            },
            {
                "name": "action",
                "type": "string",
                "description": "update action: 'append' (add to end), 'prepend' (add to beginning), or 'replace_all' (replace entire content)",
                "required": True,
            },
            {
                "name": "text",
                "type": "string",
                "description": "text content to add or replace with",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> UpdateDocResult:
        """
        Update a Google Doc.

        Args:
            doc_id: Document ID
            action: 'append', 'prepend', or 'replace_all'
            text: Text to add/replace

        Returns:
            UpdateDocResult with status
        """
        doc_id = kwargs.get("doc_id", "").strip()
        action = kwargs.get("action", "").strip().lower()
        text = kwargs.get("text", "")

        if not doc_id:
            raise ValueError("Document ID is required")
        if not action:
            raise ValueError("Action is required")
        if not text:
            raise ValueError("Text content is required")
        if action not in ["append", "prepend", "replace_all"]:
            raise ValueError("Action must be 'append', 'prepend', or 'replace_all'")

        credentials = load_credentials()
        if not credentials:
            return UpdateDocResult(
                success=False,
                message="Google Docs is not connected. Please connect your Google account first."
            )

        try:
            docs_service = build("docs", "v1", credentials=credentials, cache_discovery=False)

            # Get current document to find the end index
            doc = docs_service.documents().get(documentId=doc_id).execute()
            doc_title = doc.get('title', 'Untitled')
            content_end_index = doc.get('body', {}).get('content', [{}])[-1].get('endIndex', 1)

            requests = []

            if action == "append":
                # Insert text at the end
                requests.append({
                    'insertText': {
                        'location': {'index': content_end_index - 1},
                        'text': "\n" + text
                    }
                })

            elif action == "prepend":
                # Insert text at the beginning
                requests.append({
                    'insertText': {
                        'location': {'index': 1},
                        'text': text + "\n"
                    }
                })

            elif action == "replace_all":
                # Delete all content, then insert new text
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': content_end_index - 1
                        }
                    }
                })
                requests.append({
                    'insertText': {
                        'location': {'index': 1},
                        'text': text
                    }
                })

            # Execute the update
            docs_service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()

            doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

            action_msg = {
                "append": "appended to",
                "prepend": "prepended to",
                "replace_all": "replaced content in"
            }

            return UpdateDocResult(
                success=True,
                doc_id=doc_id,
                doc_url=doc_url,
                message=f"✅ Successfully {action_msg[action]} '{doc_title}': {doc_url}"
            )

        except Exception as e:
            return UpdateDocResult(
                success=False,
                doc_id=doc_id,
                message=f"Failed to update document: {str(e)}"
            )
