import os
import fitz  # PyMuPDF
import streamlit as st
from markdown import markdown
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. DYNAMIC CONTENT EXTRACTION FROM UPLOADED PDF
# -----------------------------------------------------------------------------
def extract_content_and_style_from_pdf(uploaded_file):
    """
    Parses an uploaded PDF template to dynamically extract:
    1. Visual geometry & CSS rules (margins, columns, font size).
    2. Document Title (from top/largest text block).
    3. Main Body Content (formatted into Markdown headers & paragraphs).
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        if len(doc) == 0:
            return get_default_css(), "", "", ""

        # Analyze layout geometry from first page
        page = doc[0]
        rect = page.rect
        blocks = page.get_text("blocks")
        
        # Detect multi-column layout
        x_centers = [b[0] for b in blocks if len(b) >= 4]
        is_two_column = False
        if x_centers:
            midpoint = rect.width / 2
            left = [x for x in x_centers if x < midpoint - 25]
            right = [x for x in x_centers if x > midpoint + 25]
            if len(left) > 0 and len(right) > 0:
                is_two_column = True

        column_css = "column-count: 2; column-gap: 18pt;" if is_two_column else "column-count: 1;"

        css = f"""
        @page {{ size: A4; margin: 18mm 15mm; }}
        body {{ font-family: 'Times New Roman', serif; font-size: 10.5pt; line-height: 1.4; color: #000; margin: 0; }}
        .header-container {{ width: 100%; text-align: center; margin-bottom: 14pt; }}
        .body-container {{ {column_css} text-align: justify; }}
        h1 {{ font-size: 18pt; text-align: center; margin-bottom: 8pt; }}
        h2 {{ font-size: 11pt; font-weight: bold; text-transform: uppercase; border-bottom: 1px solid #000; margin-top: 12pt; margin-bottom: 4pt; break-after: avoid; }}
        h3 {{ font-size: 10pt; font-weight: bold; margin-top: 8pt; margin-bottom: 3pt; break-after: avoid; }}
        p {{ margin-bottom: 6pt; text-indent: 10pt; }}
        ul, ol {{ margin-bottom: 6pt; padding-left: 14pt; }}
        """

        # Dynamic Content Extraction across all pages
        extracted_blocks = []
        for p in doc:
            p_blocks = p.get_text("blocks")
            for b in p_blocks:
                # b[4] contains the block text
                text = b[4].strip()
                if text:
                    extracted_blocks.append(text)

        if not extracted_blocks:
            return css, "", "", ""

        # First block is treated dynamically as Title
        extracted_title = extracted_blocks[0].replace('\n', ' ')
        
        # Second block is treated as Abstract / Header info (if short or contains keywords)
        extracted_abstract = ""
        body_start_idx = 1
        
        if len(extracted_blocks) > 1 and ("abstract" in extracted_blocks[1].lower() or len(extracted_blocks[1]) < 300):
            extracted_abstract = extracted_blocks[1]
            body_start_idx = 2

        # Convert remaining blocks into Markdown format dynamically
        body_blocks = extracted_blocks[body_start_idx:]
        markdown_body = []

        for block in body_blocks:
            lines = block.split('\n')
            # Check if short block or uppercase line represents a Section Heading
            if len(lines) == 1 and (len(lines[0]) < 60 or lines[0].isupper()):
                markdown_body.append(f"\n## {lines[0]}\n")
            else:
                markdown_body.append(block)

        extracted_body_markdown = "\n\n".join(markdown_body)

        return css, extracted_title, extracted_abstract, extracted_body_markdown

    except Exception as e:
        st.error(f"Error reading uploaded PDF: {e}")
        return get_default_css(), "", "", ""


def get_default_css() -> str:
    return """
    @page { size: A4; margin: 18mm 15mm; }
    body { font-family: 'Times New Roman', serif; font-size: 10.5pt; line-height: 1.4; color: #000; }
    .header-container { width: 100%; text-align: center; margin-bottom: 14pt; }
    .body-container { column-count: 1; text-align: justify; }
    h1 { font-size: 18pt; text-align: center; }
    h2 { font-size: 11pt; font-weight: bold; border-bottom: 1px solid #000; margin-top: 12pt; margin-bottom: 4pt; }
    """


# -----------------------------------------------------------------------------
# 2. STREAMLIT INTERFACE WITH DYNAMIC TEMPLATE AUTO-EXTRACTION
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="DocMind AI - Dynamic Template Extractor", layout="wide")
    st.title("📄 DocMind AI: Universal Template & Content Extractor")

    # Initialize state variables
    if "doc_title" not in st.session_state:
        st.session_state.doc_title = ""
    if "doc_abstract" not in st.session_state:
        st.session_state.doc_abstract = ""
    if "doc_content" not in st.session_state:
        st.session_state.doc_content = ""
    if "uploaded_filename" not in st.session_state:
        st.session_state.uploaded_filename = ""

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Target PDF Template")
        uploaded_template = st.file_uploader("Upload Any Sample PDF Template", type=["pdf"])

        if uploaded_template:
            # Check if a new file was uploaded
            if st.session_state.uploaded_filename != uploaded_template.name:
                active_css, title, abstract, content = extract_content_and_style_from_pdf(uploaded_template)
                
                # Dynamically set session state directly from uploaded PDF
                st.session_state.doc_title = title
                st.session_state.doc_abstract = abstract
                st.session_state.doc_content = content
                st.session_state.uploaded_filename = uploaded_template.name
                st.rerun()
            else:
                active_css, _, _, _ = extract_content_and_style_from_pdf(uploaded_template)

            st.success(f"Loaded & Extracted: `{uploaded_template.name}`")
        else:
            active_css = get_default_css()
            st.info("Upload any sample PDF template to automatically extract its layout and content.")

        st.subheader("2. Document Content (Extracted Dynamically)")

        # Form controls backed by dynamic session state
        title_val = st.text_input(
            "Document Title / Header", 
            value=st.session_state.doc_title,
            placeholder="Upload a PDF or enter title..."
        )
        
        abstract_val = st.text_area(
            "Abstract / Subtitle / Header Block", 
            value=st.session_state.doc_abstract, 
            height=100,
            placeholder="Upload a PDF or enter abstract..."
        )
        
        content_val = st.text_area(
            "Main Document Content (Markdown Format)", 
            value=st.session_state.doc_content, 
            height=320,
            placeholder="Upload a PDF or paste document content..."
        )

    with col2:
        st.subheader("3. Rendered PDF Output")

        if st.button("Generate Formatted PDF", type="primary"):
            if not title_val and not content_val:
                st.warning("Please upload a document or enter text content before generating.")
            else:
                with st.spinner("Rendering document matching target template geometry..."):
                    body_html = markdown(content_val) if content_val else ""
                    abstract_html = markdown(abstract_val) if abstract_val else ""

                    full_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                      <meta charset="UTF-8">
                      <style>{active_css}</style>
                    </head>
                    <body>
                      <div class="header-container">
                        {f'<h1>{title_val}</h1>' if title_val else ''}
                        {f'<div class="abstract-box">{abstract_html}</div>' if abstract_html else ''}
                      </div>
                      <div class="body-container">
                        {body_html}
                      </div>
                    </body>
                    </html>
                    """

                    output_path = "output/Formatted_Document.pdf"
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page()
                        page.set_content(full_html)
                        page.pdf(path=output_path, print_background=True, format="A4")
                        browser.close()

                    st.success("PDF Compilation Successful!")
                    with open(output_path, "rb") as f:
                        st.download_button("📥 Download Formatted PDF", f, file_name="Formatted_Document.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()
