import cv2
import numpy as np
import pytesseract
import requests
import json
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# If running app on Pi and LLM on PC, replace localhost with your PC's local IP (e.g., http://192.168.1.15:11434)
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:3b"

def preprocess_image(image_path: str):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not open image: {image_path}")

    # 1. Red channel isolates text and naturally erases red pen circles
    red = img[:, :, 2]

    # 2. Add clean white border so text near margins is never clipped
    padded = cv2.copyMakeBorder(red, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=[255])

    # 3. Scale 2x for OCR character contour clarity
    scaled = cv2.resize(padded, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)

    # 4. Contrast Limited Adaptive Histogram Equalization (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(scaled)

    # 5. Otsu thresholding produces solid letters with clean white background
    _, thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 6. Light 2x2 morphological open to eliminate stray single-pixel dust/speckles
    clean_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, clean_kernel)

    return cleaned

def run_ocr(thresh_img) -> str:
    # PSM 4: Single column of text of variable sizes (reads all the way down to bottom totals)
    custom_config = (
        r"--oem 3 --psm 4 "
        r"-c tessedit_char_blacklist=|~_§«» "
        r"-c preserve_interword_spaces=1"
    )
    raw_text = pytesseract.image_to_string(thresh_img, config=custom_config)
    
    clean_lines = []
    for line in raw_text.splitlines():
        if re.search(r'[a-zA-Z0-9]', line):
            clean_lines.append(line)
            
    return "\n".join(clean_lines).strip()

def clean_ocr_text(text: str) -> str:
    """Repairs common OCR currency typos and recovers dropped totals."""
    cleaned_lines = []
    has_grand_total = bool(re.search(r'(Grand\s*Total|Net\s*Total)', text, re.IGNORECASE))
    
    subtotal_val = None
    tax_sum = 0.0

    for line in text.splitlines():
        # Clean common OCR misread of '.00' ending as '.0C', '.0€', or '.06'
        line = re.sub(r'(\d+\.\d)[Cc€G]', r'\g<1>0', line)
        
        # Extract Sub Total if present
        m_sub = re.search(r'Sub\s*Total\D*(\d+\.?\d*)', line, re.IGNORECASE)
        if m_sub:
            try:
                subtotal_val = float(m_sub.group(1))
            except ValueError:
                pass

        # Detect tax/service charge add-ons
        m_tax = re.search(r'(CGST|SGST|Service Charge)\D*(\d+\.\d{2})', line, re.IGNORECASE)
        if m_tax:
            try:
                tax_sum += float(m_tax.group(2))
            except ValueError:
                pass

        # Decimal repair for unpointed numbers (e.g., 635 -> 6.35)
        m = re.search(r'(Total|Payable|Amount|Incl|GST)[\w\s.:-]*[:\s]\s*(\d{3,4})\b', line, re.IGNORECASE)
        if m and '.' not in m.group(0):
            val = m.group(2)
            corrected_val = f"{val[:-2]}.{val[-2:]}"
            line = line.replace(val, corrected_val)
            
        cleaned_lines.append(line)

    # Arithmetic safety net: If the bottom edge cut off 'Grand Total', append it logically
    if not has_grand_total and subtotal_val is not None:
        estimated_total = round(subtotal_val + (tax_sum if tax_sum > 0 else 0.0), 2)
        cleaned_lines.append(f"Grand Total: {estimated_total}")

    return "\n".join(cleaned_lines)

