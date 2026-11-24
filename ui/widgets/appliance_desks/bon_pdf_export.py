# -*- coding: utf-8 -*-
"""
Clean A4 PDF Exporter for Order Desk Vouchers (Bon Comptant, Bon Crédit, Bon de Livraison).
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox

from ui.formatting import format_money

logger = logging.getLogger("StockLam.UI.BonPDFExport")

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


BOND_TITLES = {
    "BON_C": "BON COMPTANT",
    "BON_CREDIT": "BON CRÉDIT",
    "BON_LIVRAISON": "BON DE LIVRAISON",
    "BON_VERSEMENT": "BON VERSEMENT",
}


def export_order_bon_to_pdf(
    data_manager: Any,
    order_data: Dict[str, Any],
    parent_widget=None,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Exports any Order Desk bon (BC, BCréde, BL) to a clean A4 PDF file.
    Returns the generated file path on success, or None if cancelled/failed.
    """
    if not HAS_REPORTLAB:
        if parent_widget:
            QMessageBox.warning(parent_widget, "PDF indisponible", "La bibliothèque 'reportlab' n'est pas installée.")
        return None

    # Hydrate full order record if only minimal dict was passed
    order_id = order_data.get("Order_ID") or order_data.get("order_id")
    full_order = dict(order_data)
    if data_manager and hasattr(data_manager, "bonds") and order_id:
        if not full_order.get("lines") or not full_order.get("Client_Name"):
            fetched = data_manager.bonds.get_order_by_id(int(order_id))
            if isinstance(fetched, dict):
                merged = dict(fetched)
                merged.update({k: v for k, v in full_order.items() if v is not None and k != "lines"})
                if not merged.get("lines"):
                    merged["lines"] = fetched.get("lines") or []
                full_order = merged

    order_num = str(
        full_order.get("Order_Number")
        or full_order.get("order_number")
        or f"BON-{order_id or 0}"
    )
    bond_type = str(full_order.get("Bond_Type") or full_order.get("bond_type") or "BON_C").upper()
    doc_title = BOND_TITLES.get(bond_type, "BON DE COMMANDE")
    client_name = str(full_order.get("Client_Name") or "Client Comptoir")
    client_phone = str(full_order.get("Client_Phone") or "")
    delivery_addr = str(full_order.get("Delivery_Address") or "")
    raw_date = str(full_order.get("Order_Date") or datetime.now().strftime("%Y-%m-%d %H:%M"))
    total_ttc = float(full_order.get("Total_Amount_TTC") or full_order.get("total_ttc") or 0.0)
    paid_so_far = float(full_order.get("Amount_Paid_So_Far") or 0.0)
    rem_credit = float(full_order.get("Amount_Remaining_Credit") if full_order.get("Amount_Remaining_Credit") is not None else total_ttc)
    lines = full_order.get("lines") or []

    # Resolve company settings safely
    company_name = "StockLam Électroménager"
    company_addr = ""
    company_phone = ""
    if data_manager and hasattr(data_manager, "company_settings"):
        try:
            st = data_manager.company_settings.get_settings() or {}
            if isinstance(st, dict):
                company_name = st.get("lab_name") or st.get("company_name") or company_name
                company_addr = st.get("lab_address") or st.get("address") or ""
                company_phone = st.get("lab_phone") or st.get("phone") or ""
        except Exception:
            pass

    path = output_path
    if not path:
        safe_num = order_num.replace("/", "-").replace(" ", "_")
        default_name = f"{safe_num}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Exporter le Bon en PDF",
            default_name,
            "Fichiers PDF (*.pdf)",
        )
        if not path:
            return None

    try:
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=1.6 * cm,
            rightMargin=1.6 * cm,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
        )
        styles = getSampleStyleSheet()
        teal = colors.HexColor("#007572")
        slate = colors.HexColor("#334155")
        border_gray = colors.HexColor("#CBD5E1")
        bg_light = colors.HexColor("#F8FAFC")

        title_style = ParagraphStyle(
            "BonTitle",
            parent=styles["Normal"],
            fontSize=15,
            leading=19,
            textColor=teal,
            fontName="Helvetica-Bold",
        )
        normal_style = ParagraphStyle(
            "BonNormal",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            textColor=slate,
        )

        elements = []

        # Header Table (Store on left, Bon & Client on right)
        left_lines = [f"<b>{company_name}</b>"]
        if company_addr:
            left_lines.append(company_addr)
        if company_phone:
            left_lines.append(f"Tél : {company_phone}")
        left_lines.append(f"Date : {raw_date}")

        right_lines = [
            f"<b>N° Bon : {order_num}</b>",
            f"Client : <b>{client_name}</b>",
        ]
        if client_phone:
            right_lines.append(f"Tél : {client_phone}")
        if delivery_addr:
            right_lines.append(f"Livraison : {delivery_addr}")

        elements.append(Paragraph(doc_title, title_style))
        elements.append(Spacer(1, 0.35 * cm))

        hdr_table = Table(
            [
                [
                    Paragraph("<br/>".join(left_lines), normal_style),
                    Paragraph("<br/>".join(right_lines), normal_style),
                ]
            ],
            colWidths=[8.9 * cm, 8.9 * cm],
        )
        hdr_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), bg_light),
                    ("BOX", (0, 0), (-1, -1), 0.6, border_gray),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(hdr_table)
        elements.append(Spacer(1, 0.5 * cm))

        # Articles Table
        table_rows = [["#", "Désignation", "Marque", "Couleur", "Qté", "Prix Unit. TTC", "Total TTC"]]
        for idx, ln in enumerate(lines, start=1):
            p_name = str(ln.get("Product_Name") or ln.get("name") or "")
            brand = str(ln.get("Brand_Mark") or ln.get("mark") or "-")
            color = str(ln.get("Color_Finish") or ln.get("coloure") or ln.get("color") or "-")
            qty = int(ln.get("Quantity_Ordered") or ln.get("quantity") or 1)
            u_ttc = float(ln.get("Unit_Price_TTC") or ln.get("unit_price_ttc") or 0.0)
            l_ttc = float(ln.get("Line_Total_TTC") or (qty * u_ttc))
            table_rows.append([
                str(idx),
                Paragraph(p_name, normal_style),
                brand,
                color,
                str(qty),
                f"{format_money(u_ttc)} DA",
                f"{format_money(l_ttc)} DA",
            ])

        items_table = Table(
            table_rows,
            colWidths=[1.0 * cm, 6.2 * cm, 2.5 * cm, 2.1 * cm, 1.2 * cm, 2.4 * cm, 2.4 * cm],
            repeatRows=1,
        )
        items_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), teal),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (4, 0), (4, -1), "CENTER"),
                    ("ALIGN", (5, 0), (6, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_light]),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(items_table)
        elements.append(Spacer(1, 0.45 * cm))

        # Summary Totals
        tot_rows = [["TOTAL TTC", f"{format_money(total_ttc)} DA"]]
        if bond_type == "BON_LIVRAISON" and (paid_so_far > 0 or rem_credit < total_ttc):
            tot_rows.append(["Acompte Versé", f"{format_money(paid_so_far)} DA"])
            tot_rows.append(["Reste à Payer", f"{format_money(rem_credit)} DA"])

        tot_table = Table(tot_rows, colWidths=[4.2 * cm, 3.6 * cm], hAlign="RIGHT")
        tot_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), bg_light),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("TEXTCOLOR", (0, 0), (-1, 0), teal),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOX", (0, 0), (-1, -1), 0.6, border_gray),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, border_gray),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(tot_table)

        doc.build(elements)

        if not os.environ.get("PYTEST_CURRENT_TEST") and hasattr(os, "startfile"):
            try:
                os.startfile(path)
            except Exception:
                pass

        return path
    except Exception as err:
        logger.error(f"Failed to generate Bon PDF: {err}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Erreur PDF", f"Impossible d'exporter le PDF :\n{err}")
        return None


