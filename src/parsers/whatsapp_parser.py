"""
WhatsApp Parser
Extracts order intent from raw WhatsApp chat messages.

Pipeline:
1. Split raw chat into individual messages
2. Detect sender per message
3. Classify intent: order vs casual chat
4. Extract order fragments into IR format

Strategy: Rule-based first → LLM fallback for ambiguous cases
"""

import re
from typing import List, Dict, Any, Optional


# Indonesian order keywords (extend as needed)
ORDER_KEYWORDS = [
    "pesan", "order", "minta", "beli", "ambil", "pesen",
    "mau", "butuh", "request", "book", "booking"
]

# Common Indonesian units
UNIT_PATTERNS = {
    "liter": ["liter", "l", "lt"],
    "kilogram": ["kg", "kilo", "kilogram"],
    "gram": ["gram", "gr", "g"],
    "piece": ["pcs", "buah", "biji", "unit", "lembar"],
    "portion": ["porsi", "piring", "mangkok", "bungkus", "pak"],
    "bottle": ["botol", "bt"],
    "pack": ["pack", "pak", "sachet"],
    "box": ["box", "kotak", "dus"],
}

# Time expressions → will be resolved by normalizer
TIME_EXPRESSIONS = {
    "besok": "tomorrow",
    "lusa": "day_after_tomorrow",
    "hari ini": "today",
    "sekarang": "now",
    "nanti": "later",
    "minggu depan": "next_week",
    "senin": "monday",
    "selasa": "tuesday",
    "rabu": "wednesday",
    "kamis": "thursday",
    "jumat": "friday",
    "sabtu": "saturday",
    "minggu": "sunday",
}


class WhatsAppParser:
    def __init__(self):
        self._order_pattern = re.compile(
            r'\b(' + '|'.join(ORDER_KEYWORDS) + r')\b',
            re.IGNORECASE
        )
        self._quantity_pattern = re.compile(r'\b(\d+)\s*([a-zA-Z]*)\b')
        self._sender_pattern = re.compile(r'^([^:]+):\s*(.+)$')

    async def parse(self, data: str, options: Dict = {}) -> Dict:
        """Parse raw WhatsApp chat text into IR"""
        if not isinstance(data, str) or not data.strip():
            return {"raw_orders": [], "source_meta": {"parser": "whatsapp", "messages_processed": 0}}

        messages = self._split_messages(data)
        raw_orders = []

        for msg in messages:
            sender, text = self._extract_sender(msg)
            if not text:
                continue

            if not self._is_order_intent(text):
                continue

            fragments = self._extract_order_fragments(text, sender)
            raw_orders.extend(fragments)

        return {
            "raw_orders": raw_orders,
            "source_meta": {
                "parser": "whatsapp",
                "messages_processed": len(messages),
                "order_messages_found": len(raw_orders)
            }
        }

    def _split_messages(self, data: str) -> List[str]:
        """Split chat blob into individual messages"""
        lines = [line.strip() for line in data.strip().split('\n') if line.strip()]

        # Handle WhatsApp export format: [DD/MM/YY, HH:MM:SS] Name: message
        wa_export_pattern = re.compile(
            r'^\[?\d{1,2}/\d{1,2}/\d{2,4},?\s*\d{1,2}:\d{2}(?::\d{2})?\]?\s*-?\s*'
        )

        messages = []
        for line in lines:
            # Strip timestamp if present
            clean = wa_export_pattern.sub('', line).strip()
            if clean:
                messages.append(clean)

        return messages

    def _extract_sender(self, message: str) -> tuple[Optional[str], Optional[str]]:
        """Extract sender name and message content"""
        match = self._sender_pattern.match(message)
        if match:
            sender = match.group(1).strip()
            text = match.group(2).strip()
            # Skip system messages
            if sender.lower() in ['system', 'whatsapp', 'info']:
                return None, None
            return sender, text
        return None, message

    def _is_order_intent(self, text: str) -> bool:
        """Classify if a message contains order intent"""
        return bool(self._order_pattern.search(text))

    def _extract_order_fragments(self, text: str, sender: Optional[str]) -> List[Dict]:
        """Extract one or more order fragments from a single message"""
        fragments = []

        # Detect time expression in the full message
        time_raw = self._extract_time(text)

        # Split by conjunctions to handle multi-item orders
        # e.g. "pesan 2 es teh dan 1 nasi goreng"
        items = self._split_order_items(text)

        for item_text in items:
            qty, unit, product = self._extract_product_info(item_text)

            if product:
                fragment = {
                    "customer": sender,
                    "product": product,
                    "quantity": str(qty) if qty else None,
                    "unit": unit,
                    "time": time_raw,
                    "raw_text": item_text.strip()
                }
                fragments.append(fragment)

        # Fallback: if no products found but it was an order intent
        if not fragments:
            fragments.append({
                "customer": sender,
                "product": None,
                "quantity": None,
                "unit": None,
                "time": time_raw,
                "raw_text": text,
                "_extraction_note": "intent detected but product unclear"
            })

        return fragments

    def _split_order_items(self, text: str) -> List[str]:
        """Split a message into individual item texts"""
        # Split on conjunctions
        split_pattern = re.compile(r'\b(dan|sama|juga|,|;)\b', re.IGNORECASE)
        parts = split_pattern.split(text)
        # Filter out the separator tokens themselves
        items = [p.strip() for p in parts if p.strip() and not re.match(r'^(dan|sama|juga|,|;)$', p.strip(), re.IGNORECASE)]
        return items if items else [text]

    def _extract_product_info(self, text: str) -> tuple:
        """Extract quantity, unit, and product name from text fragment"""
        # Pattern: number [unit] product
        pattern = re.compile(
            r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\s+(.+)',
            re.IGNORECASE
        )

        # Remove order keywords to isolate product
        clean = self._order_pattern.sub('', text).strip()

        # Try to find quantity + product
        match = pattern.search(clean)
        if match:
            qty_str = match.group(1)
            possible_unit = match.group(2) or ""
            rest = match.group(3) or ""

            qty = float(qty_str) if '.' in qty_str else int(qty_str)
            unit = self._resolve_unit(possible_unit)

            if unit:
                product = rest.strip()
            else:
                product = (possible_unit + " " + rest).strip()
                unit = None

            return qty, unit, product if product else None

        # No quantity found — try to extract product only
        clean_no_keywords = self._order_pattern.sub('', clean).strip()
        # Remove common filler words
        fillers = re.compile(r'\b(ya|dong|deh|nih|kan|sih|yuk|aja|dulu|tolong|boleh)\b', re.IGNORECASE)
        product_text = fillers.sub('', clean_no_keywords).strip()

        return None, None, product_text if len(product_text) > 1 else None

    def _extract_time(self, text: str) -> Optional[str]:
        """Find time expression in text"""
        text_lower = text.lower()

        # Check multi-word first
        for expr, canonical in sorted(TIME_EXPRESSIONS.items(), key=lambda x: -len(x[0])):
            if expr in text_lower:
                return canonical

        # Check for explicit date patterns (DD/MM or DD-MM-YYYY)
        date_pattern = re.compile(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b')
        match = date_pattern.search(text)
        if match:
            day, month, year = match.group(1), match.group(2), match.group(3) or ""
            return f"explicit:{day}/{month}/{year}"

        return None

    def _resolve_unit(self, token: str) -> Optional[str]:
        """Resolve a token to a canonical unit name"""
        token_lower = token.lower().strip()
        for canonical, aliases in UNIT_PATTERNS.items():
            if token_lower in aliases:
                return canonical
        return None
