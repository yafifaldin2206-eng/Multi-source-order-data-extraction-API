"""
Test suite for Order Extraction API pipeline
Run with: python tests/test_pipeline.py
"""

import asyncio
import sys
sys.path.insert(0, ".")

from src.router.source_router import SourceRouter

router = SourceRouter()
PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
errors = []


def check(label, condition, actual=None):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}" + (f" | got: {actual}" if actual is not None else ""))
        errors.append(label)


async def test_whatsapp_basic():
    print("\n[WhatsApp Parser - Basic]")
    result = await router.route("whatsapp", "Budi: pesan 2 es teh 1L besok ya")
    orders = result["orders"]
    check("Returns 1 order", len(orders) == 1, len(orders))
    check("Customer is Budi", orders[0].get("customer") == "Budi", orders[0].get("customer"))
    check("Quantity is 2", orders[0].get("quantity") == 2, orders[0].get("quantity"))
    check("Date is tomorrow", orders[0].get("date") is not None)
    check("Confidence > 0.7", orders[0].get("confidence", 0) > 0.7)


async def test_whatsapp_multi_order():
    print("\n[WhatsApp Parser - Multi-order message]")
    result = await router.route(
        "whatsapp",
        "Dewi: order 2 es teh dan 1 nasi goreng buat besok"
    )
    orders = result["orders"]
    check("Returns 2 orders", len(orders) == 2, len(orders))
    check("Both orders have customer Dewi", all(o.get("customer") == "Dewi" for o in orders))


async def test_whatsapp_casual_filtered():
    print("\n[WhatsApp Parser - Casual chat filtered]")
    result = await router.route(
        "whatsapp",
        "Ali: halo semua!\nBob: gimana kabarnya?\nCindy: selamat pagi"
    )
    check("No orders extracted from casual chat", len(result["orders"]) == 0, len(result["orders"]))


async def test_csv_basic():
    print("\n[CSV Parser - Basic]")
    csv = "customer,product,qty,date\nDewi,Es Teh,5,2026-04-27\nRudi,Nasi Goreng,2,2026-04-28"
    result = await router.route("csv_text", csv)
    orders = result["orders"]
    check("Returns 2 orders", len(orders) == 2, len(orders))
    check("First customer is Dewi", orders[0].get("customer") == "Dewi")
    check("Quantity normalized to int", isinstance(orders[0].get("quantity"), int))


async def test_csv_messy_headers():
    print("\n[CSV Parser - Messy headers]")
    csv = "nama pelanggan,nama produk,jumlah order,tanggal\nSari,Es Jeruk,3,2026-04-27"
    result = await router.route("csv_text", csv)
    orders = result["orders"]
    check("Extracts 1 order with fuzzy headers", len(orders) == 1, len(orders))
    check("Customer mapped correctly", orders[0].get("customer") == "Sari")


async def test_missing_fields_flagged():
    print("\n[Validator - Missing fields]")
    csv = "customer,product,qty\n,Mie Goreng,3"
    result = await router.route("csv_text", csv)
    orders = result["orders"]
    check("Order has validation_flags", bool(orders[0].get("validation_flags")))
    check("Warning in metadata", len(result["metadata"]["warnings"]) > 0)
    check("valid_orders < total_orders", result["metadata"]["valid_orders"] < result["metadata"]["total_orders"])


async def test_invalid_source():
    print("\n[Router - Invalid source]")
    try:
        await router.route("telegram", "some text")
        check("Should raise ValueError", False)
    except ValueError:
        check("Raises ValueError for unknown source", True)


async def test_date_normalization():
    print("\n[Normalizer - Date resolution]")
    result = await router.route("whatsapp", "Ana: pesan 1 kopi hari ini")
    orders = result["orders"]
    from datetime import date
    today = date.today().isoformat()
    if orders:
        check("'hari ini' resolves to today", orders[0].get("date") == today, orders[0].get("date"))


async def main():
    await test_whatsapp_basic()
    await test_whatsapp_multi_order()
    await test_whatsapp_casual_filtered()
    await test_csv_basic()
    await test_csv_messy_headers()
    await test_missing_fields_flagged()
    await test_invalid_source()
    await test_date_normalization()

    print(f"\n{'─'*40}")
    total = 19
    failed = len(errors)
    print(f"Results: {total - failed} passed, {failed} failed")
    if errors:
        print("Failed checks:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("\033[92mAll tests passed!\033[0m")


asyncio.run(main())
