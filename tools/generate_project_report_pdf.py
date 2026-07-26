from __future__ import annotations

import argparse
import re
import textwrap
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List, Optional


A4_WIDTH = 595.28
A4_HEIGHT = 841.89
MARGIN_X = 56
MARGIN_TOP = 58
MARGIN_BOTTOM = 54
CONTENT_WIDTH = A4_WIDTH - (2 * MARGIN_X)
BLUE = (20, 74, 128)
DARK = (35, 42, 50)
MUTED = (92, 103, 115)
LIGHT = (239, 244, 249)
BORDER = (205, 214, 224)


def _pdf_text(value: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2192": "->",
        "\u2022": "-",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    encoded = value.encode("cp1252", errors="replace").decode("cp1252")
    return encoded.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _plain(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = value.replace("**", "")
    return value.strip()


def _wrap(value: str, width: int) -> List[str]:
    return textwrap.wrap(
        _plain(value),
        width=max(12, width),
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def _chars_for_width(points: float, font_size: int) -> int:
    # Helvetica average glyph width is close enough for deterministic wrapping.
    return max(12, int(points / (font_size * 0.52)))


@dataclass
class Page:
    commands: List[str]


class PdfDocument:
    def __init__(self) -> None:
        self.pages: List[Page] = []

    def add_page(self) -> Page:
        page = Page(commands=[])
        self.pages.append(page)
        return page

    def write(self, output_path: Path) -> None:
        objects: List[bytes] = []

        def add_object(content: bytes) -> int:
            objects.append(content)
            return len(objects)

        font_regular = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font_bold = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        font_mono = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")

        page_object_ids: List[int] = []
        page_contents: List[bytes] = []

        for page in self.pages:
            stream = "\n".join(page.commands).encode("cp1252", errors="replace")
            content_id = add_object(
                b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
            )
            page_contents.append(stream)
            page_id = add_object(
                (
                    f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {A4_WIDTH:.2f} {A4_HEIGHT:.2f}] "
                    f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_mono} 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode("ascii")
            )
            page_object_ids.append(page_id)

        kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
        pages_id = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode("ascii"))

        for i, obj in enumerate(objects):
            if b"/Parent 0 0 R" in obj:
                objects[i] = obj.replace(b"/Parent 0 0 R", f"/Parent {pages_id} 0 R".encode("ascii"))

        catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii"))

        output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{idx} 0 obj\n".encode("ascii"))
            output.extend(obj)
            output.extend(b"\nendobj\n")
        xref_start = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            (
                f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
                f"startxref\n{xref_start}\n%%EOF\n"
            ).encode("ascii")
        )
        output_path.write_bytes(output)


