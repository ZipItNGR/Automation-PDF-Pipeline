import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INCOMING_DIR = BASE_DIR / "invoices" / "incoming"

def create_invoice(filename, vendor_name, iban, total, vat, line_items_amount):
    INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(INCOMING_DIR / filename), pagesize=letter)
    c.drawString(100, 750, "INVOICE")
    c.drawString(100, 730, f"Vendor: {vendor_name}")
    c.drawString(100, 710, f"Invoice Number: INV-{filename.split('_')[0]}")
    c.drawString(100, 690, f"IBAN: {iban}")
    c.drawString(100, 670, "-" * 50)
    c.drawString(100, 650, f"Line Items Subtotal: ${line_items_amount:.2f}")
    c.drawString(100, 630, f"VAT Amount: ${vat:.2f}")
    c.drawString(100, 610, "-" * 50)
    c.drawString(100, 590, f"Total Amount Due: ${total:.2f}")
    c.save()

if __name__ == "__main__":
    # Clean invoice - Math matches, Vendor exists, IBAN matches expected (BG98STSA93000012345678)
    create_invoice(
        "1001_clean.pdf",
        "TechCorp Solutions",
        "BG98 STSA 9300 0012 3456 78", # IBAN formatted with spaces
        1200.00,
        200.00,
        1000.00
    )

    # Fraudulent invoice 1 - IBAN mismatch (different from database)
    create_invoice(
        "1002_fraud_iban.pdf",
        "TechCorp Solutions",
        "BG12 HACK 9999 0012 3456 78", # Fake hacker IBAN
        600.00,
        100.00,
        500.00
    )

    # Fraudulent invoice 2 - Math mismatch (Subtotal + VAT != Total)
    create_invoice(
        "1003_math_error.pdf",
        "Office Supplies Ltd",
        "BG12UNCR76301045612300", 
        250.00, # Actual total written on paper
        40.00,
        200.00 # 200 + 40 = 240, but invoice claims 250!
    )
    
    print(f"Generated 3 test invoices in {INCOMING_DIR}")
