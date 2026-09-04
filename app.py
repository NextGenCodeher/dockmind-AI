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
  @page { 
    size: {{ width }}px {{ height }}px; 
    margin: 0; 
  }
  body {
    position: relative;
    width: {{ width }}px;
    height: {{ height }}px;
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
  <div class="block" style="left: {{ layout.header.left }}px; top: {{ layout.header.top }}px; width: {{ layout.header.width }}px; text-align: {{ layout.header.alignment }};">
    <b>{{ content.header }}</b>
  </div>
  <div class="block" style="left: {{ layout.date.left }}px; top: {{ layout.date.top }}px; width: {{ layout.date.width }}px; text-align: {{ layout.date.alignment }};">
    <b>Date:</b> {{ content.date }}
  </div>
  <div class="block" style="left: {{ layout.address.left }}px; top: {{ layout.address.top }}px; width: {{ layout.address.width }}px; text-align: {{ layout.address.alignment }};">
    <b>To,</b><br>
    {% for line in content.address %}{{ line }}<br>{% endfor %}
  </div>
  <div class="block" style="left: {{ layout.subject.left }}px; top: {{ layout.subject.top }}px; width: {{ layout.subject.width }}px; text-align: {{ layout.subject.alignment }};">
    <u><b>Subject: {{ content.subject }}</b></u>
  </div>
  <div class="block" style="left: {{ layout.salutation.left }}px; top: {{ layout.salutation.top }}px; width: {{ layout.salutation.width }}px; text-align: {{ layout.salutation.alignment }};">
    {{ content.salutation }},
  </div>
  <div class="block" style="left: {{ layout.body.left }}px; top: {{ layout.body.top }}px; width: {{ layout.body.width }}px; text-align: justify;">
    {% for p in content.paragraphs %}
      <p style="text-indent: 35px; margin-bottom: 12px;">{{ p }}</p>
    {% endfor %}
  </div>
  <div class="block" style="left: {{ layout.closing.left }}px; top: {{ layout.closing.top }}px; width: {{ layout.closing.width }}px; text-align: {{ layout.closing.alignment }};">
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

    # Convert to integer pixel values
    w_px = round(page_w)
    h_px = round(page_h)

    template = Template(HTML_TEMPLATE_STRING)
    rendered_html = template.render(
        width=w_px,
        height=h_px,
        layout=layout_map,
        content=content_data
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html)

        # Pass 'px' strings to Playwright page.pdf()
        page.pdf(
            path=output_pdf,
            width=f"{w_px}px",
            height=f"{h_px}px",
            margin={"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}
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
