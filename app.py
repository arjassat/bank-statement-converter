import re
import io
import csv
from datetime import datetime

import pandas as pd
import pytesseract
import streamlit as st
from pdf2image import convert_from_bytes


# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config(
    page_title="Bank Statement Converter",
    page_icon="🏦",
    layout="wide"
)

OCR_CONFIG = r'--oem 3 --psm 6'


# ============================================================
# HELPERS
# ============================================================

def extract_year(text):

    match = re.search(r'(20\d{2})', text)

    if match:
        return match.group(1)

    return str(datetime.now().year)


def clean_amount(raw_amount):

    if not raw_amount:
        return None

    raw_amount = raw_amount.replace(',', '').strip()

    negative = False

    if raw_amount.endswith('-'):
        negative = True
        raw_amount = raw_amount[:-1]

    if raw_amount.startswith('-'):
        negative = True
        raw_amount = raw_amount[1:]

    try:
        value = float(raw_amount)

        if negative:
            value = -value

        return round(value, 2)

    except:
        return None


def clean_description(text):

    text = re.sub(r'\b\d{2}:\d{2}(?::\d{2})?\b', '', text)
    text = re.sub(r'\b\d{4}\*\d{4}\b', '', text)

    text = re.sub(r'[^A-Za-z0-9\s\-/&.@#]', ' ', text)

    text = re.sub(r'\s+', ' ', text)

    text = text.strip()

    words = text.split()

    text = ' '.join(words[:10])

    return text


def is_noise(line):

    blacklist = [
        'STATEMENT',
        'ACCOUNT SUMMARY',
        'VAT',
        'BALANCE BROUGHT FORWARD',
        'CLOSING BALANCE',
        'OPENING BALANCE',
        'CUSTOMER CARE',
        'PAGE',
        'REGISTERED CREDIT PROVIDER',
    ]

    upper = line.upper()

    return any(word in upper for word in blacklist)


# ============================================================
# MAIN OCR PARSER
# ============================================================

def parse_statement(pdf_bytes):

    pages = convert_from_bytes(pdf_bytes, dpi=300)

    first_page_text = pytesseract.image_to_string(
        pages[0],
        config=OCR_CONFIG
    )

    year = extract_year(first_page_text)

    transactions = []

    pending_description = ''

    amount_pattern = re.compile(
        r'(\d[\d,]*\.\d{2}-?)'
    )

    date_pattern = re.compile(
        r'\b(\d{2})\s(\d{2})\b'
    )

    for page in pages:

        text = pytesseract.image_to_string(
            page,
            config=OCR_CONFIG
        )

        lines = text.split('\n')

        for raw_line in lines:

            line = raw_line.strip()

            if not line:
                continue

            if is_noise(line):
                continue

            amounts = amount_pattern.findall(line)

            dates = date_pattern.findall(line)

            # ====================================================
            # TRANSACTION DETECTED
            # ====================================================

            if amounts and dates:

                # ====================================================
# SMART TRANSACTION AMOUNT DETECTION
# ====================================================

amount_raw = None

# Debit transaction
for amt in amounts:
    if amt.endswith('-'):
        amount_raw = amt
        break

# Credit transaction
if amount_raw is None:

    # Usually:
    # second-last amount = transaction
    # last amount = running balance

    if len(amounts) >= 2:
        amount_raw = amounts[-2]

    else:
        amount_raw = amounts[0]

                amount = clean_amount(amount_raw)

                if amount is None:
                    continue

                month = dates[0][0]
                day = dates[0][1]

                try:

                    formatted_date = datetime.strptime(
                        f'{day}/{month}/{year}',
                        '%d/%m/%Y'
                    ).strftime('%d/%m/%Y')

                except:
                    continue

                description = line

                for d in dates:
                    description = description.replace(
                        f'{d[0]} {d[1]}',
                        ''
                    )

                for amt in amounts:
                    description = description.replace(amt, '')

                if pending_description:
                    description = pending_description + ' ' + description
                    pending_description = ''

                description = clean_description(description)

                if len(description) < 3:
                    continue

                transactions.append({
                    'Date': formatted_date,
                    'Description': description,
                    'Amount': amount,
                })

            else:

                # ====================================================
                # WRAPPED DESCRIPTION
                # ====================================================

                cleaned = clean_description(line)

                if not cleaned:
                    continue

                if len(cleaned.split()) <= 1:
                    continue

                numeric_ratio = (
                    sum(c.isdigit() for c in cleaned)
                    / max(len(cleaned), 1)
                )

                if numeric_ratio > 0.35:
                    continue

                pending_description = cleaned

    # ============================================================
    # DATAFRAME CLEANUP
    # ============================================================

    if not transactions:
        return pd.DataFrame(
            columns=['Date', 'Description', 'Amount']
        )

    df = pd.DataFrame(transactions)

    df = df.drop_duplicates()

    df = df[df['Amount'] != 0]

    df = df[df['Description'].str.len() > 2]

    df = df.reset_index(drop=True)

    return df


# ============================================================
# STREAMLIT UI
# ============================================================

st.title('🏦 Bank Statement Converter')

st.write(
    'Upload bank statement PDFs and export clean CSV files.'
)

uploaded_file = st.file_uploader(
    'Upload PDF Statement',
    type=['pdf']
)

if uploaded_file:

    st.success('PDF uploaded successfully')

    if st.button('Process Statement'):

        with st.spinner('Extracting transactions...'):

            try:

                pdf_bytes = uploaded_file.read()

                df = parse_statement(pdf_bytes)

                if df.empty:

                    st.error('No transactions detected.')

                    st.stop()

                st.success(
                    f'{len(df)} transactions extracted successfully'
                )

                st.subheader('Transaction Preview')

                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                )

                csv_buffer = io.StringIO()

                df.to_csv(
                    csv_buffer,
                    index=False,
                    quoting=csv.QUOTE_MINIMAL,
                )

                st.download_button(
                    label='Download CSV',
                    data=csv_buffer.getvalue(),
                    file_name=f'bank_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                    mime='text/csv'
                )

            except Exception as e:

                st.error(f'Error processing PDF: {str(e)}')
