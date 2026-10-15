"""Exportación del resultado completo de un cálculo de sueldos."""

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from payroll.calculations import horas_a_horasminutos


def crear_pdf_calculo(run, registros):
    """Genera el resumen y todos los registros, con encabezados en cada página."""
    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida, pagesize=landscape(A4), rightMargin=24, leftMargin=24,
        topMargin=28, bottomMargin=32, title="Reporte de sueldos",
    )
    estilos = getSampleStyleSheet()
    celda = ParagraphStyle("Celda", fontName="Helvetica", fontSize=7, leading=9)
    cabecera = ParagraphStyle("Cabecera", parent=celda, textColor=colors.white, fontName="Helvetica-Bold")

    def texto(valor, estilo=celda):
        return Paragraph(escape(str(valor if valor is not None else "-")), estilo)

    def monto(valor):
        return f"Gs. {float(valor or 0):,.2f}"

    story = [Paragraph("Reporte de sueldos", estilos["Title"])]
    fecha = run.created_at.strftime("%d/%m/%Y %H:%M")
    story.append(texto(f"{run.source_name or 'Cálculo'} | {fecha} | Valor por hora: {monto(run.valor_por_hora)} | Seguro IPS: {run.seguro_ips}"))
    story.append(Spacer(1, 12))
    bruto = float(run.total_salario_bruto or run.total_sueldos or 0)
    normales = float(run.total_monto_horas_normales or (run.total_horas_normales or 0) * (run.valor_por_hora or 0))
    especiales = float(run.total_monto_horas_especiales or (run.total_horas_especiales or 0) * (run.valor_por_hora or 0) * 1.3)
    feriados = max(0, float(run.total_monto_feriados or bruto - normales - especiales))
    if (not run.feriados and feriados <= 0.01) or feriados < 0.015:
        feriados = 0
    resumen = [
        ["Registros", str(len(registros)), "Total horas", horas_a_horasminutos(float(run.total_horas or 0))],
        ["Horas normales", horas_a_horasminutos(float(run.total_horas_normales or 0)), "Monto normal", monto(normales)],
        ["Horas especiales", horas_a_horasminutos(float(run.total_horas_especiales or 0)), "Monto especial", monto(especiales)],
        ["Feriados", monto(feriados), "Bonificación", monto(run.total_bonificacion)],
        ["Salario bruto", monto(bruto), "Descuento IPS", monto(run.total_descuento_ips)],
        ["Aporte empleador IPS", monto(run.total_aporte_empleador_ips), "Neto tras IPS", monto(run.total_salario_neto_ips or bruto - float(run.total_descuento_ips or 0))],
        ["Otros descuentos", monto(sum(float(r.descuento_inventario or 0) + float(r.descuento_caja or 0) + float(r.retiro or 0) for r in registros)), "Sueldo final a pagar", monto(sum(float(r.sueldo_final or 0) for r in registros))],
    ]
    tabla_resumen = Table(resumen, colWidths=[doc.width * p for p in (0.25, 0.25, 0.25, 0.25)])
    tabla_resumen.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef3fb")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.extend([tabla_resumen, Spacer(1, 16), Paragraph("Detalle por empleado", estilos["Heading2"])])
    encabezados = ["Empleado", "Fecha", "Entrada", "Salida", "Feriado", "Horas", "Normales", "Especiales", "Desc. Inv.", "Desc. Caja", "Desc. IPS", "Retiro", "Sueldo final"]
    filas = [[texto(t, cabecera) for t in encabezados]]
    for r in registros:
        valores = [r.empleado, r.fecha, r.entrada, r.salida, r.feriado, r.horas_trabajadas,
                   horas_a_horasminutos(float(r.horas_normales or 0)), horas_a_horasminutos(float(r.horas_especiales or 0)),
                   *[f"{float(v or 0):,.2f}" for v in (r.descuento_inventario, r.descuento_caja, r.descuento_ips, r.retiro, r.sueldo_final)]]
        filas.append([texto(v) for v in valores])
    pesos = [16, 9, 5, 5, 5, 5, 6, 6, 7, 7, 7, 7, 9]
    detalle = Table(filas, colWidths=[doc.width * p / sum(pesos) for p in pesos], repeatRows=1)
    detalle.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dbe2ed")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(detalle)

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawRightString(doc.pagesize[0] - 24, 16, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=pie, onLaterPages=pie)
    salida.seek(0)
    return salida
