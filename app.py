import os
import re
import subprocess
import fitz  # PyMuPDF
import streamlit as st

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="DocMind AI: Dynamic LaTeX Document Compiler",
    page_icon="📄",
    layout="wide",
)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -----------------------------------------------------------------------------
# DEFAULT LATEX TEMPLATE FALLBACK
# -----------------------------------------------------------------------------
def get_default_latex_template() -> str:
    return r"""\documentclass[twocolumn,10pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=18mm]{geometry}
\usepackage{microtype}
\usepackage{titlesec}
\usepackage{abstract}
\usepackage{hyperref}

\titleformat{\section}{\large\bfseries\uppercase}{}{0pt}{}[\titlerule]
\titleformat{\subsection}{\normalfont\bfseries}{}{0pt}{}

\title{\textbf{{{TITLE}}}}
\date{}

\begin{document}

\twocolumn[
  \begin{maketitle}
  \end{maketitle}
  \begin{abstract}
  \noindent {{ABSTRACT}}
  \end{abstract}
  \vspace{1.5em}
]

{{BODY_CONTENT}}

\end{document}
"""


# -----------------------------------------------------------------------------
# STEP 1: PARSE REFERENCE PDF & BUILD DYNAMIC LATEX TEMPLATE (FIXED)
# -----------------------------------------------------------------------------
def extract_latex_template_from_pdf(uploaded_file) -> str:
    """Analyzes reference PDF geometry and typography to construct a LaTeX template shell."""
    doc = None
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        
        # PyMuPDF document initialization
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        if len(doc) == 0:
            return get_default_latex_template()

        page = doc[0]
        rect = page.rect

        spans = []
        page_dict = page.get_text("dict")

        for b in page_dict.get("blocks", []):
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        text = span.get("text", "").strip()
                        if text:
                            spans.append(
                                {
                                    "text": text,
                                    "size": round(span.get("size", 10), 1),
                                    "bbox": span.get("bbox"),
                                }
                            )

        if not spans:
            return get_default_latex_template()

        # Extract Bounding Margins
        min_x = min(s["bbox"][0] for s in spans)
        min_y = min(s["bbox"][1] for s in spans)
        max_x = max(s["bbox"][2] for s in spans)
        max_y = max(s["bbox"][3] for s in spans)

        margin_top = f"{max(12, round(min_y * 0.35, 1))}mm"
        margin_bottom = f"{max(12, round((rect.height - max_y) * 0.35, 1))}mm"
        margin_left = f"{max(12, round(min_x * 0.35, 1))}mm"
        margin_right = f"{max(12, round((rect.width - max_x) * 0.35, 1))}mm"

        # Detect Column Layout (1 Column vs 2 Column)
        midpoint = rect.width / 2
        left_spans = [s for s in spans if s["bbox"][2] < midpoint - 10]
        right_spans = [s for s in spans if s["bbox"][0] > midpoint + 10]
        is_two_column = len(left_spans) > 5 and len(right_spans) > 5

        column_option = "twocolumn," if is_two_column else "onecolumn,"

        # Detect Font Hierarchy
        sorted_sizes = sorted(
            list(set(s["size"] for s in spans)), reverse=True
        )
        base_size = "10pt"
        if sorted_sizes:
            avg_body_size = sorted_sizes[-1]
            if avg_body_size >= 11:
                base_size = "11pt"
            elif avg_body_size >= 12:
                base_size = "12pt"

        # Construct Dynamic LaTeX Template Shell
        latex_template = rf"""\documentclass[{column_option}{base_size},a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[top={margin_top},bottom={margin_bottom},left={margin_left},right={margin_right}]{{geometry}}
\usepackage{{microtype}}
\usepackage{{titlesec}}
\usepackage{{abstract}}
\usepackage{{hyperref}}

\titleformat{{\section}}{{\large\bfseries\uppercase}}{{}}{{0pt}}{{}}[\titlerule]
\titleformat{{\subsection}}{{\normalfont\bfseries}}{{}}{{0pt}}{{}}

\title{{\textbf{{{{TITLE}}}}}}
\date{{}}

\begin{document}

\twocolumn[
  \begin{maketitle}
  \end{maketitle}
  \begin{abstract}
  \noindent {{{{ABSTRACT}}}}
  \end{abstract}
  \vspace{{1.5em}}
]

{{{{BODY_CONTENT}}}}

\end{document}
"""
        return latex_template

    except Exception as e:
        st.error(f"Error parsing reference PDF template: {e}")
        return get_default_latex_template()
    finally:
        if doc is not None:
            doc.close()


