import os
import subprocess
import json
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
    st.warning(f"Browser setup: {e}")

st.set_page_config(page_title="DocMind AI - Chat PDF Generator", layout="centered", page_icon="💬")

st.title("💬 DocMind AI: Chat Interface")
st.caption("Upload a reference PDF and describe the changes or contents you want in plain text.")

# Default document state
if "doc_data" not in st.session_state:
    st.session_state.doc_data = {
        "header": "DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING",
        "date": "September 5, 2026",
        "address": "The Principal\nG. Pulla Reddy Engineering College\nKurnool",
        "subject": "Request for Lab Resources",
        "salutation": "Respected Sir",
        "paragraphs": "I am writing to request access to the machine learning laboratory for our research project.\n\nWe plan to run multi-node workload experiments starting next week.",
        "sign_off": "Yours faithfully",
        "sender_name": "Honey Amilineni",
        "sender_title": "Student Lead, CSE"
    }

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Upload a reference template if you'd like, or tell me what changes or content you'd like in your letter."}
    ]

# HTML Template Definition
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

def generate_pdf(content_data, output_path="generated_letter.pdf"):
    template = Template(HTML_TEMPLATE_STRING)
    rendered_html = template.render(content=content_data)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html)
        page.pdf(path=output_path, format="A4", print_background=True)
        browser.close()
    return output_path

# File Upload Sidebar / Top section
uploaded_file = st.file_uploader("📎 Upload PDF Reference Template", type=["pdf"])
if uploaded_file:
    st.info(f"Loaded reference template: `{uploaded_file.name}`")

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "pdf_path" in msg:
            with open(msg["pdf_path"], "rb") as f:
                st.download_button(
                    label="📥 Download Generated PDF",
                    data=f.read(),
                    file_name="generated_document.pdf",
                    mime="application/pdf",
                    key=msg["pdf_path"]
                )

# Chat Input
user_input = st.chat_input("E.g., Change date to Oct 10 and update subject to Machine Learning Lab Access")

if user_input:
    # Render user prompt
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Process input & render response
    with st.chat_message("assistant"):
        with st.spinner("Updating document and generating PDF..."):
            
            # Simple keyword parsing demo to update document state
            text_lower = user_input.lower()
            if "subject" in text_lower:
                st.session_state.doc_data["subject"] = user_input.replace("subject", "").strip(" :")
            if "date" in text_lower:
                st.session_state.doc_data["date"] = user_input.replace("date", "").strip(" :")
            if "body" in text_lower or "paragraph" in text_lower:
                st.session_state.doc_data["paragraphs"] = user_input

            pdf_file = generate_pdf(st.session_state.doc_data, output_path=f"output_{len(st.session_state.messages)}.pdf")
            
            response_text = "I've updated your document based on your request and rendered the new PDF!"
            st.write(response_text)
            
            with open(pdf_file, "rb") as f:
                pdf_bytes = f.read()
                st.download_button(
                    label="📥 Download Updated PDF",
                    data=pdf_bytes,
                    file_name="generated_document.pdf",
                    mime="application/pdf"
                )

            st.session_state.messages.append({
                "role": "assistant",
                "content": response_text,
                "pdf_path": pdf_file
            })
