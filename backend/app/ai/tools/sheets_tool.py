"""Google Sheets tools - allows the agent to read and write Google Sheets."""

from typing import Any
from pydantic import BaseModel

from app.ai.tools.base import Tool, ToolParameter
from app.google.oauth import load_credentials
from googleapiclient.discovery import build


class ReadSheetResult(BaseModel):
    """Result of reading sheet data."""
    success: bool
    spreadsheet_id: str | None = None
    spreadsheet_name: str | None = None
    range: str | None = None
    values: list[list[Any]] = []
    row_count: int = 0
    message: str


class ReadGoogleSheetTool(Tool):
    """Tool for reading data from Google Sheets."""

    @property
    def name(self) -> str:
        return "read_google_sheet"

    @property
    def description(self) -> str:
        return "read data from a Google Sheet by spreadsheet ID and range"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "spreadsheet_id",
                "type": "string",
                "description": "the ID of the spreadsheet (from URL or search_drive_files)",
                "required": True,
            },
            {
                "name": "range",
                "type": "string",
                "description": "range to read in A1 notation (e.g., 'Sheet1!A1:D10', 'Sheet1!A:A'). Default: 'Sheet1'",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> ReadSheetResult:
        """
        Read data from a Google Sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range: Range in A1 notation (default: 'Sheet1')

        Returns:
            ReadSheetResult with sheet data
        """
        spreadsheet_id = kwargs.get("spreadsheet_id", "").strip()
        range_name = kwargs.get("range", "Sheet1").strip()

        if not spreadsheet_id:
            raise ValueError("Spreadsheet ID is required")

        credentials = load_credentials()
        if not credentials:
            return ReadSheetResult(
                success=False,
                message="Google Sheets is not connected. Please connect your Google account first."
            )

        try:
            service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

            # Get spreadsheet metadata
            sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            sheet_name = sheet_metadata.get('properties', {}).get('title', 'Untitled')

            # Read the values
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])

            return ReadSheetResult(
                success=True,
                spreadsheet_id=spreadsheet_id,
                spreadsheet_name=sheet_name,
                range=range_name,
                values=values,
                row_count=len(values),
                message=f"✅ Read {len(values)} row(s) from '{sheet_name}' range {range_name}"
            )

        except Exception as e:
            return ReadSheetResult(
                success=False,
                spreadsheet_id=spreadsheet_id,
                message=f"Failed to read sheet: {str(e)}"
            )


class CreateSheetResult(BaseModel):
    """Result of creating a spreadsheet."""
    success: bool
    spreadsheet_id: str | None = None
    spreadsheet_url: str | None = None
    title: str | None = None
    message: str


class CreateGoogleSheetTool(Tool):
    """Tool for creating new Google Sheets."""

    @property
    def name(self) -> str:
        return "create_google_sheet"

    @property
    def description(self) -> str:
        return "create a new Google Sheet with optional initial data"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "title",
                "type": "string",
                "description": "title of the new spreadsheet",
                "required": True,
            },
            {
                "name": "sheet_name",
                "type": "string",
                "description": "name for the first sheet tab (default: 'Sheet1')",
                "required": False,
            },
        ]

    def execute(self, **kwargs) -> CreateSheetResult:
        """
        Create a new Google Sheet.

        Args:
            title: Spreadsheet title
            sheet_name: First sheet tab name (default 'Sheet1')

        Returns:
            CreateSheetResult with new spreadsheet details
        """
        title = kwargs.get("title", "").strip()
        sheet_name = kwargs.get("sheet_name", "Sheet1").strip()

        if not title:
            raise ValueError("Spreadsheet title is required")

        credentials = load_credentials()
        if not credentials:
            return CreateSheetResult(
                success=False,
                message="Google Sheets is not connected. Please connect your Google account first."
            )

        try:
            service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

            spreadsheet_body = {
                'properties': {'title': title},
                'sheets': [{'properties': {'title': sheet_name}}]
            }

            spreadsheet = service.spreadsheets().create(body=spreadsheet_body).execute()
            spreadsheet_id = spreadsheet['spreadsheetId']
            spreadsheet_url = spreadsheet['spreadsheetUrl']

            return CreateSheetResult(
                success=True,
                spreadsheet_id=spreadsheet_id,
                spreadsheet_url=spreadsheet_url,
                title=title,
                message=f"✅ Created Google Sheet '{title}': {spreadsheet_url}"
            )

        except Exception as e:
            return CreateSheetResult(
                success=False,
                message=f"Failed to create spreadsheet: {str(e)}"
            )


class UpdateSheetResult(BaseModel):
    """Result of updating sheet data."""
    success: bool
    spreadsheet_id: str | None = None
    range: str | None = None
    updated_cells: int = 0
    message: str


