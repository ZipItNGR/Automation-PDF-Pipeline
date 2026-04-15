PDF Invoice Inconsistency Checker: Project Walkthrough
AI-powered pipeline that automatically ingests and reviews incoming supplier invoices. Here is an overview of the implementation and how to use it.

Architecture & Workflow
The system is built sequentially to process unstructured PDFs into highly structured, validated data:

Ingestion (invoices/incoming/): Any PDF dropped into this directory is automatically processed by pipeline.py.
AI Capabilities (Gemini 2.5 Flash): Instead of traditional OCR which misses context, the script passes the raw PDF up to the Gemini Mulitmodal API and queries it with a Pydantic schema, reliably extracting the Subtotal, Total Amount, VAT, Vendor Name, Bank IBAN, and Invoice Number.
Database Lookback (database/vendors.json): We cross-reference the parsed Vendor Name with a local mock dataset containing anticipated details (expected IBAN, standard VAT rate for that supplier).
Validation Engine: Performs logical constraints:
Math Continuity: Line Items Total + VAT MUST equal Total Amount.
Identity Confidence: The parsed IBAN MUST accurately mirror the expected_iban stored on file.
Categorical Actioning:
Passed Invoices are relocated to invoices/approved/.
Flawed Invoices move to invoices/flagged/ and print specific reasons for human review (e.g. math errors or unrecognized bank accounts).
In both cases, a log file is written to the reports/ folder.

File Map
pipeline.py
: The main execution script. Run this to execute the checker.
database/vendors.json
: The repository containing standard expected parameters for verified suppliers.
mock_invoice_generator.py
: An auxiliary script that creates test PDFs.
.env
: Environment variables housing the GEMINI_API_KEY (included in .gitignore for safety reasons).
requirements.txt
: Python dependencies.

Verification Run
Using the gemini-2.5-flash, which parses the information flawlessly. Using mock_invoice_generator.py, we created three fictional scenarios and ran the pipeline:

NOTE

Scenario 1: A clean invoice totaling $1200 ($1000 + $200 VAT) from TechCorp Solutions matching expectations natively. Outcome: APPROVED. Located in invoices/approved/1001_clean.pdf.

CAUTION

Scenario 2: A fraudulent invoice from TechCorp Solutions where everything matched, EXCEPT the IBAN had been manipulated to an unexpected one. Outcome: FLAGGED. Routed to invoices/flagged/1002_fraud_iban.pdf. Caught output: "IBAN mismatch: Found 'BG12 HACK 9999 0012 3456 78', Expected 'BG98STSA93000012345678'".

WARNING

Scenario 3: A broken invoice logically where the math sum on the paper (claiming $250.00) incorrectly failed against the subtotal entries on the page ($200.00 + $40.00 VAT = $240.00). Outcome: FLAGGED. Routed to invoices/flagged/1003_math_error.pdf. Caught output: "Math check failed: Line Items Total (200.0) + VAT (40.0) = 240.0, but Total Extract is 250.0."

How To Use
Place real PDF invoices in the Pipeline\invoices\incoming directory.
Ensure you have the vendors.json filled out to match the providers in those invoices.
Run python pipeline.py from that directory.
Check the reports, approved, and flagged folders to see the results of Gemini's API labor!
