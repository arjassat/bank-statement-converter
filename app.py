import re
    # DATAFRAME CLEANUP
    # ============================================================

    if not transactions:
        return pd.DataFrame(columns=['Date', 'Description', 'Amount'])

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

                st.success(f'{len(df)} transactions extracted successfully')

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
