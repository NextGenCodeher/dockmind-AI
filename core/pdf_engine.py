import os
import subprocess
import re
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

def convert_pdf_template_to_latex(pdf_path: str) -> str:
    """
    Analyzes an uploaded reference PDF template and generates a matching LaTeX (.tex) template.
    """
    # Upload the PDF file to Gemini File API for visual layout extraction
    uploaded_file = client.files.upload(file=pdf_path)
    
    prompt = """
    Analyze the visual layout, formatting, typography, structure, and sections of this reference PDF template.
    Create a flexible LaTeX (.tex) document template that recreates this exact formatting and style.
    Use placeholders like [[TITLE]], [[SUMMARY]], [[SECTION_1]], [[CONTENT_1]] for dynamic content.
    Return ONLY the raw LaTeX code inside a code block.
    """
    
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[uploaded_file, prompt]
    )
    
    # Extract raw LaTeX from output
    latex_code = response.text
    if "```latex" in latex_code:
        latex_code = latex_code.split("```latex")[1].split("```")[0].strip()
    elif "```" in latex_code:
        latex_code = latex_code.split("```")[1].split("```")[0].strip()
        
    return latex_code

def map_content_to_latex(user_content: str, latex_template: str) -> str:
    """
    Takes user content and maps it into the extracted LaTeX template code.
    """
    prompt = f"""
    You are a LaTeX document builder.
    Below is a LaTeX template with structure and styling:

    LATEX TEMPLATE:
    {latex_template}

    Place the following USER CONTENT into this LaTeX template while preserving the structural tags,
    styling, and packages. Ensure all special LaTeX characters (e.g., %, $, &, _) in the content are escaped.

    USER CONTENT:
    {user_content}

    Return ONLY the valid, full, compilable LaTeX code.
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    
    latex_code = response.text
    if "```latex" in latex_code:
        latex_code = latex_code.split("```latex")[1].split("```")[0].strip()
    elif "```" in latex_code:
        latex_code = latex_code.split("```")[1].split("```")[0].strip()

    return latex_code

def compile_tex_to_pdf(tex_code: str, output_basename: str = "output") -> str:
    """
    Saves and compiles LaTeX code into a PDF using pdflatex.
    """
    tex_file = f"{output_basename}.tex"
    with open(tex_file, "w", encoding="utf-8") as f:
        f.write(tex_code)

    try:
        subprocess.run(
            ["pdflatex", "-interaction=batchmode", tex_file],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return f"{output_basename}.pdf"
    except Exception as e:
        print(f"Compilation error: {e}")
        return None
