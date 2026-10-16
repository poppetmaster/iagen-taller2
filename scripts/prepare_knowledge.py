"""Prepara documentos derivados; no crea políticas ni atributos comerciales nuevos."""
import csv
import hashlib
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def policy_sections(policy):
    """La misma representación alimenta PDF, FAQ y controles de consistencia."""
    conditions = {"opened": {False: "sin abrir", True: "abierto"},
                  "used": {False: "sin uso", True: "usado"},
                  "good_condition": {True: "en buen estado", False: "con deterioro"},
                  "packaging_ok": {True: "con empaque en condiciones", False: "sin empaque adecuado"}}
    sections = [
        ("alcance", "Alcance de la demostración", policy["description"]),
        ("plazo", "Plazo de devolución",
         f"La devolución ordinaria tiene un plazo de {policy['return_window_days']} días calendario desde la entrega efectiva. El último día está incluido. Si falta la fecha de entrega, debe confirmarse antes de decidir."),
        ("exclusiones", "Categorías excluidas de devolución ordinaria",
         "La política excluye de devolución ordinaria estas categorías: " + ", ".join(policy["ordinary_excluded_categories"]) + ". Esta exclusión no sustituye la revisión de una reclamación especial."),
        ("reclamaciones", "Defectos, daños y productos equivocados",
         "Los motivos que requieren revisión humana son: " + ", ".join(policy["human_review_reasons"]) + ". Las reclamaciones por defecto, daño o producto equivocado se revisan antes de aplicar las exclusiones de devolución ordinaria."),
    ]
    for category, values in policy["conditions_by_category"].items():
        text = ", ".join(conditions[key][value] for key, value in values.items())
        sections.append(("condiciones_" + category, "Condiciones: " + category,
                         f"Para la categoría {category}, el producto debe estar {text}. También debe cumplir el plazo de devolución. Si una condición no se conoce, se solicita el dato; no se presume su cumplimiento."))
    sections.extend([
        ("procedimiento", "Cómo solicitar una devolución", " ".join(policy["steps"])),
        ("revision", "Cuándo solicitar revisión humana", policy["escalation"]),
    ])
    return sections


def expected_faq(policy):
    questions = {
        "alcance": "¿La política de EcoMarket de este ejercicio es real?",
        "plazo": "¿Cuántos días tengo para devolver un producto?",
        "exclusiones": "¿Se pueden devolver productos perecederos por cambio de opinión?",
        "reclamaciones": "¿Qué hago si recibo un producto defectuoso, dañado o equivocado?",
        "procedimiento": "¿Cómo inicio el trámite de devolución?",
        "revision": "¿Cuándo debo solicitar revisión humana?",
    }
    return [{"id": key, "question": questions.get(key, "¿Qué condiciones exige la devolución de la categoría " + key.removeprefix("condiciones_") + "?"),
             "answer": text, "source": "data/return_policy.json", "policy_id": policy["policy_id"]}
            for key, title, text in policy_sections(policy)]


def expected_products(orders):
    return sorted({(o["product"], o["category"]) for o in orders})


def verify():
    policy = read("return_policy.json")
    manifest = json.loads((ROOT / "knowledge/provenance.json").read_text(encoding="utf-8"))
    for name, value in manifest["sha256"].items():
        if digest(ROOT / name) != value:
            raise ValueError(f"Cambió {name}. Regenera los documentos y vuelve a indexar.")
    faq = json.loads((ROOT / "knowledge/faq.json").read_text(encoding="utf-8"))
    if faq != expected_faq(policy):
        raise ValueError("Las FAQ no corresponden a la política canónica.")
    with (ROOT / "knowledge/catalogo.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if [(r["product"], r["category"]) for r in rows] != expected_products(read("orders.json")):
        raise ValueError("El catálogo no corresponde a los productos de los pedidos.")
    from pypdf import PdfReader
    reader = PdfReader(ROOT / "knowledge/politica_devoluciones.pdf")
    if len(reader.pages) != len(policy_sections(policy)):
        raise ValueError("El PDF no contiene todas las secciones de la política.")
    for page, (_, title, text) in zip(reader.pages, policy_sections(policy)):
        content = " ".join(page.extract_text().split())
        if " ".join(text.split()) not in content or title not in content:
            raise ValueError("El contenido del PDF difiere de la política.")
    return {"policy_id": policy["policy_id"], "sections": len(faq), "products": len(rows),
            "status": "Documentos coherentes con sus fuentes canónicas."}


def main():
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.pagesizes import A5
    policy = read("return_policy.json")
    folder = ROOT / "knowledge"
    folder.mkdir(exist_ok=True)
    with (folder / "catalogo.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["product", "category", "source", "fictional"])
        for product, category in expected_products(read("orders.json")):
            writer.writerow([product, category, "data/orders.json", "true"])
    (folder / "faq.json").write_text(json.dumps(expected_faq(policy), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PolicyBody", fontName="Helvetica", fontSize=12, leading=18, spaceAfter=12, alignment=TA_LEFT))
    styles["Title"].fontSize = 21
    styles["Title"].leading = 26
    styles["Title"].textColor = colors.HexColor("#175C4C")
    story = []
    sections = policy_sections(policy)
    for index, (key, title, text) in enumerate(sections):
        if index:
            story.append(PageBreak())
        story += [Paragraph("EcoMarket | Taller 2", styles["Normal"]), Spacer(1, 24),
                  Paragraph(escape(title), styles["Title"]), Spacer(1, 12),
                  Paragraph(escape(text), styles["PolicyBody"]), Spacer(1, 16),
                  Paragraph("Documento académico. Política ficticia " + policy["policy_id"] + ".", styles["Normal"]),
                  Spacer(1, 8), Paragraph("Fuente: data/return_policy.json. Sección: " + key + ".", styles["Normal"])]
    def footer(canvas, doc):
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#536760"))
        canvas.drawString(36, 25, f"Política de demostración | {doc.page}/{len(sections)}")
    SimpleDocTemplate(str(folder / "politica_devoluciones.pdf"), pagesize=A5,
                      rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=42,
                      title="EcoMarket - Política de devoluciones académica", author="Grupo Taller 2").build(story, onFirstPage=footer, onLaterPages=footer)
    names = ["data/orders.json", "data/return_policy.json", "scripts/prepare_knowledge.py",
             "knowledge/politica_devoluciones.pdf", "knowledge/catalogo.csv", "knowledge/faq.json"]
    manifest = {"origin": "https://github.com/poppetmaster/iagen-taller1", "policy_id": policy["policy_id"],
                "note": "Tres representaciones documentales derivadas de dos fuentes académicas; no son fuentes independientes.",
                "sha256": {name: digest(ROOT / name) for name in names}}
    (folder / "provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(verify(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
