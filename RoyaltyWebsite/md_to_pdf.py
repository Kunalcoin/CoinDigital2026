#!/usr/bin/env python3
"""Convert DDEX_FULL_USER_FLOW_AND_SPEC.md to PDF using fpdf2."""
import re
from pathlib import Path

from fpdf import FPDF


class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 6, "DDEX Full User Flow & Implementation Spec", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 6, f"Page {self.page_no()}", align="C", new_x="LMARGIN", new_y="NEXT")


def strip_md_bold(s):
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", s)


def to_ascii_safe(s):
    """Replace Unicode so fpdf2 Helvetica can render (Latin-1)."""
    if not s:
        return s
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    return "".join(c if ord(c) < 256 else "?" for c in s)


def clean(s):
    return to_ascii_safe(strip_md_bold(s))


def render_bold_cell(pdf, text, w, h=6, bold_style=True):
    """Render text with **bold** as bold."""
    pdf.set_font("Helvetica", "B" if bold_style else "", 10)
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    x = pdf.get_x()
    for part in parts:
        if part.startswith("**") and part.endswith("**"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, h, strip_md_bold(part), new_x="RIGHT", new_y="LAST")
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, h, part, new_x="RIGHT", new_y="LAST")
    pdf.set_x(x)
    pdf.cell(w, h, "", new_x="LMARGIN", new_y="NEXT")  # move to next line


def main():
    md_path = Path(__file__).parent / "DDEX_FULL_USER_FLOW_AND_SPEC.md"
    out_path = Path(__file__).parent / "DDEX_FULL_USER_FLOW_AND_SPEC.pdf"
    text = md_path.read_text(encoding="utf-8")

    pdf = PDF()
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=15)

    in_table = False
    table_rows = []
    for line in text.splitlines():
        line_stripped = line.strip()
        if not line_stripped and not in_table:
            pdf.ln(3)
            continue
        if not line_stripped and in_table:
            # Flush table
            if table_rows:
                col_count = max(len(r) for r in table_rows)
                w = 190 / col_count
                for i, row in enumerate(table_rows):
                    if i == 0:
                        pdf.set_font("Helvetica", "B", 9)
                    else:
                        pdf.set_font("Helvetica", "", 8)
                    for j, cell in enumerate(row):
                        if j < col_count:
                            cell_clean = clean(cell.strip())[:60] + ("..." if len(cell.strip()) > 60 else "")
                            pdf.cell(w, 6, cell_clean, border=1)
                    pdf.ln()
                pdf.ln(2)
                pdf.set_x(pdf.l_margin)
            table_rows = []
            in_table = False
            continue
        if line_stripped.startswith("|") and "---" not in line_stripped and "|" in line_stripped[1:]:
            in_table = True
            cells = [c.strip() for c in line_stripped.split("|")[1:-1]]
            table_rows.append(cells)
            continue
        if line_stripped.startswith("|") and "---" in line_stripped:
            continue  # skip separator row
        in_table = False
        if table_rows:
            col_count = max(len(r) for r in table_rows)
            w = 190 / col_count
            for i, row in enumerate(table_rows):
                if i == 0:
                    pdf.set_font("Helvetica", "B", 9)
                else:
                    pdf.set_font("Helvetica", "", 8)
                for j, cell in enumerate(row):
                    if j < col_count:
                        cell_clean = clean(cell.strip())[:55] + ("..." if len(cell.strip()) > 55 else "")
                        pdf.cell(w, 6, cell_clean, border=1)
                pdf.ln()
            pdf.ln(2)
            pdf.set_x(pdf.l_margin)
            table_rows = []

        pdf.set_x(pdf.l_margin)
        if line_stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 16)
            pdf.ln(4)
            pdf.multi_cell(0, 8, clean(line_stripped[2:]))
        elif line_stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 13)
            pdf.ln(4)
            pdf.multi_cell(0, 7, clean(line_stripped[3:]))
        elif line_stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.ln(3)
            pdf.multi_cell(0, 6, clean(line_stripped[4:]))
        elif line_stripped.startswith("- ") or line_stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(6, 5, "-")
            pdf.multi_cell(0, 5, clean(line_stripped[2:]))
        elif line_stripped.startswith("1. ") or re.match(r"^\d+\. ", line_stripped):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, clean(line_stripped))
        elif line_stripped.startswith("- [ ]"):
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(8, 5, "[ ]")
            pdf.multi_cell(0, 5, clean(line_stripped[5:].strip()))
        else:
            pdf.set_font("Helvetica", "", 10)
            t = clean(line_stripped)
            if len(t) > 500:
                t = t[:497] + "..."
            pdf.multi_cell(0, 5, t)

    if table_rows:
        col_count = max(len(r) for r in table_rows)
        w = 190 / col_count
        for i, row in enumerate(table_rows):
            if i == 0:
                pdf.set_font("Helvetica", "B", 9)
            else:
                pdf.set_font("Helvetica", "", 8)
            for j, cell in enumerate(row):
                if j < col_count:
                    cell_clean = clean(cell.strip())[:55] + ("..." if len(cell.strip()) > 55 else "")
                    pdf.cell(w, 6, cell_clean, border=1)
            pdf.ln()
        pdf.set_x(pdf.l_margin)

    pdf.output(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
