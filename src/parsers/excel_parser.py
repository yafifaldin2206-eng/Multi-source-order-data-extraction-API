"""
Excel Parser
Handles messy Excel/CSV files with fuzzy header detection and column mapping.

Features:
- Detects actual header row even if not on row 1
- Fuzzy column name mapping (e.g. "nama customer" → customer)
- Handles merged cells, empty rows, trailing whitespace
- Supports .xlsx, .xls, .csv via openpyxl / pandas
"""

import io
import re
from typing import Dict, List, Optional, Any, Tuple

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


# Column name alias map — add more as needed
COLUMN_ALIASES = {
    "customer": [
        "customer", "nama", "name", "pelanggan", "pembeli", "buyer",
        "nama customer", "customer name", "nama pelanggan", "nama_pelanggan",
        "customer_name", "nama pembeli"
    ],
    "product": [
        "product", "produk", "item", "barang", "menu", "nama produk",
        "product name", "nama_produk", "nama barang", "item_name"
    ],
    "quantity": [
        "quantity", "qty", "jumlah", "banyak", "amount", "qnty",
        "jumlah_order", "jumlah order", "total_qty"
    ],
    "unit": [
        "unit", "satuan", "uom", "unit of measure", "units"
    ],
    "date": [
        "date", "tanggal", "tgl", "order date", "tanggal_order",
        "delivery_date", "tanggal pesan", "delivery date", "tgl order"
    ],
    "price": [
        "price", "harga", "cost", "total", "harga satuan", "harga_satuan",
        "total_price", "total harga"
    ],
    "notes": [
        "notes", "catatan", "keterangan", "note", "remarks", "comment", "info"
    ]
}


class ExcelParser:
    def __init__(self):
        self._alias_map = self._build_alias_map()

    def _build_alias_map(self) -> Dict[str, str]:
        """Build reverse lookup: alias → canonical field name"""
        result = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                result[alias.lower().strip()] = canonical
        return result

    async def parse(self, data: bytes, options: Dict = {}) -> Dict:
        """Parse Excel or CSV bytes into IR"""
        if not isinstance(data, bytes) or len(data) == 0:
            raise ValueError("No file data received")

        filename = options.get("filename", "file.xlsx").lower()

        if filename.endswith(".csv"):
            return await self._parse_csv_bytes(data, options)
        else:
            return await self._parse_excel_bytes(data, options)

    async def _parse_excel_bytes(self, data: bytes, options: Dict) -> Dict:
        """Parse .xlsx file bytes"""
        if not OPENPYXL_AVAILABLE:
            raise RuntimeError("openpyxl not installed. Run: pip install openpyxl")

        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        ws = wb.active

        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append([self._clean_cell(c) for c in row])

        return self._process_rows(rows, options)

    async def _parse_csv_bytes(self, data: bytes, options: Dict) -> Dict:
        """Parse .csv bytes"""
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")

        lines = text.strip().split('\n')
        rows = []
        for line in lines:
            cells = [self._clean_cell(c) for c in line.split(',')]
            rows.append(cells)

        return self._process_rows(rows, options)

    def _process_rows(self, rows: List[List], options: Dict) -> Dict:
        """Common processing: detect headers, map columns, extract IR"""
        if not rows:
            return {"raw_orders": [], "source_meta": {"parser": "excel", "rows_processed": 0}}

        # Detect which row is the actual header
        header_idx, column_map = self._detect_headers(rows)

        if header_idx is None:
            return {
                "raw_orders": [],
                "source_meta": {
                    "parser": "excel",
                    "rows_processed": len(rows),
                    "warning": "Could not detect header row"
                }
            }

        raw_orders = []
        data_rows = rows[header_idx + 1:]

        for row_idx, row in enumerate(data_rows):
            if all(v is None or v == "" for v in row):
                continue  # skip empty rows

            order = {}
            for col_idx, canonical_field in column_map.items():
                if col_idx < len(row):
                    value = row[col_idx]
                    if value not in (None, ""):
                        order[canonical_field] = str(value).strip()

            if order:
                order["_row"] = row_idx + header_idx + 2  # 1-indexed excel row
                raw_orders.append(order)

        return {
            "raw_orders": raw_orders,
            "source_meta": {
                "parser": "excel",
                "header_row": header_idx + 1,
                "column_map": {str(k): v for k, v in column_map.items()},
                "rows_processed": len(data_rows),
                "orders_extracted": len(raw_orders)
            }
        }

    def _detect_headers(self, rows: List[List]) -> Tuple[Optional[int], Dict[int, str]]:
        """
        Find the row most likely to be the header.
        Returns: (header_row_index, {col_index: canonical_field})
        """
        best_score = 0
        best_idx = None
        best_map = {}

        # Search first 10 rows for header
        search_limit = min(10, len(rows))

        for row_idx in range(search_limit):
            row = rows[row_idx]
            col_map = {}
            score = 0

            for col_idx, cell in enumerate(row):
                if not cell:
                    continue
                canonical = self._resolve_column(str(cell))
                if canonical:
                    col_map[col_idx] = canonical
                    score += 1

            if score > best_score:
                best_score = score
                best_idx = row_idx
                best_map = col_map

        if best_score == 0:
            return None, {}

        return best_idx, best_map

    def _resolve_column(self, header_text: str) -> Optional[str]:
        """Map a raw column header to a canonical field name"""
        normalized = header_text.lower().strip()
        normalized = re.sub(r'[\s_\-/]+', ' ', normalized)  # normalize separators

        # Exact match
        if normalized in self._alias_map:
            return self._alias_map[normalized]

        # Partial match (header contains alias)
        for alias, canonical in self._alias_map.items():
            if alias in normalized or normalized in alias:
                return canonical

        return None

    def _clean_cell(self, value: Any) -> Optional[str]:
        """Clean a single cell value"""
        if value is None:
            return None
        text = str(value).strip()
        # Remove zero-width spaces, tabs
        text = re.sub(r'[\u200b\u200c\u200d\t]', '', text)
        return text if text else None