# -----------------------------------------------------------------------------
# HELPER: MARKDOWN TO LATEX CONVERTER
# -----------------------------------------------------------------------------
def markdown_to_latex(text: str) -> str:
    if not text:
        return ""

    # Escape raw special LaTeX characters
    text = text.replace("&", r"\&").replace("%", r"\%").replace("$", r"\$")

    # Headings
    text = re.sub(r"^###\s+(.*$)", r"\\subsubsection*{\1}", text, flags=re.M)
    text = re.sub(r"^##\s+(.*$)", r"\\subsection*{\1}", text, flags=re.M)
    text = re.sub(r"^#\s+(.*$)", r"\\section*{\1}", text, flags=re.M)

    # Bold & Italics
    text = re.sub(r"\*\*(.*?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"\*(.*?)\*", r"\\italic{\1}", text)

    # Bullet lists
    lines = text.split("\n")
    in_list = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            item = line.strip()[2:]
            if not in_list:
                new_lines.append(r"\begin{itemize}")
                in_list = True
            new_lines.append(rf"  \item {item}")
        else:
            if in_list:
                new_lines.append(r"\end{itemize}")
                in_list = False
            new_lines.append(line)

    if in_list:
        new_lines.append(r"\end{itemize}")

    return "\n".join(new_lines)


# -----------------------------------------------------------------------------
# CHAT CONTENT PARSER
# -----------------------------------------------------------------------------
def parse_chat_content(user_message: str):
    title = "Untitled Document"
    abstract = ""
    body = user_message

    title_match = re.search(
        r"^(?:#\s+|(?:Title:\s*))([^\n]+)", user_message, re.IGNORECASE
    )
    if title_match:
        title = title_match.group(1).strip()
        body = user_message.replace(title_match.group(0), "", 1).strip()

    abstract_match = re.search(
        r"Abstract:\s*([^\n]+(?:\n[^\n]+)*?)(?=\n\n|\n#|$)", body, re.IGNORECASE
    )
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        body = body.replace(abstract_match.group(0), "", 1).strip()

    return title, abstract, body


# -----------------------------------------------------------------------------
# LATEX PDF COMPILER (`pdflatex`)
# -----------------------------------------------------------------------------
def render_pdf_with_latex(latex_code: str, output_filename: str) -> bool:
    try:
        tex_filename = output_filename.replace(".pdf", ".tex")
        with open(tex_filename, "w", encoding="utf-8") as f:
            f.write(latex_code)

        # Run pdflatex command
        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            f"-output-directory={OUTPUT_DIR}",
            tex_filename,
        ]

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        if result.returncode == 0 and os.path.exists(output_filename):
            return True
        else:
            st.error(
                "LaTeX Compilation Error. Please ensure special LaTeX characters are properly formatted."
            )
            return False

    except Exception as e:
        st.error(
            f"Failed to execute pdflatex binary: {e}. Ensure `texlive-latex-base` is installed in packages.txt."
        )
        return False


# -----------------------------------------------------------------------------
# MAIN STREAMLIT APP
# -----------------------------------------------------------------------------
def main():
    st.title("📄 DocMind AI: PDF Layout Extractor & LaTeX Compiler")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Step 1: Upload a sample reference PDF in the sidebar.\nStep 2: Type or paste your document text below in the chat to format it into PDF!",
            }
        ]

    if "latex_template" not in st.session_state:
        st.session_state.latex_template = get_default_latex_template()

    # --- SIDEBAR: STEP 1 (UPLOAD & EXTRACT TEMPLATE) ---
    with st.sidebar:
        st.header("Step 1: Input Reference PDF")
        uploaded_file = st.file_uploader(
            "Upload Reference PDF Template", type=["pdf"]
        )

        if uploaded_file:
            st.session_state.latex_template = extract_latex_template_from_pdf(
                uploaded_file
            )
            st.success(
                f"Extracted LaTeX structure from `{uploaded_file.name}`!"
            )

        with st.expander("🔍 View Generated LaTeX Shell"):
            st.code(st.session_state.latex_template, language="latex")

    # --- MAIN CHAT INTERFACE: STEP 2 (REPLACE CONTENT & COMPILE) ---
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if "pdf_path" in msg and os.path.exists(msg["pdf_path"]):
                with open(msg["pdf_path"], "rb") as f:
                    st.download_button(
                        label="📥 Download Generated LaTeX PDF",
                        data=f,
                        file_name=os.path.basename(msg["pdf_path"]),
                        mime="application/pdf",
                        key=f"dl_{msg['pdf_path']}",
                    )

    if prompt := st.chat_input("Paste or type your new document content..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Injecting text and compiling LaTeX PDF..."):
                title, abstract, body_markdown = parse_chat_content(prompt)

                title_latex = markdown_to_latex(title)
                abstract_latex = markdown_to_latex(abstract)
                body_latex = markdown_to_latex(body_markdown)

                # Inject parsed chat content into the extracted LaTeX template placeholders
                final_latex = (
                    st.session_state.latex_template.replace(
                        "{{TITLE}}", title_latex
                    )
                    .replace("{{ABSTRACT}}", abstract_latex)
                    .replace("{{BODY_CONTENT}}", body_latex)
                )

                pdf_filename = os.path.join(
                    OUTPUT_DIR,
                    f"Formatted_Paper_{len(st.session_state.messages)}.pdf",
                )

                success = render_pdf_with_latex(final_latex, pdf_filename)

                if success:
                    response_text = "✅ **Document Formatted & Compiled via LaTeX Successfully!**"
                    st.markdown(response_text)

                    with open(pdf_filename, "rb") as f:
                        st.download_button(
                            label="📥 Download Generated LaTeX PDF",
                            data=f,
                            file_name="Formatted_Document.pdf",
                            mime="application/pdf",
                        )

                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": response_text,
                            "pdf_path": pdf_filename,
                        }
                    )


if __name__ == "__main__":
    main()
