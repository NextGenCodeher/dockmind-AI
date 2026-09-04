import os
import fitz  # PyMuPDF
import streamlit as st
from markdown import markdown
from jinja2 import Template
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. UNIVERSAL TEMPLATE ANALYSIS (Works for IEEE, College Reports, Letters, etc.)
# -----------------------------------------------------------------------------
def analyze_any_pdf_template(uploaded_file) -> str:
    """
    Scans any uploaded PDF template (college report, IEEE paper, letterhead, lab manual)
    and extracts page margins, font family, headings hierarchy, and column count.
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if len(doc) == 0:
            return get_universal_fallback_css()

        page = doc[0]
        rect = page.rect
        
        # 1. Detect margins from text bounding boxes
        blocks = page.get_text("blocks")
        if blocks:
            min_x = min(b[0] for b in blocks)
            min_y = min(b[1] for b in blocks)
            max_x = max(b[2] for b in blocks)
            max_y = max(b[3] for b in blocks)
            
            margin_left = f"{round(min_x, 1)}pt"
            margin_top = f"{round(min_y, 1)}pt"
            margin_right = f"{round(rect.width - max_x, 1)}pt"
            margin_bottom = f"{round(rect.height - max_y, 1)}pt"
        else:
            margin_left, margin_top, margin_right, margin_bottom = "18mm", "18mm", "18mm", "18mm"

        # 2. Check for multi-column layout
        x_centers = [b[0] for b in blocks if len(b) >= 4]
        is_two_column = False
        if x_centers:
            midpoint = rect.width / 2
            left_blocks = [x for x in x_centers if x < midpoint - 20]
            right_blocks = [x for x in x_centers if x > midpoint + 20]
            if len(left_blocks) > 0 and len(right_blocks) > 0:
                is_two_column = True

        # 3. Extract Font Hierarchy & Colors
        font_family = "Times New Roman, serif"
        primary_color = "#000000"
        font_sizes = []

        dict_blocks = page.get_text("dict")["blocks"]
        for b in dict_blocks:
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        font_name = span.get("font", "")
                        if font_name:
                            font_family = font_name
                        font_sizes.append(span.get("size", 11))
                        color_int = span.get("color", 0)
                        if color_int > 0 and primary_color == "#000000":
                            primary_color = f"#{color_int:06x}"

        # Estimate header vs body size from font distributions
        body_size = round(sorted(font_sizes)[len(font_sizes) // 2]) if font_sizes else 11
        h1_size = round(max(font_sizes)) if font_sizes else 18
        h2_size = round(body_size * 1.25)

        column_css = "column-count: 2; column-gap: 18px;" if is_two_column else "column-count: 1;"

        return f"""
        @page {{
            size: A4;
            margin: {margin_top} {margin_right} {margin_bottom} {margin_left};
        }}
        body {{
            font-family: '{font_family}', Arial, sans-serif;
            font-size: {body_size}pt;
            line-height: 1.45;
            color: {primary_color};
            margin: 0;
            padding: 0;
        }}
        .document-container {{
            {column_css}
            text-align: justify;
        }}
        h1 {{
            font-size: {h1_size}pt;
            text-align: center;
            color: {primary_color};
            margin-bottom: 12px;
            column-span: all; /* Title/H1 spans full page even in 2-column mode */
        }}
        h2 {{
            font-size: {h2_size}pt;
            color: {primary_color};
            border-bottom: 1px solid #ccc;
            margin-top: 16px;
            margin-bottom: 8px;
            break-after: avoid;
        }}
        h3 {{
            font-size: {body_size + 1}pt;
            color: {primary_color};
            margin-top: 12px;
            margin-bottom: 6px;
            break-after: avoid;
        }}
        p {{
            margin-top: 0;
            margin-bottom: 8px;
            text-indent: 10px;
        }}
        ul, ol {{
            margin-top: 0;
            margin-bottom: 8px;
            padding-left: 20px;
        }}
        blockquote {{
            font-style: italic;
            margin: 10px 0;
            padding-left: 15px;
            border-left: 3px solid #ccc;
        }}
        """

    except Exception as e:
        st.warning(f"Could not parse template details ({e}). Using universal default style.")
        return get_universal_fallback_css()


def get_universal_fallback_css() -> str:
    """Universal standard document fallback layout."""
    return """
    @page { size: A4; margin: 20mm 15mm; }
    body { font-family: 'Times New Roman', serif; font-size: 11pt; line-height: 1.5; color: #111; }
    .document-container { column-count: 1; text-align: justify; }
    h1 { font-size: 20pt; text-align: center; margin-bottom: 15px; column-span: all; }
    h2 { font-size: 13pt; border-bottom: 1px solid #ccc; margin-top: 16px; margin-bottom: 8px; break-after: avoid; }
    h3 { font-size: 11.5pt; margin-top: 12px; margin-bottom: 6px; break-after: avoid; }
    p { margin-bottom: 8px; text-indent: 12px; }
    """


# -----------------------------------------------------------------------------
# 2. UNIVERSAL COMPILER
# -----------------------------------------------------------------------------
def compile_any_document(raw_markdown_content: str, dynamic_css: str, output_path: str = "output/formatted_document.pdf") -> str:
    """Converts any structured markdown content into the target template style."""
    
    # Converts standard Markdown (#, ##, ###, lists, text) to HTML
    html_content = markdown(raw_markdown_content)

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
      {dynamic_css}
    </style>
    </head>
    <body>
      <div class="document-container">
        {html_content}
      </div>
    </body>
    </html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(full_html)
        page.pdf(path=output_path, print_background=True, format="A4")
        browser.close()

    return output_path


# -----------------------------------------------------------------------------
# 3. STREAMLIT APPLICATION
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Universal Document Formatter", layout="wide")
    st.title("📄 DocMind AI: Universal Template Formatter")
    st.write("Upload **any** sample PDF (College Lab Manual, Thesis Report, IEEE Paper, or Official Letter) and paste your content below. The layout will adapt automatically.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Upload Sample PDF Template")
        uploaded_template = st.file_uploader("Upload Target Template PDF", type=["pdf"])
        
        if uploaded_template:
            st.success(f"Template Loaded: `{uploaded_template.name}`")
            active_css = analyze_any_pdf_template(uploaded_template)
            with st.expander("View Auto-Extracted Rules"):
                st.code(active_css, language="css")
        else:
            st.info("No template uploaded. Default single-column document layout active.")
            active_css = get_universal_fallback_css()

        st.subheader("2. Provide Document Content")
        st.caption("Use standard Markdown formatting (# Title, ## Section Header, ### Subsection, Bullet points)")
        
        user_content = st.text_area(
            "Document Content",
            height=400,
            value="""# College Project Report: Automated Document Synthesis

## 1. Introduction
This project aims to automate document layout compliance across various academic and professional domains. By parsing PDF templates dynamically, the application extracts structural attributes and applies them to user-provided markdown content.

## 2. Objectives
* Automate font and margin extraction from arbitrary PDF samples.
* Support single-column and multi-column document reflowing.
* Provide clean, reproducible PDF outputs via browser rendering engines.

## 3. Implementation Details
The backend utilizes PyMuPDF for layout extraction and Playwright for headless HTML-to-PDF rendering.

### 3.1 Template Analysis
The analysis module measures text element bounds to infer margins and computes font size histograms to identify header hierarchies.

## 4. Conclusion
The proposed framework eliminates manual document re-formatting tasks across diverse institutional templates."""
        )

    with col2:
        st.subheader("3. Rendered Output")
        
        if st.button("Format Document & Export PDF", type="primary"):
            with st.spinner("Analyzing template layout and compiling PDF..."):
                output_pdf = compile_any_document(user_content, active_css)
                st.success("Document successfully compiled!")
                
                with open(output_pdf, "rb") as pdf_file:
                    st.download_button(
                        label="📥 Download Formatted PDF",
                        data=pdf_file,
                        file_name="Formatted_Document.pdf",
                        mime="application/pdf"
                    )

if __name__ == "__main__":
    main()
