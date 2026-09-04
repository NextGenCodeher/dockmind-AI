import os
import re
import fitz  # PyMuPDF
import streamlit as st
from markdown import markdown
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. TEMPLATE PARSER: Extracts HTML/CSS Layout Shell from Uploaded PDF
# -----------------------------------------------------------------------------
def extract_template_html_and_css(uploaded_file):
    """
    Parses the reference PDF to extract structural layout, page geometry,
    font properties, margins, and column distribution into an HTML template shell.
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        if len(doc) == 0:
            return get_default_template()

        page = doc[0]
        rect = page.rect
        blocks = page.get_text("blocks")

        # 1. Extract Margins
        if blocks:
            min_x = min(b[0] for b in blocks)
            min_y = min(b[1] for b in blocks)
            max_x = max(b[2] for b in blocks)
            max_y = max(b[3] for b in blocks)

            margin_left = f"{max(12, round(min_x, 1))}pt"
            margin_top = f"{max(15, round(min_y, 1))}pt"
            margin_right = f"{max(12, round(rect.width - max_x, 1))}pt"
            margin_bottom = f"{max(15, round(rect.height - max_y, 1))}pt"
        else:
            margin_left, margin_top, margin_right, margin_bottom = "18mm", "18mm", "18mm", "18mm"

        # 2. Detect Multi-Column Layout
        x_centers = [b[0] for b in blocks if len(b) >= 4]
        is_two_column = False
        if x_centers:
            midpoint = rect.width / 2
            left = [x for x in x_centers if x < midpoint - 25]
            right = [x for x in x_centers if x > midpoint + 25]
            if len(left) > 0 and len(right) > 0:
                is_two_column = True

        column_css = "column-count: 2; column-gap: 18pt; column-fill: balance;" if is_two_column else "column-count: 1;"

        # 3. Extract Font Family & Primary Color
        font_family = "Times New Roman, serif"
        primary_color = "#000000"
        
        dict_blocks = page.get_text("dict")["blocks"]
        for b in dict_blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        font_name = span.get("font", "")
                        if font_name:
                            font_family = font_name
                        color_int = span.get("color", 0)
                        if color_int > 0 and primary_color == "#000000":
                            primary_color = f"#{color_int:06x}"

        css = f"""
        @page {{
            size: A4;
            margin: {margin_top} {margin_right} {margin_bottom} {margin_left};
        }}
        body {{
            font-family: '{font_family}', 'Times New Roman', serif;
            font-size: 10pt;
            line-height: 1.4;
            color: {primary_color};
            margin: 0;
            padding: 0;
            background: #ffffff;
        }}
        .header-container {{
            width: 100%;
            text-align: center;
            margin-bottom: 16pt;
        }}
        .header-container h1 {{
            font-size: 18pt;
            font-weight: bold;
            margin: 0 0 8pt 0;
            line-height: 1.25;
            color: {primary_color};
        }}
        .abstract-box {{
            text-align: justify;
            font-size: 10pt;
            margin: 10pt 0;
            padding: 8pt 10pt;
            background-color: #fcfcfc;
            border-left: 3px solid {primary_color};
        }}
        .body-container {{
            {column_css}
            text-align: justify;
        }}
        h2 {{
            font-size: 11pt;
            font-weight: bold;
            text-transform: uppercase;
            color: {primary_color};
            border-bottom: 1px solid {primary_color};
            margin-top: 12pt;
            margin-bottom: 4pt;
            padding-bottom: 2pt;
            break-after: avoid;
        }}
        h3 {{
            font-size: 10pt;
            font-weight: bold;
            color: {primary_color};
            margin-top: 8pt;
            margin-bottom: 3pt;
            break-after: avoid;
        }}
        p {{
            margin: 0 0 6pt 0;
            text-indent: 10pt;
        }}
        ul, ol {{
            margin: 0 0 6pt 0;
            padding-left: 14pt;
        }}
        li {{
            margin-bottom: 3pt;
            text-indent: 0;
        }}
        """

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
{css}
  </style>
</head>
<body>
  <div class="header-container">
    {{{{TITLE}}}}
    {{{{ABSTRACT}}}}
  </div>
  <div class="body-container">
    {{{{BODY_CONTENT}}}}
  </div>
</body>
</html>"""

    except Exception as e:
        st.error(f"Error analyzing reference PDF template: {e}")
        return get_default_template()


