"""
Normalizer
Converts raw Intermediate Representation (IR) into clean, typed, standardized values.

Responsibilities:
- Quantity: "2" → 2 (int), "dua" → 2
- Time: "besok" → "2026-04-27", "today" → "2026-04-26"
- Product: normalize product names
- Customer: clean name formatting
"""

import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Any


# Indonesian word-to-number map
WORD_NUMBERS = {
    "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
    "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
    "sebelas": 11, "dua belas": 12, "selusin": 12,
    "setengah": 0.5, "seperempat": 0.25,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

WEEKDAYS = {
    "monday": 0, "senin": 0,
    "tuesday": 1, "selasa": 1,
    "wednesday": 2, "rabu": 2,
    "thursday": 3, "kamis": 3,
    "friday": 4, "jumat": 4,
    "saturday": 5, "sabtu": 5,
    "sunday": 6, "minggu": 6,
}

# Product name normalization (add your catalog here)
PRODUCT_CATALOG = {
    "es teh": "Es Teh",
    "es the": "Es Teh",
    "ice tea": "Es Teh",
    "nasi goreng": "Nasi Goreng",
    "nasgor": "Nasi Goreng",
    "mie goreng": "Mie Goreng",
    "mi goreng": "Mie Goreng",
    "ayam goreng": "Ayam Goreng",
    "es jeruk": "Es Jeruk",
    "air mineral": "Air Mineral",
    "aqua": "Air Mineral",
    "kopi": "Kopi",
    "coffee": "Kopi",
}


class Normalizer:
    def normalize(self, ir: Dict, source: str) -> Dict:
        """Normalize all raw orders in the IR"""
        raw_orders = ir.get("raw_orders", [])
        normalized = []

        for raw in raw_orders:
            order = self._normalize_order(raw)
            normalized.append(order)

        return {
            "orders": normalized,
            "source_meta": ir.get("source_meta", {})
        }

    def _normalize_order(self, raw: Dict) -> Dict:
        """Normalize a single raw order fragment"""
        return {
            "customer": self._normalize_customer(raw.get("customer")),
            "product": self._normalize_product(raw.get("product")),
            "quantity": self._normalize_quantity(raw.get("quantity")),
            "unit": self._normalize_unit(raw.get("unit")),
            "date": self._normalize_date(raw.get("time") or raw.get("date")),
            "price": self._normalize_price(raw.get("price")),
            "notes": raw.get("notes"),
            "_raw": raw,
        }

    def _normalize_customer(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        # Title case, strip punctuation
        clean = re.sub(r'[^\w\s]', '', value).strip()
        return clean.title() if clean else None

    def _normalize_product(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        clean = value.lower().strip()
        # Remove filler words
        clean = re.sub(r'\b(ya|dong|deh|nih|tolong|boleh|mau|minta)\b', '', clean).strip()
        clean = re.sub(r'\s+', ' ', clean).strip()

        # Catalog lookup (partial match)
        for alias, canonical in PRODUCT_CATALOG.items():
            if alias in clean:
                # Preserve any size info (e.g. "1L", "500ml")
                size_match = re.search(r'(\d+\s*(?:ml|l|liter|gr|kg|g))', clean, re.IGNORECASE)
                size_suffix = f" {size_match.group(1).upper()}" if size_match else ""
                return canonical + size_suffix

        # Remove trailing time/filler phrases that leaked into product name
        trailing_time = re.compile(
            r'\b(buat|untuk|pada|di|tanggal|tgl|jam|pukul|hari ini|besok|lusa|nanti|sekarang'
            r'|buat hari ini|buat besok)\b.*$',
            re.IGNORECASE
        )
        clean = trailing_time.sub('', clean).strip()

        # Fallback: title case the cleaned text
        return clean.title() if clean else None

    def _normalize_quantity(self, value: Optional[str]) -> Optional[int]:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return int(value)

        text = str(value).lower().strip()

        # Direct numeric
        try:
            return int(float(text))
        except ValueError:
            pass

        # Word-based numbers (check multi-word first)
        for word, num in sorted(WORD_NUMBERS.items(), key=lambda x: -len(x[0])):
            if word in text:
                return int(num)

        # Extract first number found
        match = re.search(r'\d+(?:\.\d+)?', text)
        if match:
            return int(float(match.group()))

        return None

    def _normalize_unit(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        return value.lower().strip()

    def _normalize_date(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        today = date.today()
        v = value.lower().strip()

        if v in ("today", "now", "sekarang", "hari ini"):
            return today.isoformat()

        if v in ("tomorrow", "besok"):
            return (today + timedelta(days=1)).isoformat()

        if v in ("day_after_tomorrow", "lusa"):
            return (today + timedelta(days=2)).isoformat()

        if v == "next_week":
            return (today + timedelta(weeks=1)).isoformat()

        if v == "later":
            return None  # unresolvable

        # Weekday resolution
        if v in WEEKDAYS:
            target_weekday = WEEKDAYS[v]
            current_weekday = today.weekday()
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7  # next occurrence
            return (today + timedelta(days=days_ahead)).isoformat()

        # Explicit date string: "explicit:DD/MM/YYYY"
        if v.startswith("explicit:"):
            raw_date = v[9:]
            return self._parse_explicit_date(raw_date, today.year)

        # ISO or common date formats
        iso_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', v)
        if iso_match:
            return f"{iso_match.group(1)}-{int(iso_match.group(2)):02d}-{int(iso_match.group(3)):02d}"

        return None  # unresolvable date

    def _parse_explicit_date(self, raw: str, current_year: int) -> Optional[str]:
        """Parse DD/MM or DD/MM/YYYY into ISO format"""
        parts = re.split(r'[/-]', raw)
        try:
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2]) if len(parts) > 2 and parts[2] else current_year
            if year < 100:
                year += 2000
            return date(year, month, day).isoformat()
        except (ValueError, IndexError):
            return None

    def _normalize_price(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        # Remove currency symbols and thousand separators
        clean = re.sub(r'[Rp\s,.]', '', str(value))
        # Handle Indonesian "." as thousand separator
        try:
            return float(clean)
        except ValueError:
            return None
