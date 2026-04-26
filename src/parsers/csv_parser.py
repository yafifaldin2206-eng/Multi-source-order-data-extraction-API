"""
CSV Text Parser
Handles inline CSV content passed as a string (not a file).
"""

from src.parsers.excel_parser import ExcelParser


class CSVParser:
    def __init__(self):
        self._excel_parser = ExcelParser()

    async def parse(self, data: str, options: dict = {}) -> dict:
        """Parse inline CSV string into IR"""
        if not isinstance(data, str):
            raise ValueError("CSV text parser expects a string")

        # Encode string to bytes and delegate to ExcelParser's CSV handler
        csv_bytes = data.encode("utf-8")
        opts = {**options, "filename": "inline.csv"}
        return await self._excel_parser.parse(csv_bytes, opts)
