import os
import fitz  # PyMuPDF
import streamlit as st
from markdown import markdown
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# 1. ADVANCED TEMPLATE PARSER (Extracts Structural Spacing & Layout Constraints)
# -----------------------------------------------------------------------------
def analyze_template_and_build_css(uploaded_file) -> str:
    """
    Parses any target PDF template to extract layout structure, font families,
    font sizes, colors, and margin geometry.
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if len(doc) == 0:
            return get_universal_css()

        page = doc[0]
        rect = page.rect
        
        # 1. Extract Page Margins
        blocks = page.get_text("blocks")
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

        # 2. Check for Multi-Column Document Layout
        x_centers = [b[0] for b in blocks if len(b) >= 4]
        is_two_column = False
        if x_centers:
            midpoint = rect.width / 2
            left_blocks = [x for x in x_centers if x < midpoint - 25]
            right_blocks = [x for x in x_centers if x > midpoint + 25]
            if len(left_blocks) > 0 and len(right_blocks) > 0:
                is_two_column = True

        # 3. Extract Font Family & Color Palette
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
                        font_sizes.append(span.get("size", 10))
                        color_int = span.get("color", 0)
                        if color_int > 0 and primary_color == "#000000":
                            primary_color = f"#{color_int:06x}"

        body_size = round(sorted(font_sizes)[len(font_sizes) // 2]) if font_sizes else 10
        h1_size = round(max(font_sizes)) if font_sizes else 18
        h2_size = round(body_size * 1.2)

        column_css = """
            column-count: 2;
            column-gap: 20pt;
            column-fill: balance;
        """ if is_two_column else "column-count: 1;"

        return f"""
        @page {{
            size: A4;
            margin: {margin_top} {margin_right} {margin_bottom} {margin_left};
        }}
        body {{
            font-family: '{font_family}', 'Times New Roman', serif;
            font-size: {body_size}pt;
            line-height: 1.4;
            color: {primary_color};
            margin: 0;
            padding: 0;
            background: #ffffff;
        }}
        
        /* FULL-WIDTH HEADER SECTION (Title, Authors, Abstract) */
        .header-container {{
            width: 100%;
            text-align: center;
            margin-bottom: 18pt;
            border-bottom: 1px solid #ddd;
            padding-bottom: 12pt;
        }}
        .header-container h1 {{
            font-size: {h1_size}pt;
            font-weight: bold;
            margin: 0 0 10pt 0;
            line-height: 1.25;
            color: {primary_color};
        }}
        .abstract-box {{
            text-align: justify;
            font-size: {body_size}pt;
            margin: 10pt 0;
            padding: 8pt 12pt;
            background-color: #fcfcfc;
            border-left: 3px solid {primary_color};
        }}

        /* MULTI-COLUMN BODY CONTENT */
        .body-container {{
            {column_css}
            text-align: justify;
        }}
        h2 {{
            font-size: {h2_size}pt;
            font-weight: bold;
            text-transform: uppercase;
            color: {primary_color};
            border-bottom: 1px solid #000;
            margin-top: 14pt;
            margin-bottom: 6pt;
            padding-bottom: 2pt;
            break-after: avoid;
            page-break-after: avoid;
        }}
        h3 {{
            font-size: {body_size + 1}pt;
            font-weight: bold;
            color: {primary_color};
            margin-top: 10pt;
            margin-bottom: 4pt;
            break-after: avoid;
            page-break-after: avoid;
        }}
        p {{
            margin: 0 0 6pt 0;
            text-indent: 10pt;
        }}
        ul, ol {{
            margin: 0 0 8pt 0;
            padding-left: 16pt;
        }}
        li {{
            margin-bottom: 3pt;
            text-indent: 0;
        }}
        strong {{
            color: #000;
        }}
        """

    except Exception as e:
        st.warning(f"Template analysis warning ({e}). Using standard academic formatting.")
        return get_universal_css()


def get_universal_css() -> str:
    """Fallback CSS for academic and institutional documents."""
    return """
    @page { size: A4; margin: 18mm 15mm; }
    body { font-family: 'Times New Roman', serif; font-size: 10pt; line-height: 1.35; color: #000; }
    .header-container { width: 100%; text-align: center; margin-bottom: 16pt; }
    .header-container h1 { font-size: 18pt; font-weight: bold; margin-bottom: 8pt; }
    .abstract-box { text-align: justify; margin: 10pt 0; padding: 6pt 10pt; background: #fafafa; border-left: 3px solid #000; }
    .body-container { column-count: 2; column-gap: 18pt; text-align: justify; }
    h2 { font-size: 11pt; text-transform: uppercase; border-bottom: 1px solid #000; margin-top: 12pt; margin-bottom: 6pt; break-after: avoid; }
    h3 { font-size: 10pt; font-weight: bold; margin-top: 8pt; margin-bottom: 4pt; break-after: avoid; }
    p { margin-bottom: 6pt; text-indent: 10pt; }
    ul, ol { margin-bottom: 6pt; padding-left: 14pt; }
    """


# -----------------------------------------------------------------------------
# 2. DOCUMENT COMPILER (Splits Header & Body for Flawless Reflowing)
# -----------------------------------------------------------------------------
def compile_formatted_pdf(doc_title: str, abstract_text: str, body_markdown: str, css_styles: str, output_filename: str = "output/Formatted_Document.pdf") -> str:
    """Converts structured content into HTML and renders it to PDF using Playwright."""
    
    # Render abstract & body markdown to clean HTML
    abstract_html = markdown(abstract_text) if abstract_text else ""
    body_html = markdown(body_markdown)

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        {css_styles}
      </style>
    </head>
    <body>
      <!-- Header spans 100% width -->
      <div class="header-container">
        <h1>{doc_title}</h1>
        {f'<div class="abstract-box"><strong>Abstract:</strong> {abstract_html}</div>' if abstract_html else ''}
      </div>

      <!-- Main content reflows smoothly into target column structure -->
      <div class="body-container">
        {body_html}
      </div>
    </body>
    </html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(full_html)
        page.pdf(path=output_filename, print_background=True, format="A4")
        browser.close()

    return output_filename


# -----------------------------------------------------------------------------
# 3. STREAMLIT INTERFACE
# -----------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="DocMind AI: Template Document Formatter", layout="wide")
    st.title("📄 DocMind AI: Template Document Formatter")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. Target Sample PDF Template")
        uploaded_template = st.file_uploader("Upload Sample PDF (IEEE, College Report, etc.)", type=["pdf"])
        
        if uploaded_template:
            st.success(f"Loaded Template: `{uploaded_template.name}`")
            active_css = analyze_template_and_build_css(uploaded_template)
        else:
            st.info("No template uploaded. Default academic multi-column layout active.")
            active_css = get_universal_css()

        st.subheader("2. Document Content")
        
        title_input = st.text_input(
            "Document Title",
            "CodePulse AI: Automated Codebase Refactoring & Architecture Health Platform"
        )
        
        abstract_input = st.text_area(
            "Abstract & Keywords",
            height=120,
            value="Maintaining legacy codebases and conducting thorough code reviews consumes immense engineering bandwidth. Developers frequently spend up to 40% of their time manually identifying anti-patterns, tracing dependency bottlenecks, and checking compliance against evolving coding standards. CodePulse AI is an agentic codebase analysis and refactoring platform that evaluates full-stack repositories for architectural integrity and performance.\n\n**Keywords:** Codebase Analysis, Multi-Agent Orchestration, Graph RAG, AST Parsing, Code Refactoring, Vector Database, CodePulse AI."
        )

        body_markdown_input = st.text_area(
            "Main Document Content (Markdown)",
            height=320,
            value="""## 1. Problem Statement
Maintaining legacy codebases and conducting thorough code reviews consumes immense engineering bandwidth. Developers frequently spend up to 40% of their time manually identifying anti-patterns, tracing dependency bottlenecks, and checking compliance against evolving coding standards. Standard static analysis tools flag syntax errors but lack architectural context, while generic AI coding assistants offer isolated snippet suggestions without understanding system-wide dependencies.

## 2. Proposed Solution
CodePulse AI is an agentic codebase analysis and refactoring platform that evaluates full-stack repositories for architectural integrity and performance.

* **Dependency Mapping:** Ingests source code, commit history, and API schemas into a graph vector database to build a holistic dependency map.
* **Tri-Agent Framework:** Deploys an Auditor, Security Analyst, and Refactor Agent to scan for security vulnerabilities, dead code, and performance bottlenecks.
* **Automated Refactoring:** Generates context-aware refactoring pull requests.
* **CI/CD Integration:** An automated test runner executes continuous integration checks on proposed changes, reducing manual code review overhead by up to 70%.

## 3. Project Domain & Technical Specifications

### 3.1 Domain Categorization
* **Project Domain:** Developer Tools & Software Engineering Quality Assurance
* **Technical Domain:** Generative AI, Retrieval-Augmented Generation (RAG), Static Code Analysis, Multi-Agent Systems, AST Processing, REST APIs

### 3.2 System Requirements
* **Software Requirements:**
  * Core Languages & Frameworks: Python, FastAPI, React.js / Next.js
  * Code Parsing & AI: Tree-sitter, LangGraph, Groq API (Llama 3.3)
  * Data & Storage: ChromaDB / Neo4j
  * DevOps & Environment: Docker, Git & GitHub, Postman, VS Code
* **Hardware Requirements:**
  * Processor: Intel i5 / i7 or equivalent
  * Memory: 16GB+ RAM
  * Storage: High-speed SSD
  * Connectivity: High-Speed Internet Connection"""
        )

    with col2:
        st.subheader("3. PDF Output Generation")
        
        if st.button("Generate Formatted PDF", type="primary"):
            with st.spinner("Reflowing document content to match target PDF geometry..."):
                output_pdf = compile_formatted_pdf(
                    doc_title=title_input,
                    abstract_text=abstract_input,
                    body_markdown=body_markdown_input,
                    css_styles=active_css
                )
                st.success("PDF Generation Complete!")
                
                with open(output_pdf, "rb") as pdf_file:
                    st.download_button(
                        label="📥 Download Formatted PDF",
                        data=pdf_file,
                        file_name="Formatted_Document.pdf",
                        mime="application/pdf"
                    )

if __name__ == "__main__":
    main()
