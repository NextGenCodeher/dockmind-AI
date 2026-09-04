import fitz  # PyMuPDF
from jinja2 import Template
from playwright.sync_api import sync_playwright

def parse_pdf_layout(input_pdf_path):
    doc = fitz.open(input_pdf_path)
    page = doc[0]
    p_width = page.rect.width
    p_height = page.rect.height

    blocks = page.get_text("blocks")
    extracted = []

    for b in blocks:
        x0, y0, x1, y1, text, _, _ = b
        cleaned = text.strip()
        if not cleaned:
            continue

        align = "left"
        if x0 > p_width * 0.55:
            align = "right"
        elif abs((x0 + x1) / 2 - p_width / 2) < 30:
            align = "center"

        extracted.append({
            "left": round(x0, 2),
            "top": round(y0, 2),
            "width": round(x1 - x0, 2),
            "height": round(y1 - y0, 2),
            "alignment": align
        })

    extracted.sort(key=lambda b: b["top"])

    layout = {
        "header": extracted[0] if len(extracted) > 0 else {"left": 0, "top": 40, "width": p_width, "alignment": "center"},
        "date": extracted[1] if len(extracted) > 1 else {"left": p_width * 0.6, "top": 100, "width": 200, "alignment": "right"},
        "address": extracted[2] if len(extracted) > 2 else {"left": 50, "top": 140, "width": 250, "alignment": "left"},
        "subject": extracted[3] if len(extracted) > 3 else {"left": 50, "top": 220, "width": 500, "alignment": "left"},
        "salutation": extracted[4] if len(extracted) > 4 else {"left": 50, "top": 260, "width": 200, "alignment": "left"},
        "body": extracted[5] if len(extracted) > 5 else {"left": 50, "top": 300, "width": p_width - 100, "alignment": "justify"},
        "closing": extracted[-1] if len(extracted) > 6 else {"left": 50, "top": p_height - 150, "width": 300, "alignment": "left"}
    }
    return layout, p_width, p_height


HTML_TEMPLATE_STRING = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @page { size: {{ width }}pt {{ height }}pt; margin: 0; }
  body {
    position: relative;
    width: {{ width }}pt;
    height: {{ height }}pt;
    margin: 0;
    padding: 0;
    font-family: 'Times New Roman', serif;
    font-size: 12pt;
    line-height: 1.5;
  }
  .block { position: absolute; box-sizing: border-box; word-wrap: break-word; }
</style>
</head>
<body>
  <div class="block" style="left: {{ layout.header.left }}pt; top: {{ layout.header.top }}pt; width: {{ layout.header.width }}pt; text-align: {{ layout.header.alignment }};">
    <b>{{ content.header }}</b>
  </div>
  <div class="block" style="left: {{ layout.date.left }}pt; top: {{ layout.date.top }}pt; width: {{ layout.date.width }}pt; text-align: {{ layout.date.alignment }};">
    <b>Date:</b> {{ content.date }}
  </div>
  <div class="block" style="left: {{ layout.address.left }}pt; top: {{ layout.address.top }}pt; width: {{ layout.address.width }}pt; text-align: {{ layout.address.alignment }};">
    <b>To,</b><br>
    {% for line in content.address %}{{ line }}<br>{% endfor %}
  </div>
  <div class="block" style="left: {{ layout.subject.left }}pt; top: {{ layout.subject.top }}pt; width: {{ layout.subject.width }}pt; text-align: {{ layout.subject.alignment }};">
    <u><b>Subject: {{ content.subject }}</b></u>
  </div>
  <div class="block" style="left: {{ layout.salutation.left }}pt; top: {{ layout.salutation.top }}pt; width: {{ layout.salutation.width }}pt; text-align: {{ layout.salutation.alignment }};">
    {{ content.salutation }},
  </div>
  <div class="block" style="left: {{ layout.body.left }}pt; top: {{ layout.body.top }}pt; width: {{ layout.body.width }}pt; text-align: justify;">
    {% for p in content.paragraphs %}
      <p style="text-indent: 35px; margin-bottom: 12px;">{{ p }}</p>
    {% endfor %}
  </div>
  <div class="block" style="left: {{ layout.closing.left }}pt; top: {{ layout.closing.top }}pt; width: {{ layout.closing.width }}pt; text-align: {{ layout.closing.alignment }};">
    Thanking you,<br>
    {{ content.sign_off }},<br><br><br>
    <b>{{ content.sender_name }}</b><br>
    {{ content.sender_title }}
  </div>
</body>
</html>
"""


def convert_pdf_template(input_pdf, content_data, output_pdf):
    layout_map, page_w, page_h = parse_pdf_layout(input_pdf)

    template = Template(HTML_TEMPLATE_STRING)
    rendered_html = template.render(
        width=round(page_w),
        height=round(page_h),
        layout=layout_map,
        content=content_data
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html)
        
        # Round the width and height to integer pt strings for Playwright
        page.pdf(
            path=output_pdf,
            width=f"{round(page_w)}pt",
            height=f"{round(page_h)}pt",
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"}
        )
        browser.close()

    print(f"Done! Output saved to: {output_pdf}")


if __name__ == "__main__":
    my_content = {
        "header": "DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING",
        "date": "September 5, 2026",
        "address": ["The Principal", "G. Pulla Reddy Engineering College", "Kurnool"],
        "subject": "Request for Lab Resources",
        "salutation": "Dear Sir",
        "paragraphs": [
            "I am writing to request access to the machine learning laboratory for our research project.",
            "We plan to run multi-node workload experiments starting next week."
        ],
        "sign_off": "Yours faithfully",
        "sender_name": "Honey Amilineni",
        "sender_title": "Student Lead, CSE"
    }

    convert_pdf_template("sample_letter.pdf", my_content, "final_letter_output.pdf")