def get_default_template():
    return """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    @page { size: A4; margin: 18mm 15mm; }
    body { font-family: 'Times New Roman', serif; font-size: 10pt; line-height: 1.4; color: #000; }
    .header-container { width: 100%; text-align: center; margin-bottom: 16pt; }
    .body-container { column-count: 2; column-gap: 18pt; text-align: justify; }
    h1 { font-size: 18pt; text-align: center; margin-bottom: 8pt; }
    h2 { font-size: 11pt; font-weight: bold; border-bottom: 1px solid #000; margin-top: 12pt; margin-bottom: 4pt; break-after: avoid; }
    h3 { font-size: 10pt; font-weight: bold; margin-top: 8pt; margin-bottom: 3pt; break-after: avoid; }
    p { margin-bottom: 6pt; text-indent: 10pt; }
    ul, ol { margin-bottom: 6pt; padding-left: 14pt; }
  </style>
</head>
<body>
  <div class="header-container">
    {{TITLE}}
    {{ABSTRACT}}
  </div>
  <div class="body-container">
    {{BODY_CONTENT}}
  </div>
</body>
</html>"""


# -----------------------------------------------------------------------------
# 2. CHAT CONTENT PARSER (Extracts Title, Abstract, Body from Single Input)
# -----------------------------------------------------------------------------
def parse_chat_content(user_message: str):
    """
    Parses a single prompt to isolate title, abstract, and body markdown.
    """
    title = ""
    abstract = ""
    body = user_message

    # 1. Look for explicit Markdown Title (# Title) or Title: prefix
    title_match = re.search(r"^(?:#\s+|(?:Title:\s*))([^\n]+)", user_message, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()
        # Remove matched title line from body
        body = user_message.replace(title_match.group(0), "", 1).strip()

    # 2. Look for explicit Abstract section
    abstract_match = re.search(r"Abstract:\s*([^\n]+(?:\n[^\n]+)*?)(?=\n\n|\n#|$)", body, re.IGNORECASE)
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        body = body.replace(abstract_match.group(0), "", 1).strip()

    return title, abstract, body


# -----------------------------------------------------------------------------
# 3. STREAMLIT CHAT APPLICATION
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="DocMind AI Chat Formatter", layout="wide")
    st.title("💬 DocMind AI: Chat-Driven Document Compiler")

    # Initialize chat history & template state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Upload your target reference PDF in the sidebar, then paste or type your document content directly into the chat below!"}
        ]
    if "template_html" not in st.session_state:
        st.session_state.template_html = get_default_template()

    # Sidebar for uploading the formatting template
    with st.sidebar:
        st.header("1. Upload Formatting Template")
        uploaded_file = st.file_uploader("Upload Sample PDF Template", type=["pdf"])
        if uploaded_file:
            st.session_state.template_html = extract_template_html_and_css(uploaded_file)
            st.success(f"Layout template extracted from `{uploaded_file.name}`")
            
        with st.expander("🔍 View Active HTML/CSS Shell"):
            st.code(st.session_state.template_html, language="html")

    # Display Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "pdf_path" in msg and os.path.exists(msg["pdf_path"]):
                with open(msg["pdf_path"], "rb") as f:
                    st.download_button(
                        label="📥 Download Formatted PDF",
                        data=f,
                        file_name=os.path.basename(msg["pdf_path"]),
                        mime="application/pdf",
                        key=msg["pdf_path"]
                    )

    # Single Chat Input
    if prompt := st.chat_input("Type or paste your entire document content here..."):
        # Record user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate Assistant Response
        with st.chat_message("assistant"):
            with st.spinner("Synthesizing content into target PDF layout..."):
                title, abstract, body_markdown = parse_chat_content(prompt)
                
                body_html = markdown(body_markdown) if body_markdown else ""
                abstract_html = f'<div class="abstract-box"><strong>Abstract:</strong> {markdown(abstract)}</div>' if abstract else ""
                title_html = f"<h1>{title}</h1>" if title else ""

                final_html = st.session_state.template_html.replace("{{TITLE}}", title_html)\
                                                           .replace("{{ABSTRACT}}", abstract_html)\
                                                           .replace("{{BODY_CONTENT}}", body_html)

                pdf_filename = f"output/Document_{len(st.session_state.messages)}.pdf"
                
                # Render HTML to PDF
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.set_content(final_html)
                    page.pdf(path=pdf_filename, print_background=True, format="A4")
                    browser.close()

                response_text = f"✅ **Document Formatted Successfully!**\n\nI parsed your content into the reference template structure."
                st.markdown(response_text)
                
                with open(pdf_filename, "rb") as f:
                    st.download_button(
                        label="📥 Download Formatted PDF",
                        data=f,
                        file_name="Formatted_Document.pdf",
                        mime="application/pdf"
                    )

                # Save assistant response to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "pdf_path": pdf_filename
                })

if __name__ == "__main__":
    main()
