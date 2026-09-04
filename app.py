import os
import fitz  # PyMuPDF
import streamlit as st
from markdown import markdown
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. TEMPLATE PARSER: Extracts HTML/CSS Layout from Uploaded Reference PDF
# -----------------------------------------------------------------------------
def extract_template_html_and_css(uploaded_file):
    """
    Parses the reference PDF to extract structural layout, page geometry,
    font properties, margins, and column distribution. Returns an HTML template shell.
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

        # 3. Extract Font Family & Color
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

        template_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
{css}
  </style>
</head>
<body>
  <!-- HEADER SECTION -->
  <div class="header-container">
    {{{{TITLE}}}}
    {{{{ABSTRACT}}}}
  </div>

  <!-- MAIN BODY CONTENT -->
  <div class="body-container">
    {{{{BODY_CONTENT}}}}
  </div>
</body>
</html>"""

        return template_html

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
# 2. STREAMLIT APPLICATION
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="DocMind AI - HTML Template Compiler", layout="wide")
    st.title("📄 DocMind AI: PDF Template Parser & Compiler")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Upload Reference PDF Template")
        uploaded_template = st.file_uploader("Upload Target Format Reference PDF", type=["pdf"])

        if uploaded_template:
            template_html = extract_template_html_and_css(uploaded_template)
            st.success(f"Successfully Extracted Layout Template from `{uploaded_template.name}`")
        else:
            template_html = get_default_template()
            st.info("Upload a reference PDF to extract its exact HTML/CSS structure.")

        # Show extracted HTML/CSS code for review
        with st.expander("🔍 View Extracted HTML/CSS Template Code"):
            st.code(template_html, language="html")

        st.subheader("2. Enter Your New Content")
        
        doc_title = st.text_input("Document Title", placeholder="e.g. DocMind AI Project Architecture")
        
        doc_abstract = st.text_area(
            "Abstract / Subtitle / Header Meta", 
            placeholder="e.g. Abstract or recipient info...", 
            height=90
        )
        
        user_content = st.text_area(
            "Main Content (Markdown or Raw Text)", 
            placeholder="""Enter your content here:

## 1. Introduction
Write your content paragraphs...

## 2. Methodology
* Point 1
* Point 2""", 
            height=300
        )

    with col2:
        st.subheader("3. Rendered Output")

        if st.button("Compile Content into PDF Template", type="primary"):
            if not user_content and not doc_title:
                st.warning("Please provide title or content to compile.")
            else:
                with st.spinner("Injecting content into extracted HTML template..."):
                    # Process markdown into HTML tags
                    body_html = markdown(user_content) if user_content else ""
                    abstract_html = f'<div class="abstract-box">{markdown(doc_abstract)}</div>' if doc_abstract else ""
                    title_html = f"<h1>{doc_title}</h1>" if doc_title else ""

                    # Inject user content into extracted HTML template slots
                    final_html = template_html.replace("{{TITLE}}", title_html)\
                                              .replace("{{ABSTRACT}}", abstract_html)\
                                              .replace("{{BODY_CONTENT}}", body_html)

                    # Render PDF with Playwright engine
                    output_path = "output/Formatted_Document.pdf"
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                        page.set_content(final_html)
                        page.pdf(path=output_path, print_background=True, format="A4")
                        browser.close()

                    st.success("Compilation Complete!")
                    with open(output_path, "rb") as f:
                        st.download_button("📥 Download Generated PDF", f, file_name="Formatted_Document.pdf", mime="application/pdf")

                    with st.expander("🌐 View Synthesized HTML Code"):
                        st.code(final_html, language="html")

if __name__ == "__main__":
    main()
