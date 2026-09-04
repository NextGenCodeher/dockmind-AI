import fitz  # PyMuPDF
import streamlit as st


def extract_template_html_and_css(uploaded_file):
    """
    Parses the reference PDF to extract visual properties (fonts, colors,
    geometry, vector lines, margins) and generates a dynamic HTML/CSS template.
    """
    try:
        file_bytes = uploaded_file.read()
        uploaded_file.seek(0)
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        if len(doc) == 0:
            return get_default_template()

        page = doc[0]
        rect = page.rect  # Total PDF page dimensions

        # 1. Extract Spans and Analyze Typography/Colors
        spans = []
        page_dict = page.get_text("dict")

        for b in page_dict.get("blocks", []):
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        text = span.get("text", "").strip()
                        if text:
                            # Extract Hex Color from Integer
                            color_int = span.get("color", 0)
                            r = (color_int >> 16) & 255
                            g = (color_int >> 8) & 255
                            b_val = color_int & 255
                            hex_color = f"#{r:02x}{g:02x}{b_val:02x}"

                            # Clean Font Name (Remove embedded subsets like ABCDEF+FontName)
                            raw_font = span.get("font", "Times New Roman")
                            font_clean = raw_font.split("+")[-1].split("-")[0]

                            spans.append(
                                {
                                    "text": text,
                                    "size": round(span.get("size", 10), 1),
                                    "font": font_clean,
                                    "color": hex_color,
                                    "flags": span.get("flags", 0),  # Bold/Italic
                                    "bbox": span.get("bbox"),
                                }
                            )

        if not spans:
            return get_default_template()

        # 2. Extract Exact Page Margins from Bounding Box Boundaries
        min_x = min(s["bbox"][0] for s in spans)
        min_y = min(s["bbox"][1] for s in spans)
        max_x = max(s["bbox"][2] for s in spans)
        max_y = max(s["bbox"][3] for s in spans)

        margin_top = f"{max(8, round(min_y, 1))}pt"
        margin_bottom = f"{max(8, round(rect.height - max_y, 1))}pt"
        margin_left = f"{max(8, round(min_x, 1))}pt"
        margin_right = f"{max(8, round(rect.width - max_x, 1))}pt"

        # 3. Detect Dominant Body Font & Primary Accent Color
        font_counts = {}
        color_counts = {}
        for s in spans:
            font_counts[s["font"]] = font_counts.get(s["font"], 0) + 1
            if s["color"] != "#ffffff":
                color_counts[s["color"]] = color_counts.get(s["color"], 0) + 1

        primary_font = (
            max(font_counts, key=font_counts.get)
            if font_counts
            else "Times New Roman"
        )
        primary_color = (
            max(color_counts, key=color_counts.get)
            if color_counts
            else "#000000"
        )

        # 4. Extract Dynamic Font Hierarchy (Sizes for Title, Headings, Body)
        sorted_sizes = sorted(
            list(set(s["size"] for s in spans)), reverse=True
        )

        title_size = (
            f"{sorted_sizes[0]}pt" if len(sorted_sizes) >= 1 else "18pt"
        )
        h2_size = f"{sorted_sizes[1]}pt" if len(sorted_sizes) >= 2 else "12pt"
        body_size = f"{sorted_sizes[-1]}pt" if len(sorted_sizes) >= 3 else "9.5pt"

        # 5. Detect Section Divider Lines (Vector Graphics / Drawings)
        drawings = page.get_drawings()
        has_heading_borders = False
        for d in drawings:
            # Check for horizontal line vectors near content
            for item in d.get("items", []):
                if item[0] == "l":  # Line
                    p1, p2 = item[1], item[2]
                    if abs(p1.y - p2.y) < 2 and abs(p1.x - p2.x) > 100:
                        has_heading_borders = True
                        break

        border_style = (
            f"border-bottom: 1px solid {primary_color};"
            if has_heading_borders
            else "border-bottom: none;"
        )

        # 6. Detect Multi-Column Layouts
        midpoint = rect.width / 2
        left_spans = [s for s in spans if s["bbox"][2] < midpoint - 10]
        right_spans = [s for s in spans if s["bbox"][0] > midpoint + 10]
        is_two_column = len(left_spans) > 5 and len(right_spans) > 5

        column_css = (
            "column-count: 2; column-gap: 16pt; column-fill: balance;"
            if is_two_column
            else "column-count: 1;"
        )

        # 7. Build Dynamic Template CSS
        css = f"""
        @page {{
            size: A4;
            margin: {margin_top} {margin_right} {margin_bottom} {margin_left};
        }}
        body {{
            font-family: '{primary_font}', 'Segoe UI', Arial, sans-serif;
            font-size: {body_size};
            line-height: 1.35;
            color: {primary_color};
            margin: 0;
            padding: 0;
            background: #ffffff;
        }}
        .header-container {{
            width: 100%;
            text-align: center;
            margin-bottom: 10pt;
        }}
        .header-container h1 {{
            font-size: {title_size};
            font-weight: bold;
            text-transform: uppercase;
            margin: 0 0 4pt 0;
            line-height: 1.2;
            color: {primary_color};
        }}
        .abstract-box {{
            text-align: justify;
            font-size: {body_size};
            margin: 6pt 0 10pt 0;
            padding: 6pt;
            background-color: #f8f9fa;
            border-left: 3px solid {primary_color};
        }}
        .body-container {{
            {column_css}
            text-align: left;
        }}
        h2 {{
            font-size: {h2_size};
            font-weight: bold;
            text-transform: uppercase;
            color: {primary_color};
            {border_style}
            margin-top: 10pt;
            margin-bottom: 4pt;
            padding-bottom: 2pt;
            break-after: avoid;
        }}
        h3 {{
            font-size: {body_size};
            font-weight: bold;
            color: {primary_color};
            margin-top: 6pt;
            margin-bottom: 2pt;
            break-after: avoid;
        }}
        p {{
            margin: 0 0 4pt 0;
        }}
        ul, ol {{
            margin: 0 0 6pt 0;
            padding-left: 14pt;
        }}
        li {{
            margin-bottom: 2pt;
        }}
        """

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
{css}
  </style>
</head>
<body>
  <div class="header-container">
    {{{{TITLE}}}}
    {{{{ABSTRACT}}}}
  </div>
  <div class="body-container">
    {{{{BODY_CONTENT}}}}
  </div>
</body>
</html>"""

    except Exception as e:
        st.error(f"Error analyzing reference PDF template: {e}")
        return get_default_template()
