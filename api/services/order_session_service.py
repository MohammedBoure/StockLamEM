"""Services REST pour les sessions de commandes (Bureaux -> Commandes)."""

from __future__ import annotations

from typing import Any, Dict, List


def list_clients(data_manager: Any, search: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Retourne les clients actifs filtrés pour l'attribution de session mobile."""
    clients_mgr = getattr(data_manager, "clients", None)
    if clients_mgr is None or not hasattr(clients_mgr, "get_all_clients"):
        return [{"client_id": 1, "full_name": "Client Divers", "phone": "", "price_tier": "Prix_1"}]

    raw = clients_mgr.get_all_clients() or []
    q = str(search or "").strip().lower()
    results: List[Dict[str, Any]] = []
    for c in raw:
        name = str(c.get("Full_Name") or "")
        phone = str(c.get("Phone") or "")
        if q and q not in name.lower() and q not in phone.lower():
            continue
        results.append({
            "client_id": int(c.get("Client_ID") or 0),
            "full_name": name,
            "phone": phone,
            "price_tier": str(c.get("Price_Tier") or "Prix_1"),
        })
        if len(results) >= max(1, int(limit or 50)):
            break
    return results


def search_catalog(data_manager: Any, search: str = "", limit: int = 30) -> List[Dict[str, Any]]:
    """Recherche les produits disponibles en stock pour ajout dans une session."""
    serials_mgr = getattr(data_manager, "serials", None)
    if serials_mgr is None or not hasattr(serials_mgr, "get_catalog_with_theoretical_stock"):
        return []

    items = serials_mgr.get_catalog_with_theoretical_stock(only_available=True) or []
    q = str(search or "").strip().lower()
    results: List[Dict[str, Any]] = []
    for p in items:
        avail = int(p.get("Available_Theoretical_Qty") or 0)
        if avail <= 0:
            continue
        name = str(p.get("Product_Name") or "")
        brand = str(p.get("Brand_Mark") or "")
        ref = str(
            p.get("Primary_Ref")
            or p.get("Manuf_Cat_No")
            or p.get("Reference")
            or p.get("Product_Code")
            or ""
        )
        all_refs = str(p.get("All_Refs") or "")
        barcode = str(p.get("Barcode") or "")
        if q:
            haystack = f"{name} {brand} {ref} {all_refs} {barcode}".lower()
            if q not in haystack:
                continue
        results.append({
            "product_id": int(p.get("Product_ID") or 0),
            "product_name": name,
            "brand_mark": brand,
            "ref": ref or barcode or "---",
            "color_finish": str(p.get("Color_Finish") or "Standard"),
            "available_qty": avail,
            "price_1": float(p.get("Price_1_TTC") or p.get("Unit_Price_TTC") or p.get("Selling_Price_1_TTC") or 0),
            "price_2": float(p.get("Price_2_TTC") or p.get("Selling_Price_2_TTC") or 0),
            "price_3": float(p.get("Price_3_TTC") or p.get("Selling_Price_3_TTC") or 0),
            "barcode": barcode,
        })
        if len(results) >= max(1, int(limit or 30)):
            break
    return results
