import os
import tempfile
from google import genai
import streamlit as st

st.set_page_config(
    page_title="PDF to LaTeX Converter", page_icon="📄", layout="centered"
)

st.title("📄 PDF to LaTeX Converter")
st.write(
    "Upload a document or PDF to convert it into clean, compilable LaTeX code"
    " using Gemini."
)

# Initialize client using Streamlit secrets
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
  st.error("Gemini API key not found. Please configure it in Streamlit Secrets.")
else:
  client = genai.Client(api_key=api_key)

  uploaded_file = st.file_uploader(
      "Choose a PDF or text file", type=["pdf", "txt", "md"]
  )

  if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}"
    ) as tmp_file:
      tmp_file.write(uploaded_file.getvalue())
      tmp_path = tmp_file.name

    if st.button("Convert to LaTeX"):
      with st.spinner("Processing document layout with Gemini..."):
        try:
          gemini_file = client.files.upload(file=tmp_path)

          prompt = prompt = """
            You are an expert LaTeX typesetter and layout reconstruction specialist.
            Analyze the visual geometry, spacing, margins, header alignment, and precise relative placement of elements in this document.
            Recreate it in LaTeX with absolute fidelity using appropriate positioning tools (such as the 'geometry', 'fancyhdr', or 'textpos' packages if necessary).
            
            Requirements:
            1. Preserve exact relative coordinates, text alignments (left, right, center), and vertical/horizontal spacing.
            2. Match every visual block, line break, and block element to its exact corresponding location on the page.
            3. Return ONLY the raw LaTeX code inside a markdown code block.
            """

          response = client.models.generate_content(
              model="gemini-3.6-flash", contents=[gemini_file, prompt]
          )

          latex_output = (
              response.text.replace("```latex", "")
              .replace("```", "")
              .strip()
          )

          st.success("Conversion successful!")
          st.code(latex_output, language="latex")

          st.download_button(
              label="Download .tex File",
              data=latex_output,
              file_name="output.tex",
              mime="text/plain",
          )

        except Exception as e:
          st.error(f"An error occurred: {e}")
        finally:
          if os.path.exists(tmp_path):
            os.remove(tmp_path)