class ReportRenderer:
    def __init__(self, title: str) -> None:
        self.doc = PdfDocument()
        self.title = title
        self.page: Optional[Page] = None
        self.y = 0.0
        self.page_number = 0

    def rgb(self, color: tuple[int, int, int]) -> str:
        return f"{color[0] / 255:.3f} {color[1] / 255:.3f} {color[2] / 255:.3f}"

    def set_color(self, color: tuple[int, int, int]) -> None:
        assert self.page is not None
        self.page.commands.append(f"{self.rgb(color)} rg {self.rgb(color)} RG")

    def rect(self, x: float, y: float, w: float, h: float, color: tuple[int, int, int], fill: bool = True) -> None:
        assert self.page is not None
        self.set_color(color)
        self.page.commands.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re {'f' if fill else 'S'}")

    def line(self, x1: float, y1: float, x2: float, y2: float, color: tuple[int, int, int]) -> None:
        assert self.page is not None
        self.set_color(color)
        self.page.commands.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def text(self, x: float, y: float, value: str, size: int = 10, font: str = "F1", color: tuple[int, int, int] = DARK) -> None:
        assert self.page is not None
        self.set_color(color)
        self.page.commands.append(f"BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({_pdf_text(value)}) Tj ET")

    def new_page(self) -> None:
        if self.page is not None:
            self.footer()
        self.page = self.doc.add_page()
        self.page_number += 1
        self.y = A4_HEIGHT - MARGIN_TOP
        if self.page_number > 1:
            self.text(MARGIN_X, A4_HEIGHT - 32, self.title, 8, "F2", MUTED)
            self.line(MARGIN_X, A4_HEIGHT - 42, A4_WIDTH - MARGIN_X, A4_HEIGHT - 42, BORDER)
            self.y = A4_HEIGHT - 68

    def footer(self) -> None:
        if self.page is None or self.page_number == 1:
            return
        self.line(MARGIN_X, 38, A4_WIDTH - MARGIN_X, 38, BORDER)
        self.text(MARGIN_X, 24, "NAE Platform - Informe final del proyecto", 8, "F1", MUTED)
        self.text(A4_WIDTH - MARGIN_X - 50, 24, f"Pagina {self.page_number}", 8, "F1", MUTED)

    def ensure(self, height: float) -> None:
        if self.page is None:
            self.new_page()
        if self.y - height < MARGIN_BOTTOM:
            self.new_page()

    def paragraph(self, value: str, size: int = 10, leading: int = 14, color: tuple[int, int, int] = DARK) -> None:
        text = _plain(value)
        if not text:
            self.y -= 6
            return
        width_chars = _chars_for_width(CONTENT_WIDTH, size)
        lines = _wrap(text, width_chars)
        self.ensure(len(lines) * leading + 8)
        for line in lines:
            self.text(MARGIN_X, self.y, line, size, "F1", color)
            self.y -= leading
        self.y -= 4

    def bullet(self, value: str) -> None:
        text = _plain(value)
        lines = _wrap(text, _chars_for_width(CONTENT_WIDTH - 18, 10))
        self.ensure(len(lines) * 13 + 4)
        self.text(MARGIN_X + 4, self.y, "-", 10, "F2", BLUE)
        for line in lines:
            self.text(MARGIN_X + 18, self.y, line, 10, "F1", DARK)
            self.y -= 13
        self.y -= 2

    def heading(self, value: str, level: int) -> None:
        clean = _plain(value)
        if level == 1:
            return
        if level == 2:
            lines = _wrap(clean, _chars_for_width(CONTENT_WIDTH, 17))
            self.ensure(34 + (len(lines) * 20))
            self.y -= 10
            for line in lines:
                self.text(MARGIN_X, self.y, line, 17, "F2", BLUE)
                self.y -= 20
            self.line(MARGIN_X, self.y, MARGIN_X + 190, self.y, BLUE)
            self.y -= 18
        else:
            lines = _wrap(clean, _chars_for_width(CONTENT_WIDTH, 12))
            self.ensure(18 + (len(lines) * 15))
            self.y -= 6
            for line in lines:
                self.text(MARGIN_X, self.y, line, 12, "F2", DARK)
                self.y -= 15
            self.y -= 2

    def code_block(self, lines: List[str]) -> None:
        wrapped_lines: List[str] = []
        width_chars = _chars_for_width(CONTENT_WIDTH - 20, 8)
        for line in lines:
            wrapped_lines.extend(_wrap(line, width_chars))
        height = max(28, len(wrapped_lines) * 10 + 18)
        self.ensure(height + 8)
        self.rect(MARGIN_X, self.y - height + 8, CONTENT_WIDTH, height, LIGHT, True)
        y = self.y - 8
        for line in wrapped_lines:
            self.text(MARGIN_X + 10, y, line, 8, "F3", DARK)
            y -= 10
        self.y -= height + 8

    def table(self, rows: List[List[str]]) -> None:
        if not rows:
            return
        col_count = len(rows[0])
        widths = [145, CONTENT_WIDTH - 145] if col_count == 2 else [CONTENT_WIDTH / col_count] * col_count
        x = MARGIN_X
        for row_idx, row in enumerate(rows):
            wrapped_cells: List[List[str]] = []
            max_lines = 1
            for col_idx, cell in enumerate(row):
                chars = _chars_for_width(widths[col_idx] - 12, 8)
                cell_lines = _wrap(cell, chars)
                wrapped_cells.append(cell_lines)
                max_lines = max(max_lines, len(cell_lines))
            row_height = max(28, 14 + (max_lines * 10))
            self.ensure(row_height + 4)
            y0 = self.y - row_height
            self.rect(x, y0, sum(widths), row_height, LIGHT if row_idx == 0 else (255, 255, 255), True)
            self.rect(x, y0, sum(widths), row_height, BORDER, False)
            cx = x
            for col_idx, cell in enumerate(row):
                font = "F2" if row_idx == 0 else "F1"
                ty = y0 + row_height - 14
                for cell_line in wrapped_cells[col_idx]:
                    self.text(cx + 6, ty, cell_line, 8, font, DARK)
                    ty -= 10
                if col_idx < col_count - 1:
                    self.line(cx + widths[col_idx], y0, cx + widths[col_idx], y0 + row_height, BORDER)
                cx += widths[col_idx]
            self.y -= row_height
        self.y -= 12

    def cover(self, subtitle: str) -> None:
        self.new_page()
        assert self.page is not None
        self.rect(0, 0, A4_WIDTH, A4_HEIGHT, (252, 253, 255), True)
        self.rect(0, A4_HEIGHT - 210, A4_WIDTH, 210, BLUE, True)
        self.rect(0, A4_HEIGHT - 214, A4_WIDTH, 4, (95, 158, 209), True)
        self.text(MARGIN_X, A4_HEIGHT - 112, "NAE PLATFORM", 14, "F2", (255, 255, 255))
        self.text(MARGIN_X, A4_HEIGHT - 158, "Informe final del proyecto", 30, "F2", (255, 255, 255))
        self.text(MARGIN_X, A4_HEIGHT - 184, subtitle, 12, "F1", (229, 238, 247))
        cover_lines = _wrap(
            "De la encuesta al dashboard: captura, procesamiento, base de datos y visualizacion",
            _chars_for_width(CONTENT_WIDTH, 14),
        )
        cy = 124
        for line in cover_lines:
            self.text(MARGIN_X, cy, line, 14, "F2", DARK)
            cy -= 18
        self.text(MARGIN_X, 86, "Corte funcional para piloto - 23 de junio de 2026", 11, "F1", MUTED)
        self.text(MARGIN_X, 62, "URL de produccion: https://nae-plataforma.mes.gob.cu", 10, "F1", MUTED)

    def architecture_page(self) -> None:
        self.new_page()
        self.heading("Arquitectura funcional", 2)
        boxes = [
            ("Google Forms", "Captura de encuesta"),
            ("FastAPI", "Recepcion y seguridad"),
            ("RAW", "Payload original"),
            ("STAGING", "Validacion"),
            ("OPERATIONAL", "Modelo relacional"),
            ("ANALYTICS", "Dimensiones y hechos"),
            ("Dashboard", "Consulta y CSV"),
        ]
        x = MARGIN_X
        y = self.y - 20
        box_w = 150
        box_h = 52
        gap = 16
        for idx, (title, desc) in enumerate(boxes):
            col = idx % 3
            row = idx // 3
            bx = x + col * (box_w + gap)
            by = y - row * 95
            self.rect(bx, by - box_h, box_w, box_h, LIGHT, True)
            self.rect(bx, by - box_h, box_w, box_h, BLUE if idx in (0, 1, 6) else BORDER, False)
            self.text(bx + 10, by - 20, title, 11, "F2", BLUE)
            self.text(bx + 10, by - 38, desc, 8, "F1", MUTED)
        self.y = y - 240
        self.paragraph(
            "La arquitectura separa la recepcion, validacion, normalizacion y analitica para proteger el dato original y permitir correcciones sin perder trazabilidad."
        )

    def finish(self, output: Path) -> None:
        self.footer()
        self.doc.write(output)


