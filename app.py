import streamlit as st
import PyPDF2
import io
import pandas as pd
import re
import pytesseract
from pdf2image import convert_from_path, convert_from_bytes
from PIL import Image
import tempfile
import os

# Bank patterns for detection
BANK_PATTERNS = {
    'ABSA': r'ABSA|Absa',
    'Nedbank': r'Nedbank',
    'FNB': r'FNB|First National',
    'HBZ': r'HBZ',
    'Capitec': r'Capitec',
    'Standard Bank': r'Standard Bank|Stanlib'
}

@st.cache_data
def extract_text_from_pdf(pdf_bytes, use_ocr=False):
    if not use_ocr:
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except:
            pass
    # Fallback to OCR
    images = convert_from_bytes(pdf_bytes)
    text = ""
    for img in images:
        text += pytesseract.image_to_string(img) + "\n"
    return text

def detect_bank(text):
    for bank, pattern in BANK_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return bank
    return 'Unknown'

def parse_transactions(text, bank):
    # Flexible regex for common SA bank formats: Date Description Amount
    # Adjusts slightly per bank based on common patterns
    patterns = {
        'ABSA': r'(\d{2}/\d{2}/\d{4})\s+([^\n]+?)\s+([-\d,]+\.\d{2})',
        'Nedbank': r'(\d{2}-\d{2}-\d{4})\s+([^\n]+?)\s+([-\d,]+\.\d{2})',
        'FNB': r'(\d{4}-\d{2}-\d{2})\s+([^\n]+?)\s+([-\d,]+\.\d{2})',
        'HBZ': r'(\d{2}/\d{2}/\d{4})\s+([^\n]+?)\s+([-\d,]+\.\d{2})',
        'Capitec': r'(\d{2}-\d{2}-\d{4})\s+([^\n]+?)\s+([-\d,]+\.\d{2})',
        'Standard Bank': r'(\d{2}/\d{4})\s+([^\n]+?)\s+([-\d,]+\.\d{2})',  # Short date
        'Unknown': r'(\d{2}[/-]\d{2}[/-]\d{4})\s+([^\n]+?)\s+([-\d,]+\.\d{2})'
    }
    pattern = patterns.get(bank, patterns['Unknown'])
    matches = re.findall(pattern, text, re.MULTILINE)
    
    data = []
    for match in matches:
        date_str, desc, amt_str = match
        # Standardize date to YYYY-MM-DD
        try:
            if len(date_str.split('/')[0]) == 2:  # DD/MM/YYYY
                d, m, y = date_str.split('/')
                date = f"20{y if len(y)==2 else y[2:]}-{m.zfill(2)}-{d.zfill(2)}"
            elif '-' in date_str:
                parts = date_str.split('-')
                if len(parts[0]) == 4:  # YYYY-MM-DD
                    date = date_str
                else:  # DD-MM-YYYY
                    d, m, y = parts
                    date = f"20{y}-{m.zfill(2)}-{d.zfill(2)}"
            else:
                date = date_str  # Fallback
        except:
            date = 'N/A'
        
        # Clean amount: remove commas, detect debit/credit
        amt = float(re.sub(r'[,\s]', '', amt_str))
        if amt > 0 and 'debit' in desc.lower():  # Simple debit detect
            amt = -amt
        
        # Clean description: trim, remove extra refs/codes for Xero
        desc = re.sub(r'\s+', ' ', desc.strip())  # Normalize spaces
        desc = re.sub(r'REF[:\s]*\d+', '', desc)  # Remove ref numbers if verbose
        desc = desc[:100]  # Cap length for Xero
        
        data.append({'Date': date, 'Description': desc, 'Amount': amt})
    
    return pd.DataFrame(data)

st.title("🚀 Free SA Bank Statement PDF to CSV Converter")
st.write("Upload your PDF (digital or scanned). Supports ABSA, Nedbank, FNB, HBZ, Capitec, Standard Bank. Outputs Xero-ready CSV.")

uploaded_files = st.file_uploader("Choose PDF files", type='pdf', accept_multiple_files=True)

for uploaded_file in uploaded_files:
    with st.spinner(f'Processing {uploaded_file.name}...'):
        pdf_bytes = uploaded_file.read()
        
        # Auto-detect if OCR needed (if text extraction fails)
        text = extract_text_from_pdf(pdf_bytes, use_ocr=False)
        use_ocr = len(text) < 100  # Rough check for scanned
        if use_ocr:
            text = extract_text_from_pdf(pdf_bytes, use_ocr=True)
        
        bank = detect_bank(text)
        st.info(f"Detected Bank: {bank}")
        
        df = parse_transactions(text, bank)
        
        if not df.empty:
            st.success(f"Extracted {len(df)} transactions!")
            st.dataframe(df.head(10))  # Preview first 10
            
            # Download CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{uploaded_file.name.replace('.pdf', '')}_transactions.csv",
                mime="text/csv"
            )
        else:
            st.warning("No transactions found. Try a clearer scan or manual review.")

st.write("---")
st.write("Built for Xero uploads. Questions? Reply here.")
