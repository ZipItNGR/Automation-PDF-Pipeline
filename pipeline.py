import os
import json
import shutil
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

load_dotenv()

# Initialize API Key manually or allow GenAI client to pick it up from env
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY is not set in the environment.")

client = genai.Client(api_key=api_key)

# Setup directories
BASE_DIR = Path(__file__).resolve().parent
INCOMING_DIR = BASE_DIR / "invoices" / "incoming"
APPROVED_DIR = BASE_DIR / "invoices" / "approved"
FLAGGED_DIR = BASE_DIR / "invoices" / "flagged"
REPORTS_DIR = BASE_DIR / "reports"
DATABASE_FILE = BASE_DIR / "database" / "vendors.json"

for folder in [INCOMING_DIR, APPROVED_DIR, FLAGGED_DIR, REPORTS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# Define unstructured output schema using Pydantic
class InvoiceData(BaseModel):
    vendor_name: str = Field(description="The name of the vendor or supplier who issued the invoice.")
    iban: str = Field(description="The IBAN (International Bank Account Number) for payment. If multiple exist, take the primary one.")
    total_amount: float = Field(description="The total amount to be paid, including VAT. Extract as a float.")
    vat_amount: float = Field(description="The total VAT amount calculated on the invoice. Use 0.0 if there is no VAT.")
    line_items_total: float = Field(description="The sum of all line items before VAT. Also known as subtotal.")
    invoice_number: str = Field(description="The invoice number.")

def load_vendor_db() -> dict:
    if not DATABASE_FILE.exists():
        print(f"Warning: Vendor database not found at {DATABASE_FILE}")
        return {}
    with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_invoice_with_gemini(pdf_path: Path) -> InvoiceData | None:
    print(f"Uploading {pdf_path.name} to Gemini via GenAI SDK...")
    
    # Upload the file
    uploaded_file = client.files.upload(file=str(pdf_path))
    
    try:
        print(f"Analyzing {pdf_path.name} with Gemini Pro...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                uploaded_file,
                "Please extract the specific fields from this invoice as requested in the schema."
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=InvoiceData,
            ),
        )
        # Parse JSON into Pydantic obj
        extracted_data = InvoiceData.model_validate_json(response.text)
        return extracted_data
    except Exception as e:
        error_msg = f"Error during Gemini extraction: {e}"
        print(error_msg)
        with open("error_log.txt", "a", encoding="utf-8") as ef:
            ef.write(error_msg + "\n")
        return None
    finally:
        # Cleanup file from Google servers
        client.files.delete(name=uploaded_file.name)

def validate_invoice(extracted_data: InvoiceData, vendor_db: dict) -> list[str]:
    reasons = []
    
    # 1. Math Check (Subtotal + VAT == Total)
    calculated_total = round(extracted_data.line_items_total + extracted_data.vat_amount, 2)
    extracted_total = round(extracted_data.total_amount, 2)
    if calculated_total != extracted_total:
        reasons.append(f"Math check failed: Line Items Total ({extracted_data.line_items_total}) + VAT ({extracted_data.vat_amount}) = {calculated_total}, but Total Extract is {extracted_total}.")

    # 2. Database Checks
    vendor_info = vendor_db.get(extracted_data.vendor_name)
    if not vendor_info:
        reasons.append(f"Vendor '{extracted_data.vendor_name}' not found in known database.")
    else:
        # Check IBAN
        if extracted_data.iban.replace(" ", "") != vendor_info.get("expected_iban", "").replace(" ", ""):
            reasons.append(f"IBAN mismatch: Found '{extracted_data.iban}', Expected '{vendor_info.get('expected_iban')}'.")
            
        # Check VAT rate (Basic check: VAT amount / Subtotal approx matches expected rate)
        if extracted_data.line_items_total > 0:
            implied_vat = extracted_data.vat_amount / extracted_data.line_items_total
            expected_vat = vendor_info.get("expected_vat_rate", 0.0)
            if abs(implied_vat - expected_vat) > 0.01: # 1% tolerance
                reasons.append(f"VAT rate anomaly: Implied rate is {implied_vat:.2%}, expected {expected_vat:.2%}.")
                
    return reasons

def process_invoices():
    vendor_db = load_vendor_db()
    pdf_files = list(INCOMING_DIR.glob('*.pdf'))
    
    if not pdf_files:
        print("No invoices found in incoming directory.")
        return
        
    for pdf_path in pdf_files:
        print("-" * 40)
        print(f"Processing: {pdf_path.name}")
        
        extracted_data = analyze_invoice_with_gemini(pdf_path)
        if not extracted_data:
            print("Failed to extract data. Moving to flagged.")
            shutil.move(str(pdf_path), FLAGGED_DIR / pdf_path.name)
            continue
            
        print(f"Extracted: {extracted_data.model_dump_json(indent=2)}")
        
        reasons = validate_invoice(extracted_data, vendor_db)
        
        report = {
            "invoice_file": pdf_path.name,
            "extracted_data": extracted_data.model_dump(),
            "status": "APPROVED" if not reasons else "FLAGGED",
            "flagged_reasons": reasons
        }
        
        report_path = REPORTS_DIR / f"{pdf_path.stem}_report.json"
        with open(report_path, "w", encoding="utf-8") as rf:
            json.dump(report, rf, indent=2)
            
        if reasons:
            print(f"Status: FLAGGED")
            for r in reasons:
                print(f" - {r}")
            shutil.move(str(pdf_path), FLAGGED_DIR / pdf_path.name)
        else:
            print(f"Status: APPROVED")
            shutil.move(str(pdf_path), APPROVED_DIR / pdf_path.name)

if __name__ == "__main__":
    process_invoices()