def export_exit_bon_to_pdf(
    data_manager: Any,
    order_data: Dict[str, Any],
    exit_info: Optional[Dict[str, Any]] = None,
    parent_widget=None,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """
    Exports a Sortie Magasin exit voucher ('Bon de Sortie' or 'Bon Rouge') to a clean A4 PDF.
    """
    if not HAS_REPORTLAB:
        if parent_widget:
            QMessageBox.warning(parent_widget, "PDF indisponible", "La bibliothèque 'reportlab' n'est pas installée.")
        return None

    exit_info = dict(exit_info or {})
    doc_type = str(exit_info.get("exit_doc_type") or "BON_SORTIE").strip().upper()
    is_rouge = doc_type == "BON_ROUGE"
    doc_title = "BON ROUGE" if is_rouge else "BON DE SORTIE"
    exit_num = str(
        exit_info.get("exit_bond_number")
        or order_data.get("Exit_Bond_Number")
        or f"{'BRG' if is_rouge else 'BS'}-{order_data.get('Order_ID', 0)}"
    )
    gate_pass = str(exit_info.get("gate_pass") or "")
    order_num = str(order_data.get("Order_Number") or f"#{order_data.get('Order_ID', 0)}")
    client_name = str(order_data.get("Client_Name") or "Client Comptoir")
    client_phone = str(order_data.get("Client_Phone") or "")
    delivery_addr = str(order_data.get("Delivery_Address") or "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    company_name = "StockLam Électroménager"
    company_addr = ""
    company_phone = ""
    if data_manager and hasattr(data_manager, "company_settings"):
        try:
            st = data_manager.company_settings.get_settings() or {}
            if isinstance(st, dict):
                company_name = st.get("lab_name") or st.get("company_name") or company_name
                company_addr = st.get("lab_address") or st.get("address") or ""
                company_phone = st.get("lab_phone") or st.get("phone") or ""
        except Exception:
            pass

    path = output_path
    if not path:
        safe_num = exit_num.replace("/", "-").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            f"Exporter le {doc_title} en PDF",
            f"{safe_num}.pdf",
            "Fichiers PDF (*.pdf)",
        )
        if not path:
            return None

    try:
        doc = SimpleDocTemplate(
            path,
            pagesize=A4,
            leftMargin=1.6 * cm,
            rightMargin=1.6 * cm,
            topMargin=1.6 * cm,
            bottomMargin=1.6 * cm,
        )
        styles = getSampleStyleSheet()
        accent = colors.HexColor("#B91C1C") if is_rouge else colors.HexColor("#007572")
        accent_bg = colors.HexColor("#FEF2F2") if is_rouge else colors.HexColor("#F0FDFA")
        slate = colors.HexColor("#334155")
        border_gray = colors.HexColor("#CBD5E1")
        bg_light = colors.HexColor("#F8FAFC")

        title_style = ParagraphStyle(
            "ExitDocTitle",
            parent=styles["Heading1"],
            fontSize=17,
            textColor=accent,
            spaceAfter=2,
            leading=21,
        )
        sub_style = ParagraphStyle(
            "ExitDocSub",
            parent=styles["Normal"],
            fontSize=9.5,
            textColor=slate,
            leading=13,
        )
        cell_style = ParagraphStyle(
            "ExitCellStyle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#1E293B"),
            leading=12,
        )

        elements = []
        hdr_left = [Paragraph(f"<b>{company_name}</b>", title_style)]
        if company_addr:
            hdr_left.append(Paragraph(company_addr, sub_style))
        if company_phone:
            hdr_left.append(Paragraph(f"Tél : {company_phone}", sub_style))

        hdr_right = [
            Paragraph(f"<b>{doc_title}</b>", ParagraphStyle("ER", parent=title_style, alignment=2, fontSize=16)),
            Paragraph(f"<b>N° :</b> {exit_num}", ParagraphStyle("ER2", parent=sub_style, alignment=2)),
            Paragraph(f"<b>Bon Commande :</b> {order_num}", ParagraphStyle("ER3", parent=sub_style, alignment=2)),
            Paragraph(f"<b>Date :</b> {now_str}", ParagraphStyle("ER4", parent=sub_style, alignment=2)),
        ]
        if gate_pass:
            hdr_right.append(Paragraph(f"<b>Laissez-passer :</b> {gate_pass}", ParagraphStyle("ER5", parent=sub_style, alignment=2)))

        hdr_tbl = Table([[hdr_left, hdr_right]], colWidths=[9.5 * cm, 8.3 * cm])
        hdr_tbl.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, 0), 1.8, accent),
                ]
            )
        )
        elements.append(hdr_tbl)
        elements.append(Spacer(1, 0.4 * cm))

        # Client Info
        client_rows = [
            [
                Paragraph(f"<b>Client :</b> {client_name}", cell_style),
                Paragraph(f"<b>Téléphone :</b> {client_phone or '—'}", cell_style),
            ],
            [
                Paragraph(f"<b>Adresse de livraison :</b> {delivery_addr or '—'}", cell_style),
                Paragraph(f"<b>Statut :</b> Sortie Magasin Validée", cell_style),
            ],
        ]
        c_tbl = Table(client_rows, colWidths=[10.5 * cm, 7.3 * cm])
        c_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), accent_bg),
                    ("BOX", (0, 0), (-1, -1), 0.7, border_gray),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(c_tbl)
        elements.append(Spacer(1, 0.4 * cm))

        # Items Table
        scanned_lines = exit_info.get("scanned_lines") or []
        raw_lines = order_data.get("lines") or []
        table_rows = [["#", "Produit", "Marque / Couleur", "Réf / Code-Barres", "Qté", "Codes Scannés"]]
        total_units = 0
        if scanned_lines:
            for idx, st in enumerate(scanned_lines, 1):
                qty = int(st.get("qty_required") or st.get("qty_ordered") or 1)
                total_units += qty
                meta = " / ".join(p for p in (st.get("brand", ""), st.get("color", "")) if p) or "—"
                codes_str = ", ".join(st.get("scanned_codes") or []) or "VÉRIFIÉ"
                table_rows.append([
                    str(idx),
                    Paragraph(str(st.get("product_name") or ""), cell_style),
                    Paragraph(meta, cell_style),
                    Paragraph(str(st.get("code_display") or "—"), cell_style),
                    str(qty),
                    Paragraph(codes_str, cell_style),
                ])
        else:
            for idx, ln in enumerate(raw_lines, 1):
                qty = int(ln.get("Quantity_Ordered") or 1)
                total_units += qty
                meta = " / ".join(p for p in (ln.get("Brand_Mark", ""), ln.get("Color_Finish", "")) if p) or "—"
                table_rows.append([
                    str(idx),
                    Paragraph(str(ln.get("Product_Name") or ""), cell_style),
                    Paragraph(meta, cell_style),
                    Paragraph(str(ln.get("Barcode") or ln.get("Manuf_Cat_No") or "—"), cell_style),
                    str(qty),
                    Paragraph("VÉRIFIÉ", cell_style),
                ])

        items_tbl = Table(
            table_rows,
            colWidths=[0.9 * cm, 5.5 * cm, 2.8 * cm, 3.0 * cm, 1.3 * cm, 4.3 * cm],
            repeatRows=1,
        )
        items_tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), accent),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (0, 0), (0, -1), "CENTER"),
                    ("ALIGN", (4, 0), (4, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.5, border_gray),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, bg_light]),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        elements.append(items_tbl)
        elements.append(Spacer(1, 0.4 * cm))

        summary_p = Paragraph(f"<b>Total articles sortis :</b> {total_units} unité(s)", sub_style)
        elements.append(summary_p)
        elements.append(Spacer(1, 0.9 * cm))

        # Signatures
        sig_tbl = Table(
            [
                ["Signature Magasinier", "Signature Sécurité / Contrôle", "Signature Client / Livreur"],
                ["\n\n______________________", "\n\n______________________", "\n\n______________________"],
            ],
            colWidths=[5.9 * cm, 5.9 * cm, 6.0 * cm],
        )
        sig_tbl.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), slate),
                ]
            )
        )
        elements.append(sig_tbl)

        doc.build(elements)
        if not os.environ.get("PYTEST_CURRENT_TEST") and hasattr(os, "startfile"):
            try:
                os.startfile(path)
            except Exception:
                pass
        return path
    except Exception as err:
        logger.error(f"Failed to generate Exit Bon PDF: {err}")
        if parent_widget:
            QMessageBox.critical(parent_widget, "Erreur PDF", f"Impossible d'exporter le {doc_title} :\n{err}")
        return None
