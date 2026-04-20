import streamlit as st
import pandas as pd
import pdfplumber
import re
from collections import defaultdict
from datetime import datetime
from fpdf import FPDF
import io
import zipfile

st.title("Payment Receipt Generator (Production)")

uploaded_files = st.file_uploader(
    "Upload one or more Invoice PDFs",
    type="pdf",
    accept_multiple_files=True
)

# --- Improved extraction ---
def extract_data(files):
    rows = []

    for file in files:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()

                if not text:
                    continue

                for line in text.split("\n"):
                    # Match lines with amounts
                    match = re.search(r"(.+?)\s+(\d+)\s+\$?([\d.]+)\s+\$([\d.]+)", line)

                    if match:
                        try:
                            name = match.group(1).strip().upper()
                            interviews = int(match.group(2))
                            rate = float(match.group(3))
                            amount = float(match.group(4))

                            # Filter out junk rows
                            if interviews > 0 and amount > 0:
                                rows.append({
                                    "name": name,
                                    "interviews": interviews,
                                    "rate": rate,
                                    "amount": amount
                                })
                        except:
                            continue
    return rows

# --- Grouping ---
def group_data(rows):
    grouped = defaultdict(lambda: {"interviews": 0, "amount": 0})

    for r in rows:
        key = r["name"]
        grouped[key]["interviews"] += r["interviews"]
        grouped[key]["amount"] += r["amount"]

    return grouped

# --- Excel ---
def create_excel(grouped):
    data = []

    total_payout = 0

    for name, vals in grouped.items():
        total_payout += vals["amount"]

        data.append({
            "Interviewer": name,
            "Total Interviews": vals["interviews"],
            "Rate": 0.12,
            "Total Payment": round(vals["amount"], 2)
        })

    df = pd.DataFrame(data)

    # Sort highest earners first
    df = df.sort_values(by="Total Payment", ascending=False)

    return df, total_payout

# --- PDF Receipt ---
def create_pdf(name, interviews, amount):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="PAYMENT RECEIPT", ln=True)
    pdf.cell(200, 10, txt=f"Date: {datetime.today().strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(5)

    pdf.cell(200, 10, txt=f"Pay To: {name}", ln=True)
    pdf.ln(5)

    pdf.cell(200, 10, txt=f"Total Interviews: {interviews}", ln=True)
    pdf.cell(200, 10, txt=f"Rate: $0.12", ln=True)
    pdf.cell(200, 10, txt=f"Total Payment: ${round(amount,2)}", ln=True)

    return pdf.output(dest='S').encode('latin-1')

# --- MAIN FLOW ---
if uploaded_files:
    st.write("Processing PDFs...")

    rows = extract_data(uploaded_files)
    grouped = group_data(rows)

    df, total_payout = create_excel(grouped)

    st.success(f"Processed {len(grouped)} interviewers across {len(uploaded_files)} files")
    st.metric("Total Payout", f"${round(total_payout,2)}")

    st.subheader("Preview")
    st.dataframe(df)

    # Excel download
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)

    st.download_button(
        label="Download Excel Summary",
        data=excel_buffer.getvalue(),
        file_name="payments_summary.xlsx"
    )

    # --- ZIP all PDFs ---
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        for name, vals in grouped.items():
            pdf_bytes = create_pdf(name, vals["interviews"], vals["amount"])
            filename = f"{name.replace(' ', '_')}.pdf"
            z.writestr(filename, pdf_bytes)

    st.download_button(
        label="Download ALL Receipts (ZIP)",
        data=zip_buffer.getvalue(),
        file_name="receipts.zip"
    )