def parse_markdown(md: str) -> tuple[str, str, list[str], list[str]]:
    lines = md.splitlines()
    title = "Informe final del proyecto NAE Platform"
    subtitle = "Corte funcional para piloto"
    sections: list[str] = []
    for line in lines:
        if line.startswith("# "):
            title = _plain(line[2:])
        elif line.startswith("Fecha:"):
            subtitle = _plain(line)
        elif line.startswith("## "):
            sections.append(_plain(line[3:]))
    return title, subtitle, sections, lines


def render_report(markdown_path: Path, output_path: Path) -> None:
    title, subtitle, sections, lines = parse_markdown(markdown_path.read_text(encoding="utf-8"))
    renderer = ReportRenderer(title)
    renderer.cover(subtitle)
    renderer.new_page()
    renderer.heading("Contenido", 2)
    for idx, section in enumerate(sections, start=1):
        renderer.bullet(f"{idx}. {section}")
    renderer.architecture_page()

    in_code = False
    code_lines: List[str] = []
    pending_table: List[List[str]] = []

    def flush_table() -> None:
        nonlocal pending_table
        if pending_table:
            renderer.table(pending_table)
            pending_table = []

    for line in lines:
        if line.startswith("# "):
            continue
        if line.startswith("```"):
            if in_code:
                renderer.code_block(code_lines)
                code_lines = []
                in_code = False
            else:
                flush_table()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(set(cell) <= {"-", " "} for cell in cells):
                continue
            pending_table.append(cells)
            continue
        flush_table()
        if line.startswith("## "):
            renderer.heading(line[3:], 2)
        elif line.startswith("### "):
            renderer.heading(line[4:], 3)
        elif line.startswith("- "):
            renderer.bullet(line[2:])
        elif line.strip():
            renderer.paragraph(line)
        else:
            renderer.y -= 3

    flush_table()
    renderer.finish(output_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render_report(args.markdown, args.output)


if __name__ == "__main__":
    main()
