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
def extract_template_html_and_css(uploaded_file):
    """
    Parses the reference PDF to extract structural layout, page geometry,
    font properties, precise margin calculations, and heading styles.
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        if len(doc) == 0:
            return get_default_template()

        page = doc[0]
        rect = page.rect # Total page dimensions (width, height)
        
        # 1. Extract Spans with Font Sizes, Weights, Colors, and Coordinates
        spans = []
        page_dict = page.get_text("dict")
        for b in page_dict.get("blocks", []):
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        text = span.get("text", "").strip()
                        if text:
                            # Convert integer color to HEX string
                            color_int = span.get("color", 0)
                            r = (color_int >> 16) & 255
                            g = (color_int >> 8) & 255
                            b_val = color_int & 255
                            hex_color = f"#{r:02x}{g:02x}{b_val:02x}"
                            
                            spans.append({
                                "text": text,
                                "size": round(span.get("size", 10), 1),
                                "font": span.get("font", "Times New Roman"),
                                "color": hex_color,
                                "bbox": span.get("bbox") # (x0, y0, x1, y1)
                            })

        if not spans:
            return get_default_template()

        # 2. Precise Page Margins (Bounding box around actual content)
        min_x = min(s["bbox"][0] for s in spans)
        min_y = min(s["bbox"][1] for s in spans)
        max_x = max(s["bbox"][2] for s in spans)
        max_y = max(s["bbox"][3] for s in spans)

        margin_top = f"{max(10, round(min_y, 1))}pt"
        margin_bottom = f"{max(10, round(rect.height - max_y, 1))}pt"
        margin_left = f"{max(10, round(min_x, 1))}pt"
        margin_right = f"{max(10, round(rect.width - max_x, 1))}pt"

        # 3. Detect Dominant Font Family & Primary Text Color
        fonts = [s["font"] for s in spans]
        font_family = max(set(fonts), key=fonts.count) if fonts else "Times New Roman, serif"
        
        # Clean up font names (e.g., "ABCDE+Calibri-Bold" -> "Calibri")
        font_clean = font_family.split("+")[-1].split("-")[0].replace(",", "")
        
        colors = [s["color"] for s in spans if s["color"] != "#ffffff"]
        primary_color = max(set(colors), key=colors.count) if colors else "#000000"

        # 4. Extract Title, Heading (H2), and Body Font Sizes
        sorted_sizes = sorted(list(set(s["size"] for s in spans)), reverse=True)
        title_size = f"{sorted_sizes[0]}pt" if len(sorted_sizes) > 0 else "18pt"
        h2_size = f"{sorted_sizes[1]}pt" if len(sorted_sizes) > 1 else "12pt"
        body_size = f"{sorted_sizes[-1]}pt" if len(sorted_sizes) > 2 else "10pt"

        # 5. Detect Multi-Column Layout
        midpoint = rect.width / 2
        left_side = [s for s in spans if s["bbox"][2] < midpoint - 15]
        right_side = [s for s in spans if s["bbox"][0] > midpoint + 15]
        is_two_column = len(left_side) > 3 and len(right_side) > 3

        column_css = "column-count: 2; column-gap: 16pt; column-fill: balance;" if is_two_column else "column-count: 1;"

        css = f"""
        @page {{
            size: A4;
            margin: {margin_top} {margin_right} {margin_bottom} {margin_left};
        }}
        body {{
            font-family: '{font_clean}', 'Times New Roman', serif;
            font-size: {body_size};
            line-height: 1.35;
            color: {primary_color};
            margin: 0;
            padding: 0;
            background: #ffffff;
        }}
        .header-container {{
            width: 100%;
            text-align: center;
            margin-bottom: 12pt;
        }}
        .header-container h1 {{
            font-size: {title_size};
            font-weight: bold;
            margin: 0 0 6pt 0;
            line-height: 1.2;
            color: {primary_color};
        }}
        .abstract-box {{
            text-align: justify;
            font-size: {body_size};
            margin: 8pt 0;
            padding: 6pt 8pt;
            background-color: #f9f9f9;
            border-left: 3px solid {primary_color};
        }}
        .body-container {{
            {column_css}
            text-align: justify;
        }}
        h2 {{
            font-size: {h2_size};
            font-weight: bold;
            text-transform: uppercase;
            color: {primary_color};
            border-bottom: 1px solid {primary_color};
            margin-top: 10pt;
            margin-bottom: 4pt;
            padding-bottom: 2pt;
            break-after: avoid;
        }}
        h3 {{
            font-size: {body_size};
            font-weight: bold;
            color: {primary_color};
            margin-top: 6pt;
            margin-bottom: 2pt;
            break-after: avoid;
        }}
        p {{
            margin: 0 0 4pt 0;
        }}
        ul, ol {{
            margin: 0 0 6pt 0;
            padding-left: 12pt;
        }}
        li {{
            margin-bottom: 2pt;
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
