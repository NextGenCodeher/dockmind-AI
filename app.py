import os
import fitz  # PyMuPDF
import streamlit as st
from jinja2 import Template
from playwright.sync_api import sync_playwright

# Ensure output folder exists for compiled PDFs
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. TEMPLATE PARSER & INLINE CSS ENGINE
# -----------------------------------------------------------------------------
def extract_template_styles(uploaded_file) -> str:
    """
    Parses an uploaded PDF/DOCX file to extract page layout, font sizes,
    and primary colors, returning dynamic CSS string.
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)  # Reset file pointer
        
        # Default fallback values
        font_family = "Arial, sans-serif"
        primary_color = "#111111"
        font_size = "11pt"
        line_height = "1.6"
        margin_mm = "20mm"

        # Parse uploaded PDF template attributes
        if uploaded_file.name.endswith(".pdf"):
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            if len(doc) > 0:
                page = doc[0]
                blocks = page.get_text("dict")["blocks"]
                for b in blocks:
                    if "lines" in b:
                        for line in b["lines"]:
                            for span in line["spans"]:
                                font_family = span.get("font", font_family)
                                font_size = f"{round(span.get('size', 11))}pt"
                                color_int = span.get("color", 0)
                                primary_color = f"#{color_int:06x}"
                                break
                            if font_size:
                                break

        # Build dynamic CSS injection rules
        return f"""
        @page {{
            size: A4;
            margin: {margin_mm};
        }}
        body {{
            font-family: '{font_family}', sans-serif;
            font-size: {font_size};
            line-height: {line_height};
            color: {primary_color};
            margin: 0;
            padding: 0;
        }}
        .header {{
            text-align: center;
            font-weight: bold;
            font-size: 16pt;
            margin-bottom: 25px;
            color: {primary_color};
            border-bottom: 2px solid {primary_color};
            padding-bottom: 8px;
        }}
        .date {{
            text-align: right;
            margin-bottom: 20px;
            font-weight: bold;
        }}
        .address {{
            margin-bottom: 20px;
            line-height: 1.4;
        }}
        .subject {{
            font-weight: bold;
            text-decoration: underline;
            margin-top: 15px;
            margin-bottom: 20px;
        }}
        .body-paragraph {{
            text-align: justify;
            text-indent: 30px;
            margin-bottom: 15px;
        }}
        .signature {{
            margin-top: 50px;
            float: right;
            text-align: left;
        }}
        """

    except Exception as e:
        st.warning(f"Could not extract styles from template ({e}). Using default styles.")
        return get_default_css()


def get_default_css() -> str:
    """Inline default CSS fallback string."""
    return """
    @page { size: A4; margin: 20mm; }
    body { font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.5; color: #111111; margin: 0; padding: 0; }
    .header { text-align: center; font-weight: bold; font-size: 16pt; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 8px; }
    .date { text-align: right; margin-bottom: 15px; font-weight: bold; }
    .address { margin-bottom: 20px; line-height: 1.4; }
    .subject { font-weight: bold; text-decoration: underline; margin: 15px 0; }
    .body-paragraph { text-align: justify; text-indent: 30px; margin-bottom: 12px; }
    .signature { margin-top: 40px; float: right; }
    """


# -----------------------------------------------------------------------------
# 2. PDF RENDERING ENGINE
# -----------------------------------------------------------------------------
def generate_pdf(content_data: dict, custom_css: str, output_path: str = "output/generated_doc.pdf") -> str:
    """Compiles HTML with dynamic CSS and converts to PDF via Playwright."""
    html_structure = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
      {custom_css}
    </style>
    </head>
    <body>
      <div class="header">{{{{ content.header }}}}</div>
      <div class="date"><b>Date:</b> {{{{ content.date }}}}</div>
      <div class="address">
        <b>To,</b><br>
        {{% for line in content.address.split('\\n') %}}
          {{{{ line }}}}<br>
        {{% endfor %}}
      </div>
      <div class="subject">Subject: {{{{ content.subject }}}}</div>
      <div style="margin-bottom: 15px;">{{{{ content.salutation }}}},</div>
      
      {{% for p in content.paragraphs.split('\\n\\n') %}}
        <div class="body-paragraph">{{{{ p }}}}</div>
      {{% endfor %}}
      
      <div class="signature">
        <b>{{{{ content.sender_name }}}}</b><br>
        {{{{ content.sender_title }}}}
      </div>
    </body>
    </html>
    """
    
    # Render Jinja2 HTML template
    template = Template(html_structure)
    rendered_html = template.render(content=content_data)

    # Render PDF using Chromium via Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html)
        page.pdf(path=output_path, print_background=True, format="A4")
        browser.close()

    return output_path


# -----------------------------------------------------------------------------
# 3. STREAMLIT UI DASHBOARD
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="DocMind AI - Dynamic Formatter", layout="wide")
    st.title("📄 DocMind AI: Template-Aware Document Generator")
    st.write("Upload a target PDF template to extract typography, margins, and styling onto your generated document.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Template & Document Ingestion")
        uploaded_template = st.file_uploader("Upload Sample PDF Template", type=["pdf", "docx"])
        
        # Check for uploaded template and generate corresponding CSS
        if uploaded_template:
            st.success(f"Template Loaded: `{uploaded_template.name}`")
            active_css = extract_template_styles(uploaded_template)
            with st.expander("View Dynamic Extracted CSS"):
                st.code(active_css, language="css")
        else:
            st.info("No template uploaded. Default styling active.")
            active_css = get_default_css()

        st.subheader("2. Document Content")
        header = st.text_input("Document Header / Institution Name", "G. Pulla Reddy Engineering College")
        date_str = st.text_input("Date", "05/09/2026")
        address = st.text_area("Recipient Address", "To The Head of Department,\nDepartment of CSE (AIML),\nKurnool, AP.")
        subject = st.text_input("Subject", "Submission of Project Architecture Draft for DocMind AI")
        salutation = st.text_input("Salutation", "Respected Sir/Madam")
        paragraphs = st.text_area("Body Content (Separate paragraphs with double newlines)", 
            "DocMind AI is an automated technical document synthesis platform designed to streamline writing and template formatting simultaneously.\n\n"
            "It ingests source artifacts—including code repositories, configuration files, schema files, and READMEs—ensuring all generated text remains grounded without hallucinated details."
        )
        sender_name = st.text_input("Sender Name", "Honey Amilineni")
        sender_title = st.text_input("Sender Designation", "Lead AI Engineer & Student")

    with col2:
        st.subheader("3. Document Generation & Export")
        
        if st.button("Generate & Apply Template", type="primary"):
            doc_payload = {
                "header": header,
                "date": date_str,
                "address": address,
                "subject": subject,
                "salutation": salutation,
                "paragraphs": paragraphs,
                "sender_name": sender_name,
                "sender_title": sender_title
            }
            
            with st.spinner("Extracting layout styles and compiling PDF..."):
                output_pdf = generate_pdf(doc_payload, custom_css=active_css)
                st.success("Document compiled successfully!")
                
                with open(output_pdf, "rb") as pdf_file:
                    st.download_button(
                        label="📥 Download Formatted PDF",
                        data=pdf_file,
                        file_name="DocMind_Formatted_Document.pdf",
                        mime="application/pdf"
                    )

if __name__ == "__main__":
    main()
