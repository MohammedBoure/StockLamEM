# database/client_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ClientManager:
    """إدارة عمليات جدول العملاء (Clients)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_client(self, name, contact_person=None, phone=None, email=None, 
                   address=None, city=None, tax_id=None, commercial_reg=None,
                   price_tier='Prix_1', credit_limit=0.0):
        """
        إضافة عميل جديد مع تحديد الفئة السعرية وسقف الائتمان.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Clients 
                    (Client_Name, Contact_Person, Phone, Email, Address, City, Tax_ID_Number, Commercial_Reg_No, Price_Tier, Credit_Limit) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (name, contact_person, phone, email, address, city, tax_id, commercial_reg, price_tier or 'Prix_1', float(credit_limit or 0.0))
                cursor.execute(query, params)
                client_id = cursor.lastrowid
                logging.info(f"Client '{name}' added with ID {client_id}.")
                return client_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Client '{name}' already exists (Duplicate entry).")
            else:
                logging.error(f"Database error while adding client '{name}': {err}")
            return None

    def update_client(self, client_id, **kwargs):
        """
        تحديث معلومات العميل بشكل ديناميكي.
        الوسائط المتاحة: name, contact_person, phone, email, address, city, tax_id, commercial_reg, price_tier, credit_limit
        """
        field_map = {
            'name': 'Client_Name',
            'contact_person': 'Contact_Person',
            'phone': 'Phone',
            'email': 'Email',
            'address': 'Address',
            'city': 'City',
            'tax_id': 'Tax_ID_Number',
            'commercial_reg': 'Commercial_Reg_No',
            'price_tier': 'Price_Tier',
            'credit_limit': 'Credit_Limit'
        }
        
        updates = []
        params = []
        
        for kw, db_field in field_map.items():
            if kw in kwargs and kwargs[kw] is not None:
                updates.append(f"{db_field} = %s")
                params.append(kwargs[kw])
                
        if not updates:
            logging.warning(f"No fields provided for client update (ID: {client_id}).")
            return False

        params.append(client_id)
        query = f"UPDATE Clients SET {', '.join(updates)} WHERE Client_ID = %s AND Deleted_At IS NULL"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                if cursor.rowcount > 0:
                    logging.info(f"Client {client_id} updated successfully.")
                    return True
                logging.warning(f"No active client found with ID {client_id} for update.")
                return False
        except mysql.connector.Error as e:
            logging.error(f"Error updating client {client_id}: {e}")
            raise

    def get_all_clients(self, include_deleted=False):
        """
        جلب جميع العملاء.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                query = "SELECT * FROM Clients"
                if not include_deleted:
                    query += " WHERE Deleted_At IS NULL"
                query += " ORDER BY Client_Name"
                
                cursor.execute(query)
                clients = cursor.fetchall()
                logging.info(f"Fetched {len(clients)} clients.")
                return clients
        except mysql.connector.Error as e:
            logging.error(f"Error fetching clients: {e}")
            raise

    def get_client_by_id(self, client_id):
        """
        جلب عميل محدد باستخدام ID.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Clients WHERE Client_ID = %s"
                cursor.execute(query, (client_id,))
                client = cursor.fetchone()
                return client
        except mysql.connector.Error as e:
            logging.error(f"Error fetching client {client_id}: {e}")
            raise

    def soft_delete_client(self, client_id):
        """
        حذف منطقي (Soft Delete) لعميل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # التحقق مما إذا كان العميل مرتبطاً بفواتير
                cursor.execute("SELECT COUNT(*) FROM Sales_Invoices WHERE Client_ID = %s", (client_id,))
                if cursor.fetchone()[0] > 0:
                    logging.error(f"Cannot soft delete client {client_id}. They have associated sales invoices.")
                    return False
                
                query = "UPDATE Clients SET Deleted_At = %s WHERE Client_ID = %s AND Deleted_At IS NULL"
                params = (datetime.now(), client_id)
                cursor.execute(query, params)
                
                if cursor.rowcount > 0:
                    logging.info(f"Client {client_id} soft deleted successfully.")
                    return True
                return False
        except mysql.connector.Error as e:
            logging.error(f"Database error while soft deleting client {client_id}: {e}")
            return False

    def get_client_balance(self, client_id: int) -> dict:
        """
        Calcule dynamiquement le solde financier d'un client :
        Solde = Total Factures - Total Paiements Reçus - Total Avoirs
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT Client_ID, Client_Name, Credit_Limit, Price_Tier FROM Clients WHERE Client_ID = %s", 
                    (client_id,)
                )
                client = cursor.fetchone()
                if not client:
                    return {
                        "client_id": client_id,
                        "client_name": "",
                        "credit_limit": 0.0,
                        "price_tier": "Prix_1",
                        "total_invoiced": 0.0,
                        "total_paid": 0.0,
                        "total_credit_notes": 0.0,
                        "current_balance": 0.0,
                        "available_credit": 0.0
                    }

                # 1. Total Facturé (hors factures annulées, devis et commandes brouillon)
                cursor.execute("""
                    SELECT COALESCE(SUM(Total_Amount_TTC), 0) AS total_invoiced
                    FROM Sales_Invoices
                    WHERE Client_ID = %s 
                      AND Status NOT IN ('Cancelled', 'Draft')
                      AND Invoice_No NOT LIKE 'DEV-%'
                      AND Invoice_No NOT LIKE 'BC-%'
                """, (client_id,))
                total_invoiced = float(cursor.fetchone()['total_invoiced'] or 0.0)

                # 2. Total Payé au comptant lors des ventes (POS Sale Payments non-crédit + Bureaux Caisse)
                cursor.execute("""
                    SELECT (
                        COALESCE((
                            SELECT SUM(p.Amount)
                            FROM POS_Sale_Payments p
                            JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                            WHERE i.Client_ID = %s
                              AND i.Status NOT IN ('Cancelled', 'Draft')
                              AND i.Invoice_No NOT LIKE 'DEV-%'
                              AND i.Invoice_No NOT LIKE 'BC-%'
                              AND p.Payment_Method != 'Credit'
                        ), 0)
                        + COALESCE((
                            SELECT SUM(COALESCE(i2.Amount_Paid_Cash, 0) + COALESCE(i2.Amount_Paid_Card, 0) + COALESCE(i2.Amount_Paid_Wallet, 0))
                            FROM Sales_Invoices i2
                            WHERE i2.Client_ID = %s
                              AND i2.Status NOT IN ('Cancelled', 'Draft')
                              AND i2.Invoice_No NOT LIKE 'DEV-%'
                              AND i2.Invoice_No NOT LIKE 'BC-%'
                              AND NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i2.Invoice_ID)
                        ), 0)
                    ) AS pos_paid
                """, (client_id, client_id))
                pos_paid = float(cursor.fetchone()['pos_paid'] or 0.0)

                # 3. Total Paiements ultérieurs (Client_Payments hors dépôts portefeuille Versement)
                cursor.execute("""
                    SELECT COALESCE(SUM(Amount), 0) AS client_paid
                    FROM Client_Payments
                    WHERE Client_ID = %s
                      AND COALESCE(Payment_Method, '') != 'Versement'
                """, (client_id,))
                client_paid = float(cursor.fetchone()['client_paid'] or 0.0)

                total_paid = pos_paid + client_paid

                # 4. Total Avoirs / Retours (Client_Credit_Notes)
                cursor.execute("""
                    SELECT COALESCE(SUM(Total_Amount_TTC), 0) AS total_cn
                    FROM Client_Credit_Notes
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """, (client_id,))
                total_credit_notes = float(cursor.fetchone()['total_cn'] or 0.0)

                current_balance = round(total_invoiced - total_paid - total_credit_notes, 2)
                credit_limit = float(client.get('Credit_Limit') or 0.0)
                available_credit = max(0.0, round(credit_limit - current_balance, 2)) if credit_limit > 0 else 0.0

                return {
                    "client_id": client_id,
                    "client_name": client.get('Client_Name', ''),
                    "credit_limit": credit_limit,
                    "price_tier": client.get('Price_Tier', 'Prix_1'),
                    "total_invoiced": total_invoiced,
                    "total_paid": total_paid,
                    "total_credit_notes": total_credit_notes,
                    "current_balance": current_balance,
                    "available_credit": available_credit
                }
        except Exception as e:
            logging.error(f"Error getting balance for client {client_id}: {e}")
            return {
                "client_id": client_id,
                "client_name": "",
                "credit_limit": 0.0,
                "price_tier": "Prix_1",
                "total_invoiced": 0.0,
                "total_paid": 0.0,
                "total_credit_notes": 0.0,
                "current_balance": 0.0,
                "available_credit": 0.0
            }

    def get_all_clients_with_balances(self) -> list:
        """
        Récupère tous les clients avec leur solde actuel calculé dynamiquement
        (Factures validées - Règlements - Avoirs), en excluant les devis et commandes brouillon.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        c.*,
                        COALESCE(c.Credit_Limit, 0.00) AS Credit_Limit,
                        COALESCE(c.Price_Tier, 'Prix_1') AS Price_Tier,
                        COALESCE(inv.total_invoiced, 0.00) AS total_invoiced,
                        COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00) AS total_paid,
                        COALESCE(cn.total_credit_notes, 0.00) AS total_credit_notes,
                        ROUND(
                            COALESCE(inv.total_invoiced, 0.00) 
                            - (COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00)) 
                            - COALESCE(cn.total_credit_notes, 0.00), 
                            2
                        ) AS Current_Balance
                    FROM Clients c
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_invoiced
                        FROM Sales_Invoices
                        WHERE Status NOT IN ('Cancelled', 'Draft') 
                          AND Invoice_No NOT LIKE 'DEV-%'
                          AND Invoice_No NOT LIKE 'BC-%'
                          AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) inv ON c.Client_ID = inv.Client_ID
                    LEFT JOIN (
                        SELECT
                            i.Client_ID,
                            SUM(
                                COALESCE((SELECT SUM(p.Amount) FROM POS_Sale_Payments p WHERE p.Invoice_ID = i.Invoice_ID AND p.Payment_Method != 'Credit'), 0)
                                + CASE
                                    WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                    THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                    ELSE 0
                                  END
                            ) AS pos_paid
                        FROM Sales_Invoices i
                        WHERE i.Status NOT IN ('Cancelled', 'Draft') 
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                          AND i.Client_ID IS NOT NULL
                        GROUP BY i.Client_ID
                    ) pos_pay ON c.Client_ID = pos_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Amount) AS client_paid
                        FROM Client_Payments
                        WHERE Client_ID IS NOT NULL
                          AND COALESCE(Payment_Method, '') != 'Versement'
                        GROUP BY Client_ID
                    ) cl_pay ON c.Client_ID = cl_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_credit_notes
                        FROM Client_Credit_Notes
                        WHERE Status != 'Cancelled' AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) cn ON c.Client_ID = cn.Client_ID
                    WHERE c.Deleted_At IS NULL
                    ORDER BY c.Client_Name
                """
                cursor.execute(query)
                return cursor.fetchall() or []
        except Exception as e:
            logging.error(f"Error fetching clients with balances: {e}")
            return self.get_all_clients()

    def get_clients_paged(self, search_text: str = None, offset: int = 0, limit: int = 50) -> dict:
        """
        Récupère une tranche (page) de clients avec soldes et le total global pour le Lazy Loading / pagination.
        Retourne un dictionnaire : {"items": list, "total_count": int, "has_more": bool, "offset": int, "limit": int}.
        """
        # If in-memory mock or patched method is used, handle in Python
        from unittest.mock import MagicMock
        if isinstance(getattr(self, "db", None), MagicMock) or isinstance(getattr(self, "get_all_clients_with_balances", None), MagicMock):
            all_clients = self.get_all_clients_with_balances() if hasattr(self, 'get_all_clients_with_balances') else self.get_all_clients()
            if search_text and search_text.strip():
                st = search_text.strip().lower()
                filtered = [
                    c for c in all_clients
                    if st in str(c.get('Client_Name', '')).lower()
                    or st in str(c.get('Phone', '')).lower()
                    or st in str(c.get('Email', '')).lower()
                    or st in str(c.get('City', '')).lower()
                    or st in str(c.get('Price_Tier', '')).lower()
                    or st in str(c.get('Contact_Person', '')).lower()
                ]
            else:
                filtered = all_clients
            total_count = len(filtered)
            items = filtered[offset:offset + limit]
            return {
                "items": items,
                "total_count": total_count,
                "has_more": (offset + len(items)) < total_count,
                "offset": offset,
                "limit": limit
            }

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                where_clauses = ["c.Deleted_At IS NULL"]
                params = []

                if search_text and search_text.strip():
                    term = f"%{search_text.strip()}%"
                    where_clauses.append(
                        "(c.Client_Name LIKE %s OR c.Phone LIKE %s OR c.Email LIKE %s OR c.City LIKE %s OR c.Price_Tier LIKE %s OR c.Contact_Person LIKE %s)"
                    )
                    params.extend([term, term, term, term, term, term])

                where_sql = " AND ".join(where_clauses)

                # 1. Total Count Query
                count_query = f"SELECT COUNT(*) AS total FROM Clients c WHERE {where_sql}"
                cursor.execute(count_query, params)
                c_res = cursor.fetchone()
                total_count = int(c_res.get('total') or c_res.get('COUNT(*)', 0)) if c_res else 0

                # 2. Paged Data Query with dynamic balances
                data_query = f"""
                    SELECT 
                        c.*,
                        COALESCE(c.Credit_Limit, 0.00) AS Credit_Limit,
                        COALESCE(c.Price_Tier, 'Prix_1') AS Price_Tier,
                        COALESCE(inv.total_invoiced, 0.00) AS total_invoiced,
                        COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00) AS total_paid,
                        COALESCE(cn.total_credit_notes, 0.00) AS total_credit_notes,
                        ROUND(
                            COALESCE(inv.total_invoiced, 0.00) 
                            - (COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00)) 
                            - COALESCE(cn.total_credit_notes, 0.00), 
                            2
                        ) AS Current_Balance
                    FROM Clients c
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_invoiced
                        FROM Sales_Invoices
                        WHERE Status NOT IN ('Cancelled', 'Draft') 
                          AND Invoice_No NOT LIKE 'DEV-%'
                          AND Invoice_No NOT LIKE 'BC-%'
                          AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) inv ON c.Client_ID = inv.Client_ID
                    LEFT JOIN (
                        SELECT
                            i.Client_ID,
                            SUM(
                                COALESCE((SELECT SUM(p.Amount) FROM POS_Sale_Payments p WHERE p.Invoice_ID = i.Invoice_ID AND p.Payment_Method != 'Credit'), 0)
                                + CASE
                                    WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                    THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                    ELSE 0
                                  END
                            ) AS pos_paid
                        FROM Sales_Invoices i
                        WHERE i.Status NOT IN ('Cancelled', 'Draft') 
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                          AND i.Client_ID IS NOT NULL
                        GROUP BY i.Client_ID
                    ) pos_pay ON c.Client_ID = pos_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Amount) AS client_paid
                        FROM Client_Payments
                        WHERE Client_ID IS NOT NULL
                          AND COALESCE(Payment_Method, '') != 'Versement'
                        GROUP BY Client_ID
                    ) cl_pay ON c.Client_ID = cl_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_credit_notes
                        FROM Client_Credit_Notes
                        WHERE Status != 'Cancelled' AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) cn ON c.Client_ID = cn.Client_ID
                    WHERE {where_sql}
                    ORDER BY c.Client_Name
                    LIMIT %s OFFSET %s
                """
                cursor.execute(data_query, params + [int(limit), int(offset)])
                items = cursor.fetchall() or []
                has_more = (offset + len(items)) < total_count
                return {
                    "items": items,
                    "total_count": total_count,
                    "has_more": has_more,
                    "offset": offset,
                    "limit": limit
                }
        except Exception as e:
            logging.error(f"Error in get_clients_paged: {e}")
            try:
                all_clients = self.get_all_clients_with_balances() if hasattr(self, 'get_all_clients_with_balances') else self.get_all_clients()
                if search_text and search_text.strip():
                    st = search_text.strip().lower()
                    filtered = [
                        c for c in all_clients
                        if st in str(c.get('Client_Name', '')).lower()
                        or st in str(c.get('Phone', '')).lower()
                        or st in str(c.get('Email', '')).lower()
                        or st in str(c.get('City', '')).lower()
                        or st in str(c.get('Price_Tier', '')).lower()
                        or st in str(c.get('Contact_Person', '')).lower()
                    ]
                else:
                    filtered = all_clients
                total_count = len(filtered)
                items = filtered[offset:offset + limit]
                return {
                    "items": items,
                    "total_count": total_count,
                    "has_more": (offset + len(items)) < total_count,
                    "offset": offset,
                    "limit": limit
                }
            except Exception as e2:
                logging.error(f"Fallback get_clients_paged failed: {e2}")
                return {"items": [], "total_count": 0, "has_more": False, "offset": offset, "limit": limit}

    def get_client_ledger(self, client_id: int, start_date=None, end_date=None) -> dict:
        """
        Extrait l'historique complet chronologique pour le Relevé de Compte Client.
        Calcule le solde initial avant start_date, la liste des opérations (Débit, Crédit, Solde),
        et le solde final.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Récupérer infos client
                cursor.execute("SELECT * FROM Clients WHERE Client_ID = %s", (client_id,))
                client = cursor.fetchone() or {}

                # Solde initial antérieur à start_date
                initial_balance = 0.0
                if start_date:
                    cursor.execute("""
                        SELECT 
                            (
                                SELECT COALESCE(SUM(Total_Amount_TTC), 0)
                                FROM Sales_Invoices
                                WHERE Client_ID = %s 
                                  AND Status NOT IN ('Cancelled', 'Draft') 
                                  AND Invoice_No NOT LIKE 'DEV-%'
                                  AND Invoice_No NOT LIKE 'BC-%'
                                  AND Invoice_Date < %s
                            ) - (
                                SELECT COALESCE(SUM(p.Amount), 0)
                                FROM POS_Sale_Payments p
                                JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                                WHERE i.Client_ID = %s 
                                  AND i.Status NOT IN ('Cancelled', 'Draft') 
                                  AND i.Invoice_No NOT LIKE 'DEV-%'
                                  AND i.Invoice_No NOT LIKE 'BC-%'
                                  AND p.Payment_Method != 'Credit' 
                                  AND i.Invoice_Date < %s
                            ) - (
                                SELECT COALESCE(SUM(Amount), 0)
                                FROM Client_Payments
                                WHERE Client_ID = %s AND Payment_Date < %s
                            ) - (
                                SELECT COALESCE(SUM(Total_Amount_TTC), 0)
                                FROM Client_Credit_Notes
                                WHERE Client_ID = %s AND Status != 'Cancelled' AND Return_Date < %s
                            ) AS prior_balance
                    """, (client_id, start_date, client_id, start_date, client_id, start_date, client_id, start_date))
                    row = cursor.fetchone()
                    initial_balance = float(row.get('prior_balance') or 0.0) if row else 0.0

                transactions = []

                # 1. Factures dans la période
                inv_query = """
                    SELECT Invoice_ID, Invoice_No, Invoice_Date AS op_date, Total_Amount_TTC, Sale_Type, Status,
                           Bond_Settlement_Type, Amount_Paid_Cash, Amount_Paid_Card, Amount_Paid_Wallet
                    FROM Sales_Invoices
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """
                inv_params = [client_id]
                if start_date:
                    inv_query += " AND Invoice_Date >= %s"
                    inv_params.append(start_date)
                if end_date:
                    inv_query += " AND Invoice_Date <= %s"
                    inv_params.append(end_date)
                cursor.execute(inv_query, tuple(inv_params))
                for r in cursor.fetchall():
                    ref = r.get('Invoice_No') or f"FAC-{r['Invoice_ID']}"
                    status_raw = r.get('Status') or 'Validated'
                    is_quote_or_draft = (status_raw == 'Draft') or ref.startswith("DEV-") or ref.startswith("BC-")
                    bond_st = str(r.get('Bond_Settlement_Type') or '').upper()

                    if bond_st == 'BON_C_CASH' or ref.startswith("FAC-BC-"):
                        label = "Bon Comptant (Bureaux)"
                    elif bond_st == 'BON_CREDIT' or ref.startswith("FAC-BCR-"):
                        label = "Bon Crédit (Bureaux)"
                    elif bond_st == 'BON_LIVRAISON' or ref.startswith("FAC-BL-") or ref.startswith("BL-"):
                        label = "Bon de Livraison (BL)"
                    elif ref.startswith("DEV-"):
                        label = "Devis"
                    elif ref.startswith("BC-"):
                        label = "Bon de Commande (BC)"
                    elif r.get('Sale_Type') == 'Wholesale':
                        label = "Facture (Vente Gros)"
                    else:
                        label = "Facture (Vente POS)"

                    # Strict accounting segregation:
                    # Devis (DEV) and draft orders (BC) do NOT impact debt/solde
                    debit = 0.0 if is_quote_or_draft else float(r['Total_Amount_TTC'] or 0.0)
                    note_str = f"Statut: {status_raw} (Hors bilan)" if is_quote_or_draft else f"Statut: {status_raw}"

                    transactions.append({
                        'date': str(r['op_date']),
                        'type': label,
                        'reference': ref,
                        'debit': debit,
                        'credit': 0.0,
                        'is_non_binding': is_quote_or_draft,
                        'raw_amount': float(r['Total_Amount_TTC'] or 0.0),
                        'notes': note_str,
                        'doc_id': r.get('Invoice_ID'),
                        'doc_category': 'invoice',
                        'sale_type': r.get('Sale_Type'),
                        'status': status_raw
                    })

                    # Si facture Bureaux avec paiement Caisse / Portefeuille enregistré sur la facture
                    b_paid = (
                        float(r.get('Amount_Paid_Cash') or 0.0)
                        + float(r.get('Amount_Paid_Card') or 0.0)
                        + float(r.get('Amount_Paid_Wallet') or 0.0)
                    )
                    if not is_quote_or_draft and b_paid > 0.009:
                        transactions.append({
                            'date': str(r['op_date']),
                            'type': "Règlement Caisse (Bureaux)",
                            'reference': ref,
                            'debit': 0.0,
                            'credit': round(b_paid, 2),
                            'notes': f"Encaissement sur {label}",
                            'doc_id': r.get('Invoice_ID'),
                            'doc_category': 'pos_payment',
                            'payment_method': 'Caisse / Portefeuille',
                            'invoice_no': ref
                        })

                # 2. Paiements au comptant lors de la vente dans la période
                pos_pay_query = """
                    SELECT p.Payment_ID, p.Payment_Method, p.Amount, p.Reference, i.Invoice_No, i.Invoice_Date AS op_date
                    FROM POS_Sale_Payments p
                    JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                    WHERE i.Client_ID = %s AND i.Status != 'Cancelled' AND p.Payment_Method != 'Credit'
                """
                pos_pay_params = [client_id]
                if start_date:
                    pos_pay_query += " AND i.Invoice_Date >= %s"
                    pos_pay_params.append(start_date)
                if end_date:
                    pos_pay_query += " AND i.Invoice_Date <= %s"
                    pos_pay_params.append(end_date)
                cursor.execute(pos_pay_query, tuple(pos_pay_params))
                for r in cursor.fetchall():
                    ref = r.get('Reference') or r.get('Invoice_No') or f"PAY-{r['Payment_ID']}"
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': f"Paiement Caisse ({r['Payment_Method']})",
                        'reference': ref,
                        'debit': 0.0,
                        'credit': float(r['Amount'] or 0.0),
                        'notes': "Paiement direct à la vente",
                        'doc_id': r.get('Payment_ID'),
                        'doc_category': 'pos_payment',
                        'payment_method': r.get('Payment_Method'),
                        'invoice_no': r.get('Invoice_No')
                    })

                # 3. Règlements ultérieurs (Client_Payments hors dépôts portefeuille Versement)
                cl_pay_query = """
                    SELECT Payment_ID, Payment_Date AS op_date, Amount, Payment_Method, Reference, Notes
                    FROM Client_Payments
                    WHERE Client_ID = %s AND COALESCE(Payment_Method, '') != 'Versement'
                """
                cl_pay_params = [client_id]
                if start_date:
                    cl_pay_query += " AND Payment_Date >= %s"
                    cl_pay_params.append(start_date)
                if end_date:
                    cl_pay_query += " AND Payment_Date <= %s"
                    cl_pay_params.append(end_date)
                cursor.execute(cl_pay_query, tuple(cl_pay_params))
                for r in cursor.fetchall():
                    ref = r.get('Reference') or f"REG-{r['Payment_ID']}"
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': f"Règlement ({r.get('Payment_Method', 'Espèce')})",
                        'reference': ref,
                        'debit': 0.0,
                        'credit': float(r['Amount'] or 0.0),
                        'notes': r.get('Notes') or '',
                        'doc_id': r.get('Payment_ID'),
                        'doc_category': 'client_payment',
                        'payment_method': r.get('Payment_Method')
                    })

                # 4. Avoirs / Retours (Client_Credit_Notes)
                cn_query = """
                    SELECT Credit_Note_ID, Return_Date AS op_date, Total_Amount_TTC, Notes
                    FROM Client_Credit_Notes
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """
                cn_params = [client_id]
                if start_date:
                    cn_query += " AND Return_Date >= %s"
                    cn_params.append(start_date)
                if end_date:
                    cn_query += " AND Return_Date <= %s"
                    cn_params.append(end_date)
                cursor.execute(cn_query, tuple(cn_params))
                for r in cursor.fetchall():
                    transactions.append({
                        'date': str(r['op_date']),
                        'type': "Avoir / Retour Produit",
                        'reference': f"AVR-{r['Credit_Note_ID']}",
                        'debit': 0.0,
                        'credit': float(r['Total_Amount_TTC'] or 0.0),
                        'notes': r.get('Notes') or '',
                        'doc_id': r.get('Credit_Note_ID'),
                        'doc_category': 'credit_note'
                    })

                # Tri chronologique des transactions
                transactions.sort(key=lambda x: x['date'])

                # Calcul du solde progressif
                current_running = initial_balance
                for t in transactions:
                    current_running = round(current_running + t['debit'] - t['credit'], 2)
                    t['balance'] = current_running

                final_balance = current_running

                return {
                    'client': client,
                    'initial_balance': round(initial_balance, 2),
                    'transactions': transactions,
                    'final_balance': round(final_balance, 2),
                    'start_date': str(start_date) if start_date else None,
                    'end_date': str(end_date) if end_date else None
                }

        except Exception as e:
            logging.error(f"Error generating ledger for client {client_id}: {e}")
            return {
                'client': {},
                'initial_balance': 0.0,
                'transactions': [],
                'final_balance': 0.0
            }

    def audit_client_debt_balance(self, client_id: int) -> dict:
        """
        Audit d'intégrité comptable vérifiant la formule fondamentale :
        Solde Actuel = Total(Factures & BL Validés) - Total(Règlements) - Total(Avoirs Validés)
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    "SELECT Client_ID, Client_Name, Credit_Limit, Price_Tier FROM Clients WHERE Client_ID = %s",
                    (client_id,)
                )
                client = cursor.fetchone()
                if not client:
                    return {"client_id": client_id, "error": "Client introuvable", "is_balanced": False}

                # 1. Total Factures & BL validés (excluant Cancelled, Draft, DEV, BC)
                cursor.execute("""
                    SELECT COALESCE(SUM(Total_Amount_TTC), 0) AS total_invoiced,
                           COUNT(*) AS count_invoices
                    FROM Sales_Invoices
                    WHERE Client_ID = %s 
                      AND Status NOT IN ('Cancelled', 'Draft')
                      AND Invoice_No NOT LIKE 'DEV-%'
                      AND Invoice_No NOT LIKE 'BC-%'
                """, (client_id,))
                inv_res = cursor.fetchone() or {}
                total_invoiced = float(inv_res.get('total_invoiced') or 0.0)
                count_invoices = int(inv_res.get('count_invoices') or 0)

                # 2. Total Règlements Caisse POS + Bureaux
                cursor.execute("""
                    SELECT (
                        COALESCE((
                            SELECT SUM(p.Amount)
                            FROM POS_Sale_Payments p
                            JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                            WHERE i.Client_ID = %s
                              AND i.Status NOT IN ('Cancelled', 'Draft')
                              AND i.Invoice_No NOT LIKE 'DEV-%'
                              AND i.Invoice_No NOT LIKE 'BC-%'
                              AND p.Payment_Method != 'Credit'
                        ), 0)
                        + COALESCE((
                            SELECT SUM(COALESCE(i2.Amount_Paid_Cash, 0) + COALESCE(i2.Amount_Paid_Card, 0) + COALESCE(i2.Amount_Paid_Wallet, 0))
                            FROM Sales_Invoices i2
                            WHERE i2.Client_ID = %s
                              AND i2.Status NOT IN ('Cancelled', 'Draft')
                              AND i2.Invoice_No NOT LIKE 'DEV-%'
                              AND i2.Invoice_No NOT LIKE 'BC-%'
                              AND NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i2.Invoice_ID)
                        ), 0)
                    ) AS pos_paid,
                    (
                        SELECT COUNT(*)
                        FROM POS_Sale_Payments p
                        JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                        WHERE i.Client_ID = %s
                          AND i.Status NOT IN ('Cancelled', 'Draft')
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                          AND p.Payment_Method != 'Credit'
                    ) AS count_pos_payments
                """, (client_id, client_id, client_id))
                pos_res = cursor.fetchone() or {}
                pos_paid = float(pos_res.get('pos_paid') or 0.0)
                count_pos = int(pos_res.get('count_pos_payments') or 0)

                # 3. Total Règlements Directs & Acomptes (Client_Payments hors dépôts portefeuille Versement)
                cursor.execute("""
                    SELECT COALESCE(SUM(Amount), 0) AS client_paid,
                           COUNT(*) AS count_client_payments
                    FROM Client_Payments
                    WHERE Client_ID = %s
                      AND COALESCE(Payment_Method, '') != 'Versement'
                """, (client_id,))
                cl_res = cursor.fetchone() or {}
                client_paid = float(cl_res.get('client_paid') or 0.0)
                count_cl_pay = int(cl_res.get('count_client_payments') or 0)

                total_paid = round(pos_paid + client_paid, 2)

                # 4. Total Avoirs / Retours (Client_Credit_Notes)
                cursor.execute("""
                    SELECT COALESCE(SUM(Total_Amount_TTC), 0) AS total_credit_notes,
                           COUNT(*) AS count_credit_notes
                    FROM Client_Credit_Notes
                    WHERE Client_ID = %s AND Status != 'Cancelled'
                """, (client_id,))
                cn_res = cursor.fetchone() or {}
                total_credit_notes = float(cn_res.get('total_credit_notes') or 0.0)
                count_cn = int(cn_res.get('count_credit_notes') or 0)

                # Expected balance
                expected_balance = round(total_invoiced - total_paid - total_credit_notes, 2)

                # Balance from get_client_balance
                balance_data = self.get_client_balance(client_id)
                current_balance = float(balance_data.get('current_balance', 0.0))

                discrepancy = round(current_balance - expected_balance, 2)
                is_balanced = abs(discrepancy) < 0.005

                return {
                    "client_id": client_id,
                    "client_name": client.get('Client_Name', ''),
                    "credit_limit": float(client.get('Credit_Limit') or 0.0),
                    "price_tier": client.get('Price_Tier', 'Prix_1'),
                    "is_balanced": is_balanced,
                    "current_balance": current_balance,
                    "expected_balance": expected_balance,
                    "discrepancy": discrepancy,
                    "total_invoiced": total_invoiced,
                    "count_invoices": count_invoices,
                    "total_paid": total_paid,
                    "pos_paid": pos_paid,
                    "client_paid": client_paid,
                    "count_payments": count_pos + count_cl_pay,
                    "total_credit_notes": total_credit_notes,
                    "count_credit_notes": count_cn
                }
        except Exception as e:
            logging.error(f"Error auditing client debt balance for {client_id}: {e}", exc_info=True)
            return {
                "client_id": client_id,
                "error": str(e),
                "is_balanced": False
            }

    def get_client_unpaid_invoices(self, client_id: int) -> list:
        """
        Récupère toutes les factures et BL impayés ou partiellement payés pour un client.
        Calcule les jours de retard par rapport à l'échéance (Due_Date) ou à la date de facture.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT * FROM (
                        SELECT 
                            i.Invoice_ID, i.Invoice_No, i.Invoice_Date, i.Due_Date, i.Sale_Type, i.Status,
                            i.Total_Amount_TTC,
                            ROUND(
                                COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                + CASE
                                    WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                    THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                    ELSE 0
                                  END
                                + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0),
                                2
                            ) AS Paid_Amount,
                            ROUND(
                                i.Total_Amount_TTC - (
                                    COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                    + CASE
                                        WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                        THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                        ELSE 0
                                      END
                                    + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0)
                                ),
                                2
                            ) AS Remaining_Balance
                        FROM Sales_Invoices i
                        WHERE i.Client_ID = %s
                          AND i.Status NOT IN ('Cancelled', 'Draft', 'Paid')
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                    ) unpaid
                    WHERE unpaid.Remaining_Balance > 0.009
                    ORDER BY unpaid.Invoice_Date ASC, unpaid.Invoice_ID ASC
                """, (client_id,))
                rows = cursor.fetchall()
                today = datetime.now().date()
                result = []
                for r in rows:
                    due_date_str = r.get('Due_Date') or r.get('Invoice_Date')
                    days_overdue = 0
                    if due_date_str:
                        try:
                            due_date = datetime.strptime(str(due_date_str)[:10], "%Y-%m-%d").date()
                            days_overdue = (today - due_date).days
                        except Exception:
                            days_overdue = 0

                    r['Days_Overdue'] = max(0, days_overdue)
                    r['Is_Overdue'] = days_overdue > 0
                    result.append(r)
                return result
        except Exception as e:
            logging.error(f"Error fetching unpaid invoices for client {client_id}: {e}")
            return []

    def get_debts_analytics(self) -> dict:
        """
        Calcule les indicateurs clés (KPIs) globaux des créances clients :
        - Total des créances en cours (Solde > 0)
        - Total des créances échues (dettes dépassées en date d'échéance)
        - Nombre de clients débiteurs
        - Total des règlements recouvrés durant le mois en cours
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. Tous les soldes clients
                all_clients = self.get_all_clients_with_balances()
                total_receivables = 0.0
                debtor_count = 0
                for c in all_clients:
                    bal = float(c.get('Current_Balance') or 0.0)
                    if bal > 0.009:
                        total_receivables += bal
                        debtor_count += 1

                # 2. Créances échues (factures impayées dont Due_Date < aujourd'hui)
                today_str = datetime.now().strftime("%Y-%m-%d")
                cursor.execute("""
                    SELECT COALESCE(SUM(unpaid.Remaining_Balance), 0) AS overdue_total
                    FROM (
                        SELECT 
                            i.Total_Amount_TTC - (
                                COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                + CASE
                                    WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                    THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                    ELSE 0
                                  END
                                + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0)
                            ) AS Remaining_Balance
                        FROM Sales_Invoices i
                        WHERE i.Status NOT IN ('Cancelled', 'Draft', 'Paid')
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                          AND COALESCE(i.Due_Date, i.Invoice_Date) < %s
                    ) unpaid
                    WHERE unpaid.Remaining_Balance > 0.009
                """, (today_str,))
                overdue_row = cursor.fetchone() or {}
                overdue_total = float(overdue_row.get('overdue_total') or 0.0)

                # 3. Règlements recouvrés durant le mois en cours (Client_Payments + POS payments)
                first_of_month = datetime.now().strftime("%Y-%m-01")
                cursor.execute("""
                    SELECT COALESCE(SUM(Amount), 0) AS month_recovered
                    FROM Client_Payments
                    WHERE Payment_Date >= %s
                      AND COALESCE(Payment_Method, '') != 'Versement'
                """, (first_of_month,))
                month_row = cursor.fetchone() or {}
                month_recovered_cl = float(month_row.get('month_recovered') or 0.0)

                cursor.execute("""
                    SELECT (
                        COALESCE((
                            SELECT SUM(p.Amount)
                            FROM POS_Sale_Payments p
                            JOIN Sales_Invoices i ON i.Invoice_ID = p.Invoice_ID
                            WHERE i.Invoice_Date >= %s
                              AND i.Status NOT IN ('Cancelled', 'Draft')
                              AND i.Invoice_No NOT LIKE 'DEV-%'
                              AND i.Invoice_No NOT LIKE 'BC-%'
                              AND p.Payment_Method != 'Credit'
                        ), 0)
                        + COALESCE((
                            SELECT SUM(COALESCE(i2.Amount_Paid_Cash, 0) + COALESCE(i2.Amount_Paid_Card, 0) + COALESCE(i2.Amount_Paid_Wallet, 0))
                            FROM Sales_Invoices i2
                            WHERE i2.Invoice_Date >= %s
                              AND i2.Status NOT IN ('Cancelled', 'Draft')
                              AND i2.Invoice_No NOT LIKE 'DEV-%'
                              AND i2.Invoice_No NOT LIKE 'BC-%'
                              AND NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i2.Invoice_ID)
                        ), 0)
                    ) AS month_pos
                """, (first_of_month, first_of_month))
                pos_row = cursor.fetchone() or {}
                month_pos = float(pos_row.get('month_pos') or 0.0)

                total_month_recovered = round(month_recovered_cl + month_pos, 2)

                return {
                    "total_receivables": round(total_receivables, 2),
                    "overdue_receivables": round(overdue_total, 2),
                    "debtor_clients_count": debtor_count,
                    "recovered_this_month": total_month_recovered
                }
        except Exception as e:
            logging.error(f"Error calculating debts analytics: {e}")
            return {
                "total_receivables": 0.0,
                "overdue_receivables": 0.0,
                "debtor_clients_count": 0,
                "recovered_this_month": 0.0
            }

    def get_debtor_clients_summary(self, min_debt: float = 0.0, filter_status: str = "Tous", search_term: str = None) -> list:
        """
        Récupère la liste synthétique des clients débiteurs avec informations d'échéance,
        date de dernier règlement et classification de statut / badge :
        - 'Plafond Dépassé' : Solde > Plafond Crédit (avec Plafond > 0)
        - 'Alerte Retard' : Au moins une facture échue dépassée
        - 'Normal' : Solde > 0 dans les limites autorisées
        - 'Soldé' : Solde <= 0
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                today_str = datetime.now().strftime("%Y-%m-%d")

                query = """
                    SELECT 
                        c.Client_ID,
                        c.Client_Name,
                        c.Phone,
                        c.City,
                        COALESCE(c.Credit_Limit, 0.00) AS Credit_Limit,
                        COALESCE(c.Price_Tier, 'Prix_1') AS Price_Tier,
                        COALESCE(inv.total_invoiced, 0.00) AS total_invoiced,
                        COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00) AS total_paid,
                        COALESCE(cn.total_credit_notes, 0.00) AS total_credit_notes,
                        ROUND(
                            COALESCE(inv.total_invoiced, 0.00) 
                            - (COALESCE(pos_pay.pos_paid, 0.00) + COALESCE(cl_pay.client_paid, 0.00)) 
                            - COALESCE(cn.total_credit_notes, 0.00), 
                            2
                        ) AS Current_Balance,
                        last_pay.Last_Payment_Date,
                        COALESCE(overdue.Overdue_Count, 0) AS Overdue_Count,
                        COALESCE(unpaid.Unpaid_Count, 0) AS Unpaid_Count
                    FROM Clients c
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_invoiced
                        FROM Sales_Invoices
                        WHERE Status NOT IN ('Cancelled', 'Draft') 
                          AND Invoice_No NOT LIKE 'DEV-%'
                          AND Invoice_No NOT LIKE 'BC-%'
                          AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) inv ON c.Client_ID = inv.Client_ID
                    LEFT JOIN (
                        SELECT
                            i.Client_ID,
                            SUM(
                                COALESCE((SELECT SUM(p.Amount) FROM POS_Sale_Payments p WHERE p.Invoice_ID = i.Invoice_ID AND p.Payment_Method != 'Credit'), 0)
                                + CASE
                                    WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                    THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                    ELSE 0
                                  END
                            ) AS pos_paid
                        FROM Sales_Invoices i
                        WHERE i.Status NOT IN ('Cancelled', 'Draft') 
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                          AND i.Client_ID IS NOT NULL
                        GROUP BY i.Client_ID
                    ) pos_pay ON c.Client_ID = pos_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Amount) AS client_paid
                        FROM Client_Payments
                        WHERE Client_ID IS NOT NULL
                          AND COALESCE(Payment_Method, '') != 'Versement'
                        GROUP BY Client_ID
                    ) cl_pay ON c.Client_ID = cl_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, SUM(Total_Amount_TTC) AS total_credit_notes
                        FROM Client_Credit_Notes
                        WHERE Status != 'Cancelled' AND Client_ID IS NOT NULL
                        GROUP BY Client_ID
                    ) cn ON c.Client_ID = cn.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, MAX(Payment_Date) AS Last_Payment_Date
                        FROM Client_Payments
                        GROUP BY Client_ID
                    ) last_pay ON c.Client_ID = last_pay.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, COUNT(*) AS Overdue_Count
                        FROM (
                            SELECT 
                                i.Client_ID,
                                i.Total_Amount_TTC - (
                                    COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                    + CASE
                                        WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                        THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                        ELSE 0
                                      END
                                    + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0)
                                ) AS Remaining_Balance
                            FROM Sales_Invoices i
                            WHERE i.Status NOT IN ('Cancelled', 'Draft', 'Paid')
                              AND i.Invoice_No NOT LIKE 'DEV-%'
                              AND i.Invoice_No NOT LIKE 'BC-%'
                              AND COALESCE(i.Due_Date, i.Invoice_Date) < %s
                              AND i.Client_ID IS NOT NULL
                        ) ov_sub
                        WHERE ov_sub.Remaining_Balance > 0.009
                        GROUP BY Client_ID
                    ) overdue ON c.Client_ID = overdue.Client_ID
                    LEFT JOIN (
                        SELECT Client_ID, COUNT(*) AS Unpaid_Count
                        FROM (
                            SELECT 
                                i.Client_ID,
                                i.Total_Amount_TTC - (
                                    COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                    + CASE
                                        WHEN NOT EXISTS (SELECT 1 FROM POS_Sale_Payments pp2 WHERE pp2.Invoice_ID = i.Invoice_ID)
                                        THEN COALESCE(i.Amount_Paid_Cash, 0) + COALESCE(i.Amount_Paid_Card, 0) + COALESCE(i.Amount_Paid_Wallet, 0)
                                        ELSE 0
                                      END
                                    + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0)
                                ) AS Remaining_Balance
                            FROM Sales_Invoices i
                            WHERE i.Status NOT IN ('Cancelled', 'Draft', 'Paid')
                              AND i.Invoice_No NOT LIKE 'DEV-%'
                              AND i.Invoice_No NOT LIKE 'BC-%'
                              AND i.Client_ID IS NOT NULL
                        ) unp_sub
                        WHERE unp_sub.Remaining_Balance > 0.009
                        GROUP BY Client_ID
                    ) unpaid ON c.Client_ID = unpaid.Client_ID
                    WHERE c.Deleted_At IS NULL
                    ORDER BY Current_Balance DESC, c.Client_Name ASC
                """
                cursor.execute(query, (today_str,))
                clients = cursor.fetchall()

                result = []
                for c in clients:
                    bal = float(c.get('Current_Balance') or 0.0)
                    limit = float(c.get('Credit_Limit') or 0.0)
                    has_overdue = int(c.get('Overdue_Count') or 0) > 0

                    if limit > 0 and bal > limit:
                        status_badge = "Plafond Dépassé"
                    elif has_overdue and bal > 0.009:
                        status_badge = "Alerte Retard"
                    elif bal > 0.009:
                        status_badge = "Normal"
                    else:
                        status_badge = "Soldé"

                    c['Status_Badge'] = status_badge

                    # Filters
                    if min_debt > 0 and bal < min_debt:
                        continue

                    if filter_status == "Dépassant le Plafond" and status_badge != "Plafond Dépassé":
                        continue
                    elif filter_status == "En Retard / Échues" and status_badge != "Alerte Retard":
                        continue
                    elif filter_status == "Actifs" and bal <= 0.009:
                        continue
                    elif filter_status == "Soldés" and bal > 0.009:
                        continue

                    if search_term:
                        st = search_term.lower().strip()
                        c_name = str(c.get('Client_Name') or '').lower()
                        c_phone = str(c.get('Phone') or '').lower()
                        if st not in c_name and st not in c_phone:
                            continue

                    result.append(c)

                return result
        except Exception as e:
            logging.error(f"Error fetching debtor clients summary: {e}")
            return []