def extract_and_summarize(ocr_text: str) -> dict:
    cleaned_text = clean_ocr_text(ocr_text)

    prompt_extract = f"""You are a commercial receipt data extractor.
Extract structured metadata strictly from the raw receipt text.

STRICT EXTRACTION RULES:
1. CATEGORY:
   - Assign exactly ONE category based strictly on the business and items purchased:
     * "Food & Beverage": Restaurants, fast food, cafes, bakeries, bars.
     * "Retail & Groceries": Supermarkets, hardware, electronics, electrical parts, clothing, gifts.
     * "Fuel & Transport": Petrol pumps, gas stations, tolls, parking, transit.
     * "Utilities & Services": Telecom recharges, electricity/water bills, repair services.
     * "Healthcare": Pharmacies, clinics, medical stores.
     * "Other": Unclear or miscellaneous.
   - Do NOT default to "Food & Beverage". Choose the category matching the merchant.

2. ITEMS & TOTAL QUANTITY:
   - Identify the actual billed items (look for lines that have a price or quantity attached).
   - Combo sub-items or drink choices listed without individual prices (e.g., 'M Coke', 'M Fries' under a combo burger) belong to the parent meal. List only the distinct parent items (e.g., SpicyDeluxe, GrilChicBgr, Small Cone).
   - Sum the parent item quantities to find 'total_items' (e.g., 2 + 1 + 1 = 4 items).

3. MERCHANT: Store, franchise, or company name at the header.
4. TOTAL AMOUNT: Final payable balance (Total Rounded, Grand Total, Net Total, or Total Amt Payable). Disregard tender/cash paid amounts.
5. CONTACT: Phone, email, address, or tax ID.
6. RETURN POLICY: Stated return/refund policy or 'Not stated'.
7. DATE: Transaction date.

RAW RECEIPT TEXT:
\"\"\"{cleaned_text}\"\"\"

Output STRICT JSON:
{{
  "merchant": "Merchant Name",
  "items": ["Item A", "Item B"],
  "total_items": 0,
  "total_amount": 0.0,
  "category": "One Category from the rules",
  "contact_info": "Contact details",
  "return_policy": "Policy or Not stated",
  "date": "Date"
}}"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt_extract,
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.0}
    }

    data = {}
    try:
        res = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=45)
        res.raise_for_status()
        raw_resp = res.json().get("response", "{}")
        data = json.loads(raw_resp)
    except Exception as e:
        print(f"Extraction error: {e}")

    merchant = str(data.get("merchant", "Unknown Store")).strip()

    # Clean and filter item names
    items = data.get("items", [])
    if not isinstance(items, list):
        items = [str(items)]
    items = [it.strip() for it in items if it.strip()]

    # Parse quantity safely
    raw_qty = data.get("total_items")
    try:
        count = int(float(raw_qty)) if raw_qty is not None and float(raw_qty) > 0 else len(items)
    except (ValueError, TypeError):
        count = len(items) if items else 1

    items_str = ", ".join(items) if items else "purchased items"
    total = data.get("total_amount", 0.0)
    category = data.get("category", "Other")

    # Construct clean English summary
    english_summary = (
        f"The bill is from {merchant}, the bill states total {count} item(s) were bought, "
        f"the items are as follows: {items_str}, and the total amount is {total}."
    )

    # Translation to Hindi
    prompt_hi = f"""Translate this English sentence into natural Hindi in Devanagari script.
Return ONLY the Hindi sentence.

Sentence: {english_summary}"""

    hindi_summary = "विवरण उपलब्ध नहीं है।"
    try:
        res_hi = requests.post(
            OLLAMA_ENDPOINT,
            json={"model": MODEL_NAME, "prompt": prompt_hi, "stream": False, "options": {"temperature": 0.0}},
            timeout=30
        )
        res_hi.raise_for_status()
        hindi_summary = res_hi.json().get("response", "").strip()
    except Exception as e:
        print(f"Translation error: {e}")

    return {
        "merchant": merchant,
        "items": items,
        "total_items_count": count,
        "date": data.get("date", "N/A"),
        "total": total,
        "category": category,
        "contact_info": data.get("contact_info", "N/A"),
        "return_policy": data.get("return_policy", "Not stated"),
        "english_summary": english_summary,
        "hindi_summary": hindi_summary
    }

def ask_receipt_question(ocr_text: str, user_question: str) -> str:
    prompt = f"""Answer the question using ONLY the receipt text. If absent, answer: "This information is not stated on the receipt."

RECEIPT TEXT:
\"\"\"{ocr_text}\"\"\"

QUESTION:
{user_question}

ANSWER:"""

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0}
    }
    try:
        res = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=30)
        res.raise_for_status()
        return res.json().get("response", "").strip()
    except Exception as e:
        return f"Error: {e}"