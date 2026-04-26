# Multi-source-order-data-extraction-API
An API that can take data from different sources (like WhatsApp chats or Excel files), understand the messy content, and turn it into clean, structured order data (like who bought what, how many, and when)

# Order Extraction API

Self-hosted semantic normalization pipeline for unstructured business order data.

## Quick Start

```bash
cd order-extraction-api
pip install -r requirements.txt
uvicorn main:app --reload
```

API runs at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

---

## Architecture

```
Input (WhatsApp / Excel / CSV)
  ↓
Source Router          → picks correct parser
  ↓
Parser                 → Intermediate Representation (IR)
  ↓
Normalizer             → typed, clean values
  ↓
Validator              → flags, confidence score
  ↓
Output Formatter       → final JSON response
```

---

## API Usage

### POST /extract/orders — WhatsApp chat

```bash
curl -X POST http://localhost:8000/extract/orders \
  -H "Content-Type: application/json" \
  -d '{
    "source": "whatsapp",
    "data": "Budi: pesan 2 es teh 1L besok ya\nSari: order nasi goreng 3 porsi"
  }'
```

Response:
```json
{
  "orders": [
    {
      "customer": "Budi",
      "product": "Es Teh 1L",
      "quantity": 2,
      "date": "2026-04-27",
      "confidence": 0.9
    },
    {
      "customer": "Sari",
      "product": "Nasi Goreng",
      "quantity": 3,
      "date": "2026-04-26",
      "confidence": 0.95
    }
  ],
  "metadata": {
    "source": "whatsapp",
    "confidence": 0.925,
    "total_orders": 2,
    "valid_orders": 2,
    "warnings": []
  }
}
```

### POST /extract/orders — CSV text

```bash
curl -X POST http://localhost:8000/extract/orders \
  -H "Content-Type: application/json" \
  -d '{
    "source": "csv_text",
    "data": "nama pelanggan,nama produk,jumlah order,tanggal\nSari,Es Jeruk,3,2026-04-27"
  }'
```

### POST /extract/orders/file — Excel upload

```bash
curl -X POST http://localhost:8000/extract/orders/file \
  -F "file=@orders.xlsx" \
  -F "source=excel"
```

---

## Normalization Rules

| Raw Value       | Normalized      |
|-----------------|-----------------|
| `"besok"`       | `"2026-04-27"`  |
| `"hari ini"`    | `"2026-04-26"`  |
| `"senin"`       | next Monday ISO |
| `"2"`           | `2` (int)       |
| `"dua"`         | `2` (int)       |
| `"nasgor"`      | `"Nasi Goreng"` |
| `"es the"`      | `"Es Teh"`      |

---

## Column Aliases (Excel/CSV)

The parser fuzzy-matches these column names automatically:

| Canonical   | Recognized aliases                              |
|-------------|--------------------------------------------------|
| `customer`  | nama, name, pelanggan, buyer, customer name     |
| `product`   | produk, item, barang, menu, nama produk         |
| `quantity`  | qty, jumlah, banyak, jumlah_order               |
| `date`      | tanggal, tgl, order date, delivery_date         |

---

## Adding a New Source

1. Create `src/parsers/your_parser.py` implementing:

```python
class YourParser:
    async def parse(self, data, options: dict) -> dict:
        # Returns: {"raw_orders": [...], "source_meta": {...}}
```

2. Register in `src/router/source_router.py`:

```python
self._parsers = {
    ...
    "your_source": YourParser(),
}
```

That's it. The rest of the pipeline (normalize → validate → format) works automatically.

---

## Running Tests

```bash
python tests/test_pipeline.py
```

Expected: 19/19 passed

---

## Project Structure

```
order-extraction-api/
├── main.py                      # FastAPI app + endpoints
├── requirements.txt
├── dashboard.html               # Interactive demo dashboard
├── src/
│   ├── models.py                # Pydantic schemas
│   ├── router/
│   │   └── source_router.py    # Pipeline orchestrator
│   ├── parsers/
│   │   ├── whatsapp_parser.py  # WhatsApp chat parser
│   │   ├── excel_parser.py     # Excel/CSV file parser
│   │   └── csv_parser.py       # Inline CSV parser
│   ├── normalizer/
│   │   └── normalizer.py       # Value normalization
│   ├── validator/
│   │   └── validator.py        # Validation + confidence scoring
│   └── formatter/
│       └── formatter.py        # Output formatting
└── tests/
    └── test_pipeline.py        # End-to-end test suite
```
