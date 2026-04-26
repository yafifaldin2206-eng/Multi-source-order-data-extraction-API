"""
Output Formatter
Shapes validated orders into the final API response structure.
Strips internal fields (_valid, _raw, etc.) from output.
"""

from typing import Dict, List, Optional


class OutputFormatter:
    def format(self, validated: Dict, source: str) -> Dict:
        """Format validated output into clean API response"""
        orders_raw = validated.get("orders", [])
        summary = validated.get("summary", {})

        # Build clean order list (strip internal fields)
        orders = []
        for o in orders_raw:
            clean = {
                k: v for k, v in o.items()
                if not k.startswith("_") and v is not None
            }
            orders.append(clean)

        # Compute overall confidence
        overall_confidence = summary.get("avg_confidence", 0.0)
        if overall_confidence == 0.0 and orders:
            scores = [o.get("confidence", 0) for o in orders]
            overall_confidence = round(sum(scores) / len(scores), 3) if scores else 0.0

        # Build warnings list
        warnings = list(summary.get("warnings", []))

        # Add per-order warnings to global list if notable
        for o in orders_raw:
            flags = o.get("validation_flags") or []
            for flag in flags:
                msg = self._flag_to_message(flag, o)
                if msg and msg not in warnings:
                    warnings.append(msg)

        return {
            "orders": orders,
            "metadata": {
                "source": source,
                "confidence": overall_confidence,
                "total_orders": summary.get("total", len(orders)),
                "valid_orders": summary.get("valid", len(orders)),
                "warnings": warnings,
            }
        }

    def _flag_to_message(self, flag: str, order: Dict) -> Optional[str]:
        customer = order.get("customer", "unknown")
        product = order.get("product", "unknown item")

        if flag.startswith("missing_fields:"):
            fields = flag.split(":")[1]
            return f"Order for '{customer}' missing: {fields}"
        if flag == "possible_duplicate":
            return f"Possible duplicate order: {customer} → {product}"
        if flag == "quantity_suspiciously_high":
            return f"Unusually high quantity for '{product}' (qty={order.get('quantity')})"
        if flag == "quantity_too_low":
            return f"Suspicious quantity (< 1) for '{product}'"
        return None
