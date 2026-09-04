import streamlit as st
import os
from core.pdf_engine import (
    convert_pdf_template_to_latex,
    map_content_to_latex,
    compile_tex_to_pdf
)

st.set_page_config(page_title="DocMind AI - PDF Styler", layout="wide")
st.title("📄 DocMind AI: Template-Driven PDF Generator")

# Initialize session state for storing extracted LaTeX template
if "latex_template" not in st.session_state:
    st.session_state.latex_template = None

# Step 1: Upload Reference Template PDF
st.header("Step 1: Upload Reference PDF Template")
template_pdf = st.file_uploader("Upload target layout/template PDF", type=["pdf"])

if template_pdf and st.button("Extract LaTeX Template"):
    with st.spinner("Analyzing PDF visual layout and generating LaTeX template..."):
        # Save temp template
        temp_path = "temp_template.pdf"
        with open(temp_path, "wb") as f:
            f.write(template_pdf.getvalue())
        
        st.session_state.latex_template = convert_pdf_template_to_latex(temp_path)
        st.success("LaTeX template extracted successfully!")

# Show current LaTeX template code if extracted
if st.session_state.latex_template:
    with st.expander("Preview Extracted LaTeX Template Code"):
        st.code(st.session_state.latex_template, language="latex")

    # Step 2: Provide Content
    st.header("Step 2: Enter Content to Place in Template")
    user_content = st.text_area("Paste raw notes or content here:", height=200)

    if user_content and st.button("Generate Formatted Document"):
        with st.spinner("Mapping content into template and compiling PDF..."):
            # Step 2a: Map content into template
            populated_tex = map_content_to_latex(user_content, st.session_state.latex_template)
            
            # Step 2b: Compile to PDF
            pdf_path = compile_tex_to_pdf(populated_tex, output_basename="styled_document")
            
            if pdf_path and os.path.exists(pdf_path):
                st.success("PDF generated successfully!")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Output PDF",
                        data=f.read(),
                        file_name="styled_document.pdf",
                        mime="application/pdf"
                    )
            else:
                st.error("LaTeX compilation failed. Ensure pdflatex is installed on your system.")
