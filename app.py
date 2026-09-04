from jinja2 import Template
from playwright.sync_api import sync_playwright

# Clean document template using standard document flow
HTML_TEMPLATE_STRING = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @page { 
    size: A4; 
    margin: 20mm 20mm 20mm 20mm; 
  }
  body {
    font-family: 'Times New Roman', Times, serif;
    font-size: 12pt;
    line-height: 1.6;
    color: #000;
  }
  .header {
    text-align: center;
    font-weight: bold;
    font-size: 14pt;
    text-transform: uppercase;
    margin-bottom: 25px;
  }
  .date {
    text-align: right;
    margin-bottom: 20px;
    font-weight: bold;
  }
  .address {
    margin-bottom: 20px;
  }
  .subject {
    font-weight: bold;
    text-decoration: underline;
    margin-top: 15px;
    margin-bottom: 20px;
  }
  .salutation {
    margin-bottom: 15px;
  }
  .body-paragraph {
    text-align: justify;
    text-indent: 40px;
    margin-bottom: 15px;
  }
  .closing {
    margin-top: 40px;
  }
  .signature {
    margin-top: 50px;
  }
</style>
</head>
<body>

  <!-- Header -->
  <div class="header">
    {{ content.header }}
  </div>

  <!-- Date -->
  <div class="date">
    Date: {{ content.date }}
  </div>

  <!-- Address -->
  <div class="address">
    <b>To,</b><br>
    {% for line in content.address %}
      {{ line }}<br>
    {% endfor %}
  </div>

  <!-- Subject -->
  <div class="subject">
    Subject: {{ content.subject }}
  </div>

  <!-- Salutation -->
  <div class="salutation">
    {{ content.salutation }},
  </div>

  <!-- Body -->
  {% for p in content.paragraphs %}
    <div class="body-paragraph">
      {{ p }}
    </div>
  {% endfor %}

  <!-- Closing -->
  <div class="closing">
    Thanking you,<br>
    {{ content.sign_off }},
  </div>

  <!-- Signature -->
  <div class="signature">
    <b>{{ content.sender_name }}</b><br>
    {{ content.sender_title }}
  </div>

</body>
</html>
"""


def convert_pdf_template(content_data, output_pdf):
    template = Template(HTML_TEMPLATE_STRING)
    rendered_html = template.render(content=content_data)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered_html)

        # Standard A4 PDF export
        page.pdf(
            path=output_pdf,
            format="A4",
            print_background=True
        )
        browser.close()

    print(f"Done! Output saved to: {output_pdf}")


if __name__ == "__main__":
    my_content = {
        "header": "DEPARTMENT OF COMPUTER SCIENCE & ENGINEERING",
        "date": "September 5, 2026",
        "address": [
            "The Principal",
            "G. Pulla Reddy Engineering College",
            "Kurnool"
        ],
        "subject": "Request for Lab Resources",
        "salutation": "Respected Sir",
        "paragraphs": [
            "I am writing to request access to the machine learning laboratory for our research project.",
            "We plan to run multi-node workload experiments starting next week."
        ],
        "sign_off": "Yours faithfully",
        "sender_name": "Honey Amilineni",
        "sender_title": "Student Lead, CSE"
    }

    convert_pdf_template(my_content, "final_letter_output.pdf")