class UpdateGoogleSheetTool(Tool):
    """Tool for updating data in Google Sheets."""

    @property
    def name(self) -> str:
        return "update_google_sheet"

    @property
    def description(self) -> str:
        return "update or write data to a Google Sheet at a specific range"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "spreadsheet_id",
                "type": "string",
                "description": "the ID of the spreadsheet",
                "required": True,
            },
            {
                "name": "range",
                "type": "string",
                "description": "range to update in A1 notation (e.g., 'Sheet1!A1:B2')",
                "required": True,
            },
            {
                "name": "values",
                "type": "string",
                "description": "data as JSON array of arrays (e.g., '[[\"Name\", \"Age\"], [\"John\", 30]]')",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> UpdateSheetResult:
        """
        Update data in a Google Sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range: Range in A1 notation
            values: Data as JSON string (array of arrays)

        Returns:
            UpdateSheetResult with update status
        """
        import json

        spreadsheet_id = kwargs.get("spreadsheet_id", "").strip()
        range_name = kwargs.get("range", "").strip()
        values_str = kwargs.get("values", "").strip()

        if not spreadsheet_id:
            raise ValueError("Spreadsheet ID is required")
        if not range_name:
            raise ValueError("Range is required")
        if not values_str:
            raise ValueError("Values are required")

        credentials = load_credentials()
        if not credentials:
            return UpdateSheetResult(
                success=False,
                message="Google Sheets is not connected. Please connect your Google account first."
            )

        try:
            # Parse values JSON
            values = json.loads(values_str)
            if not isinstance(values, list):
                raise ValueError("Values must be a JSON array")

            service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

            body = {'values': values}

            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            updated_cells = result.get('updatedCells', 0)

            return UpdateSheetResult(
                success=True,
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                updated_cells=updated_cells,
                message=f"✅ Updated {updated_cells} cell(s) in range {range_name}"
            )

        except json.JSONDecodeError:
            return UpdateSheetResult(
                success=False,
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                message="Invalid JSON format for values. Use format: [[\"col1\", \"col2\"], [\"val1\", \"val2\"]]"
            )
        except Exception as e:
            return UpdateSheetResult(
                success=False,
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                message=f"Failed to update sheet: {str(e)}"
            )


class AppendSheetResult(BaseModel):
    """Result of appending data to sheet."""
    success: bool
    spreadsheet_id: str | None = None
    range: str | None = None
    updated_range: str | None = None
    updated_rows: int = 0
    message: str


class AppendGoogleSheetTool(Tool):
    """Tool for appending rows to Google Sheets."""

    @property
    def name(self) -> str:
        return "append_google_sheet"

    @property
    def description(self) -> str:
        return "append new rows to the end of a Google Sheet"

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            {
                "name": "spreadsheet_id",
                "type": "string",
                "description": "the ID of the spreadsheet",
                "required": True,
            },
            {
                "name": "range",
                "type": "string",
                "description": "range to append to (e.g., 'Sheet1!A:C'). Data will be added to next empty row.",
                "required": True,
            },
            {
                "name": "values",
                "type": "string",
                "description": "rows to append as JSON array (e.g., '[[\"John\", 30, \"Engineer\"]]')",
                "required": True,
            },
        ]

    def execute(self, **kwargs) -> AppendSheetResult:
        """
        Append rows to a Google Sheet.

        Args:
            spreadsheet_id: The spreadsheet ID
            range: Range to append to
            values: Rows as JSON string (array of arrays)

        Returns:
            AppendSheetResult with append status
        """
        import json

        spreadsheet_id = kwargs.get("spreadsheet_id", "").strip()
        range_name = kwargs.get("range", "").strip()
        values_str = kwargs.get("values", "").strip()

        if not spreadsheet_id:
            raise ValueError("Spreadsheet ID is required")
        if not range_name:
            raise ValueError("Range is required")
        if not values_str:
            raise ValueError("Values are required")

        credentials = load_credentials()
        if not credentials:
            return AppendSheetResult(
                success=False,
                message="Google Sheets is not connected. Please connect your Google account first."
            )

        try:
            # Parse values JSON
            values = json.loads(values_str)
            if not isinstance(values, list):
                raise ValueError("Values must be a JSON array")

            service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

            body = {'values': values}

            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()

            updated_range = result.get('updates', {}).get('updatedRange', '')
            updated_rows = result.get('updates', {}).get('updatedRows', 0)

            return AppendSheetResult(
                success=True,
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                updated_range=updated_range,
                updated_rows=updated_rows,
                message=f"✅ Appended {updated_rows} row(s) to {updated_range}"
            )

        except json.JSONDecodeError:
            return AppendSheetResult(
                success=False,
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                message="Invalid JSON format for values. Use format: [[\"val1\", \"val2\", \"val3\"]]"
            )
        except Exception as e:
            return AppendSheetResult(
                success=False,
                spreadsheet_id=spreadsheet_id,
                range=range_name,
                message=f"Failed to append to sheet: {str(e)}"
            )
