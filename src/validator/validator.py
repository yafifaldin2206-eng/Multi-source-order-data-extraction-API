"""
Validator
Checks normalized orders for:
- Missing required fields
- Inconsistent/suspicious values
- Duplicates
- Assigns confidence score per order
"""

from typing import Dict, List, Optional
import hashlib
import json


REQUIRED_FIELDS = ["customer", "product", "quantity"]
OPTIONAL_FIELDS = ["unit", "date", "price", "notes"]

# Confidence weights
FIELD_WEIGHTS = {
    "customer": 0.25,
    "product": 0.30,
    "quantity": 0.25,
    "date": 0.10,
    "unit": 0.05,
    "price": 0.05,
}

MAX_REASONABLE_QUANTITY = 10_000
MIN_REASONABLE_QUANTITY = 1


class Validator:
    def validate(self, normalized: Dict) -> Dict:
        """Validate all orders and annotate with flags + confidence"""
        orders = normalized.get("orders", [])
        source_meta = normalized.get("source_meta", {})

        seen_hashes = set()
        validated_orders = []
        global_warnings = []

        for order in orders:
            result = self._validate_order(order, seen_hashes)
            validated_orders.append(result)

        valid_count = sum(1 for o in validated_orders if o.get("_valid", False))
        avg_confidence = (
            sum(o.get("confidence", 0) for o in validated_orders) / len(validated_orders)
            if validated_orders else 0
        )

        # Global warnings
        if valid_count == 0 and len(orders) > 0:
            global_warnings.append("No valid orders could be extracted from input")

        return {
            "orders": validated_orders,
            "source_meta": source_meta,
            "summary": {
                "total": len(orders),
                "valid": valid_count,
                "avg_confidence": round(avg_confidence, 3),
                "warnings": global_warnings
            }
        }

    def _validate_order(self, order: Dict, seen_hashes: set) -> Dict:
        """Validate a single order, return annotated copy"""
        flags = []
        confidence_score = 0.0

        # Check required fields
        missing = []
        for field in REQUIRED_FIELDS:
            if not order.get(field):
                missing.append(field)

        if missing:
            flags.append(f"missing_fields:{','.join(missing)}")

        # Field-by-field confidence accumulation
        for field, weight in FIELD_WEIGHTS.items():
            value = order.get(field)
            if value is not None:
                field_conf = self._score_field(field, value)
                confidence_score += weight * field_conf

        # Quantity sanity check
        qty = order.get("quantity")
        if qty is not None:
            if qty < MIN_REASONABLE_QUANTITY:
                flags.append("quantity_too_low")
                confidence_score *= 0.7
            elif qty > MAX_REASONABLE_QUANTITY:
                flags.append("quantity_suspiciously_high")
                confidence_score *= 0.8

        # Duplicate detection
        dedup_key = {
            "customer": order.get("customer"),
            "product": order.get("product"),
            "quantity": order.get("quantity"),
            "date": order.get("date"),
        }
        key_hash = hashlib.md5(json.dumps(dedup_key, sort_keys=True).encode()).hexdigest()

        if key_hash in seen_hashes:
            flags.append("possible_duplicate")
            confidence_score *= 0.6
        else:
            seen_hashes.add(key_hash)

        # Final valid determination
        is_valid = len(missing) == 0

        return {
            "customer": order.get("customer"),
            "product": order.get("product"),
            "quantity": order.get("quantity"),
            "unit": order.get("unit"),
            "date": order.get("date"),
            "price": order.get("price"),
            "notes": order.get("notes"),
            "confidence": round(min(confidence_score, 1.0), 3),
            "validation_flags": flags if flags else None,
            "_valid": is_valid,
        }

    def _score_field(self, field: str, value) -> float:
        """Score the quality of a specific field value (0–1)"""
        if value is None:
            return 0.0

        if field == "quantity":
            if isinstance(value, int) and MIN_REASONABLE_QUANTITY <= value <= 100:
                return 1.0
            elif isinstance(value, int):
                return 0.7
            return 0.4

        if field == "date":
            # Full ISO date is best
            import re
            if re.match(r'^\d{4}-\d{2}-\d{2}$', str(value)):
                return 1.0
            return 0.5

        if field in ("customer", "product"):
            text = str(value)
            if len(text) >= 3:
                return 1.0
            elif len(text) >= 1:
                return 0.6
            return 0.2

        # Default: present = full score
        return 1.0 if value else 0.0
