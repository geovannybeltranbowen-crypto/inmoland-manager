from pathlib import Path
import sqlite3
import sys

try:
    from docx import Document
    from docx.shared import Inches, Pt
except ImportError:
    print("Falta python-docx. Instálalo con: python -m pip install python-docx")
    raise SystemExit(1)

ROOT = Path.cwd()
OUTPUT = ROOT.parent / "INMOLAND_Manager_Codigo_Completo.docx"

EXCLUDED_DIRS = {
    ".venv", "venv", "__pycache__", ".git", ".idea", ".vscode",
    "node_modules", "staticfiles", "media", "dist", "build"
}
EXCLUDED_NAMES = {
    ".env", ".env.local", ".env.production",
    "secrets.json", "credentials.json"
}
EXCLUDED_SUFFIXES = {
    ".pyc", ".pyo", ".sqlite3", ".db", ".png", ".jpg", ".jpeg",
    ".gif", ".webp", ".ico", ".pdf", ".xlsx", ".xls", ".zip",
    ".docx", ".pptx", ".woff", ".woff2", ".ttf", ".eot"
}
# Code/config/documentation extensions that are useful as text.
INCLUDED_SUFFIXES = {
    ".py", ".html", ".htm", ".css", ".js", ".json", ".toml",
    ".ini", ".cfg", ".txt", ".md", ".yaml", ".yml", ".sql",
    ".xml", ".sh", ".bat", ".ps1"
}
SPECIAL_NAMES = {
    "Dockerfile", "Procfile", "Makefile", ".gitignore",
    ".dockerignore", "requirements.txt"
}

def excluded(path):
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return True
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return True
    # Do not embed files that may contain secrets by name.
    low = path.name.lower()
    if any(word in low for word in ("secret", "credential", "password", "token", "private_key")):
        return True
    return False

files = []
for p in ROOT.rglob("*"):
    if not p.is_file() or excluded(p):
        continue
    if p.suffix.lower() in INCLUDED_SUFFIXES or p.name in SPECIAL_NAMES:
        files.append(p)
files.sort(key=lambda p: str(p.relative_to(ROOT)).lower())

doc = Document()
sec = doc.sections[0]
sec.top_margin = Inches(0.65)
sec.bottom_margin = Inches(0.65)
sec.left_margin = Inches(0.7)
sec.right_margin = Inches(0.7)

normal = doc.styles["Normal"]
normal.font.name = "Consolas"
normal.font.size = Pt(8)

doc.add_heading("INMOLAND Manager — Código fuente y estructura", 0)
doc.add_paragraph("Documento generado automáticamente desde la carpeta local del proyecto.")
doc.add_paragraph(f"Carpeta fuente: {ROOT}")
doc.add_paragraph("Nota: este documento incluye archivos de texto/código. No incluye el entorno virtual, secretos .env, archivos binarios ni los datos personales de la base de datos.")
doc.add_heading("Índice de archivos incluidos", level=1)
for p in files:
    doc.add_paragraph(str(p.relative_to(ROOT)), style="List Bullet")

for p in files:
    rel = str(p.relative_to(ROOT))
    doc.add_page_break()
    doc.add_heading(rel, level=1)
    try:
        text = p.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = p.read_text(encoding="cp1252")
        except Exception as e:
            doc.add_paragraph(f"[No se pudo leer este archivo como texto: {e}]")
            continue
    except Exception as e:
        doc.add_paragraph(f"[No se pudo leer este archivo: {e}]")
        continue
    # Remove XML-invalid control characters before inserting text into Word.
    # Keep tab, newline and carriage return; remove NULL bytes and other controls.
    text = "".join(
        ch for ch in text
        if ch in "\\t\\n\\r" or ord(ch) >= 32
    )
    # Add code in manageable chunks.
    for start in range(0, max(len(text), 1), 3000):
        chunk = text[start:start + 3000]
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(0)
        run = para.add_run(chunk if chunk else "[Archivo vacío]")
        run.font.name = "Consolas"
        run.font.size = Pt(7)

# Add schema only (table names + CREATE TABLE SQL), not customer/financial records.
db_candidates = [ROOT / "db.sqlite3", ROOT / "db.sqlite", ROOT / "database.sqlite3"]
db_path = next((p for p in db_candidates if p.exists()), None)
if db_path:
    doc.add_page_break()
    doc.add_heading("Esquema de la base de datos (sin registros)", level=1)
    doc.add_paragraph(f"Base detectada: {db_path.name}. Por privacidad, solo se exporta el esquema, no los datos.")
    try:
        con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
        rows = con.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for name, sql in rows:
            doc.add_heading(name, level=2)
            para = doc.add_paragraph()
            run = para.add_run(sql or "[Sin definición SQL disponible]")
            run.font.name = "Consolas"
            run.font.size = Pt(8)
        con.close()
    except Exception as e:
        doc.add_paragraph(f"No se pudo leer el esquema: {e}")
else:
    doc.add_paragraph("No se encontró db.sqlite3 en la raíz del proyecto. El esquema de la base de datos no fue incluido.")

doc.save(OUTPUT)
print(f"Documento creado: {OUTPUT}")
print(f"Archivos de código/documentación incluidos: {len(files)}")
print("Revisa el documento antes de compartirlo para confirmar que no contiene información confidencial.")
