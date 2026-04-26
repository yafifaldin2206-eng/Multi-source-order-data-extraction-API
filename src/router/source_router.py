"""
Source Router
Dispatches incoming data to the correct parser based on source type.
Modular design: adding new sources only requires registering a new parser here.
"""

from typing import Any, Dict
from src.parsers.whatsapp_parser import WhatsAppParser
from src.parsers.excel_parser import ExcelParser
from src.parsers.csv_parser import CSVParser
from src.normalizer.normalizer import Normalizer
from src.validator.validator import Validator
from src.formatter.formatter import OutputFormatter


class SourceRouter:
    def __init__(self):
        # Registry of all supported parsers
        # To add a new source: just add it here
        self._parsers = {
            "whatsapp": WhatsAppParser(),
            "excel": ExcelParser(),
            "csv": ExcelParser(),       # Excel parser handles CSV files too
            "csv_text": CSVParser(),    # Inline CSV text
        }

        self._normalizer = Normalizer()
        self._validator = Validator()
        self._formatter = OutputFormatter()

    async def route(self, source: str, data: Any, options: Dict = {}) -> Dict:
        """
        Full pipeline execution:
        Input → Parser → IR → Normalizer → Validator → Formatter → Output
        """
        source = source.lower().strip()

        if source not in self._parsers:
            supported = list(self._parsers.keys())
            raise ValueError(
                f"Unsupported source: '{source}'. Supported sources: {supported}"
            )

        # Step 1: Parse into Intermediate Representation (IR)
        parser = self._parsers[source]
        ir = await parser.parse(data, options)

        # Step 2: Normalize IR into clean structured data
        normalized = self._normalizer.normalize(ir, source)

        # Step 3: Validate normalized orders
        validated = self._validator.validate(normalized)

        # Step 4: Format final response
        output = self._formatter.format(validated, source)

        return output
