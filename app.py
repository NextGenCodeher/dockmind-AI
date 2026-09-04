import os
import subprocess
import streamlit as st
from jinja2 import Template
from playwright.sync_api import sync_playwright

# Ensure Playwright browser is installed in Streamlit Cloud environment
@st.cache_resource
def install_playwright_browsers():
    subprocess.run(["playwright", "install", "chromium"])

try:
    install_playwright_browsers()
except Exception as e:
    st.warning(f"Browser installation step: {e}")

st.set_page_config(page_title="DocMind AI - PDF Generator", layout="wide", page_icon="📄")

st.title("📄 DocMind AI: PDF Document Generator")
st.write("Upload a template PDF for reference and customize content fields to generate a formatted document.")

HTML_TEMPLATE_STRING = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @page { size: A4; margin: 20mm; }
  body { font-family: 'Times New Roman', Times, serif; font-size: 12pt; line-height: 1.6; color: #000; }
  .header { text-align: center; font-weight: bold; font-size: 14pt; text-transform: uppercase; margin-bottom: 25px; }
  .date { text-align: right; margin-bottom: 20px; font-weight: bold; }
  .address { margin-bottom: 20px; }
  .subject { font-weight: bold; text-decoration: underline; margin-top: 15px; margin-bottom: 20px; }
  .salutation { margin-bottom: 15px; }
  .body-paragraph { text-align: justify; text-indent: 40px; margin-bottom: 15px; }
  .closing { margin-top: 40px; }
  .signature { margin-top: 50px; }
</style>
</head>
<body>
  <div class="header">{{ content.header }}</div>
  <div class="date">Date: {{ content.date }}</div>
  <div class="address">
    <b>To,</b><br>
    {% for line in content.address.split('\n') %}{{ line }}<br>{% endfor %}
  </div>
  <div class="subject">Subject: {{ content.subject }}</div>
  <div class="salutation">{{ content.salutation }},</div>
  {% for p in content.paragraphs.split('\n\n') %}
    <div class="body-paragraph">{{ p }}</div>
  {% endfor %}
  <div class="closing">Thanking you,<br>{{ content.sign_off }},</div>
  <div class="signature">
    <b>{{ content.sender_name }}</b><br>
    {{ content.sender_title }}
  </div>
</body>
</html>
"""

def generate_pdf(content_data, output_path="final_letter_output.pdf"):
    template = Template(HTML_TEMPLATE_STRING)
    rendered_html = template.render(content=content_data)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html)
        page.pdf(path=output_path, format="A4", print_background=True)
        browser.close()
    return output_path

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Input Template & Content")
    
    uploaded_pdf = st.file_uploader("Upload Reference Template PDF (Optional)", type=["pdf"])
    if uploaded_pdf:
        st.info(f"Loaded reference: {uploaded_pdf.name}")

    header = st.text_input("Department / Organization Header", "DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING")
    date_str = st.text_input("Date", "September 5, 2026")
    address = st.text_area("To Address (One line per row)", "The Principal\nG. Pulla Reddy Engineering College\nKurnool")
    subject = st.text_input("Subject", "Request for Lab Resources")
    salutation = st.text_input("Salutation", "Respected Sir")
    paragraphs = st.text_area("Body Content (Separate paragraphs with blank lines)", 
                              "I am writing to request access to the machine learning laboratory for our research project.\n\nWe plan to run multi-node workload experiments starting next week.")
    sign_off = st.text_input("Sign Off", "Yours faithfully")
    sender_name = st.text_input("Sender Name", "Honey Amilineni")
    sender_title = st.text_input("Sender Title", "Student Lead, CSE")

    generate_btn = st.button("🚀 Generate PDF", type="primary", use_container_width=True)

with col2:
    st.subheader("📥 Output Document")
    if generate_btn:
        content_payload = {
            "header": header,
            "date": date_str,
            "address": address,
            "subject": subject,
            "salutation": salutation,
            "paragraphs": paragraphs,
            "sign_off": sign_off,
            "sender_name": sender_name,
            "sender_title": sender_title
        }
        
        with st.spinner("Rendering PDF via Playwright..."):
            try:
                pdf_file = generate_pdf(content_payload)
                st.success("PDF generated successfully!")
                
                with open(pdf_file, "rb") as f:
                    pdf_bytes = f.read()
                    
                st.download_button(
                    label="⬇️ Download Output PDF",
                    data=pdf_bytes,
                    file_name="generated_letter.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Failed to generate PDF: {e}")
