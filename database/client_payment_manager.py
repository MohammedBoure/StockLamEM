# database/client_payment_manager.py

import mysql.connector
import logging
from datetime import datetime
from .system_logger import log_methods 

@log_methods()
class ClientPaymentManager:
    """إدارة عمليات مدفوعات العملاء (Client Payments)."""

    def __init__(self, db_instance):
        self.db = db_instance

    def add_payment(self, client_id, payment_date, amount, payment_method='Espèce', reference=None, notes=None, invoice_id=None, user_id=None):
        """
        إضافة دفعة مالية جديدة من عميل.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                # Verify client exists to prevent Foreign Key constraint error 1452
                cursor.execute("SELECT Client_ID FROM Clients WHERE Client_ID = %s", (client_id,))
                if not cursor.fetchone():
                    logging.error(f"Cannot add payment: Client #{client_id} does not exist in Clients table.")
                    return None

                query = """
                    INSERT INTO Client_Payments 
                    (Client_ID, Invoice_ID, Payment_Date, Amount, Payment_Method, Reference, Notes, Created_By) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                params = (client_id, invoice_id, payment_date, amount, payment_method, reference, notes, user_id)
                cursor.execute(query, params)
                payment_id = cursor.lastrowid
                logging.info(f"Payment of {amount} added for Client {client_id} (ID: {payment_id}).")
                
                # إذا كانت الدفعة مرتبطة بفاتورة محددة، يمكن التحقق من اكتمال الدفع وتحديث حالة الفاتورة
                if invoice_id:
                    self._check_and_update_invoice_status(cursor, invoice_id)
                    
                return payment_id
        except mysql.connector.Error as err:
            logging.error(f"Database error while adding payment: {err}")
            return None

    def _check_and_update_invoice_status(self, cursor, invoice_id):
        """
        التحقق من إجمالي المدفوعات لفاتورة محددة وتحديث حالتها إلى Paid إذا تم سدادها بالكامل.
        """
        try:
            # إجمالي الفاتورة
            cursor.execute("SELECT Total_Amount_TTC, Status FROM Sales_Invoices WHERE Invoice_ID = %s", (invoice_id,))
            invoice_data = cursor.fetchone()
            if not invoice_data:
                return
            
            total_ttc = float(invoice_data[0] if isinstance(invoice_data, (tuple, list)) else invoice_data.get('Total_Amount_TTC', 0.0))
            current_status = invoice_data[1] if isinstance(invoice_data, (tuple, list)) else invoice_data.get('Status', '')

            # إجمالي المدفوعات للفاتورة من Client_Payments
            cursor.execute("SELECT COALESCE(SUM(Amount), 0) FROM Client_Payments WHERE Invoice_ID = %s", (invoice_id,))
            cl_paid_row = cursor.fetchone()
            cl_paid = float(cl_paid_row[0] if isinstance(cl_paid_row, (tuple, list)) else (cl_paid_row.get('COALESCE(SUM(Amount), 0)') or 0.0))

            # إجمالي المدفوعات من POS_Sale_Payments غير الآجلة
            cursor.execute("SELECT COALESCE(SUM(Amount), 0) FROM POS_Sale_Payments WHERE Invoice_ID = %s AND Payment_Method != 'Credit'", (invoice_id,))
            pos_paid_row = cursor.fetchone()
            pos_paid = float(pos_paid_row[0] if isinstance(pos_paid_row, (tuple, list)) else (pos_paid_row.get('COALESCE(SUM(Amount), 0)') or 0.0))

            cumulative_paid = round(cl_paid + pos_paid, 2)
            new_status = 'Paid' if cumulative_paid >= (total_ttc - 0.009) else current_status

            if new_status != current_status:
                cursor.execute(
                    "UPDATE Sales_Invoices SET Status = %s WHERE Invoice_ID = %s",
                    (new_status, invoice_id)
                )
            logging.info(f"Invoice {invoice_id} status updated: Cumulative_Paid={cumulative_paid}, Status={new_status}")
        except Exception as e:
            logging.error(f"Error checking invoice payment status: {e}", exc_info=True)

    def add_global_payment(self, client_id, payment_date, amount, payment_method='Espèce', reference=None, notes=None, auto_allocate_fifo=True, user_id=None):
        """
        Enregistre un versement global ou acompte pour un client.
        Si auto_allocate_fifo=True : ventile automatiquement le montant sur les factures impayées les plus anciennes (FIFO)
        et enregistre le reliquat éventuel en acompte libre non lettré.
        Si auto_allocate_fifo=False : enregistre le paiement global en acompte libre directement déductible du solde client.
        """
        amount = float(amount or 0.0)
        if amount <= 0:
            logging.warning(f"add_global_payment called with non-positive amount {amount}")
            return None

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Vérifier l'existence du client
                cursor.execute("SELECT Client_ID, Client_Name FROM Clients WHERE Client_ID = %s", (client_id,))
                client = cursor.fetchone()
                if not client:
                    logging.error(f"Client {client_id} not found for global payment.")
                    return None

                created_payment_ids = []
                allocated_invoices = []

                if not auto_allocate_fifo:
                    # Enregistrement direct en acompte libre
                    query = """
                        INSERT INTO Client_Payments 
                        (Client_ID, Invoice_ID, Payment_Date, Amount, Payment_Method, Reference, Notes, Created_By) 
                        VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                    """
                    note_text = f"Acompte libre / versement global. {notes or ''}".strip()
                    cursor.execute(query, (client_id, payment_date, amount, payment_method, reference, note_text, user_id))
                    pay_id = cursor.lastrowid
                    created_payment_ids.append(pay_id)
                    return {
                        "success": True,
                        "client_id": client_id,
                        "payment_ids": created_payment_ids,
                        "total_amount": amount,
                        "allocated_to_invoices": 0.0,
                        "free_advance": amount,
                        "invoices_affected": []
                    }

                # Auto-allocation FIFO
                cursor.execute("""
                    SELECT * FROM (
                        SELECT 
                            i.Invoice_ID, i.Invoice_No, i.Invoice_Date, i.Status, i.Total_Amount_TTC,
                            ROUND(
                                COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0),
                                2
                            ) AS Paid_Amount,
                            ROUND(
                                i.Total_Amount_TTC - (
                                    COALESCE((SELECT SUM(pp.Amount) FROM POS_Sale_Payments pp WHERE pp.Invoice_ID = i.Invoice_ID AND pp.Payment_Method != 'Credit'), 0)
                                    + COALESCE((SELECT SUM(cp.Amount) FROM Client_Payments cp WHERE cp.Invoice_ID = i.Invoice_ID), 0)
                                ),
                                2
                            ) AS Remaining
                        FROM Sales_Invoices i
                        WHERE i.Client_ID = %s 
                          AND i.Status NOT IN ('Cancelled', 'Draft', 'Paid')
                          AND i.Invoice_No NOT LIKE 'DEV-%'
                          AND i.Invoice_No NOT LIKE 'BC-%'
                    ) unpaid
                    WHERE unpaid.Remaining > 0.009
                    ORDER BY unpaid.Invoice_Date ASC, unpaid.Invoice_ID ASC
                """, (client_id,))
                unpaid_invoices = cursor.fetchall()

                remaining_to_allocate = amount
                total_allocated = 0.0

                for inv in unpaid_invoices:
                    if remaining_to_allocate <= 0.009:
                        break

                    inv_id = inv['Invoice_ID']
                    inv_no = inv.get('Invoice_No') or f"#{inv_id}"
                    inv_rem = float(inv['Remaining'])
                    alloc = min(remaining_to_allocate, inv_rem)
                    alloc = round(alloc, 2)

                    # Enregistrer le paiement lié à cette facture
                    query = """
                        INSERT INTO Client_Payments 
                        (Client_ID, Invoice_ID, Payment_Date, Amount, Payment_Method, Reference, Notes, Created_By) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    alloc_notes = f"Ventilation FIFO facture {inv_no}. {notes or ''}".strip()
                    cursor.execute(query, (client_id, inv_id, payment_date, alloc, payment_method, reference, alloc_notes, user_id))
                    pay_id = cursor.lastrowid
                    created_payment_ids.append(pay_id)

                    # Mettre à jour le statut de la facture si entièrement soldée
                    new_paid = round(float(inv.get('Paid_Amount') or 0.0) + alloc, 2)
                    new_status = 'Paid' if new_paid >= (float(inv['Total_Amount_TTC']) - 0.009) else 'Validated'
                    if new_status == 'Paid':
                        cursor.execute(
                            "UPDATE Sales_Invoices SET Status = 'Paid' WHERE Invoice_ID = %s",
                            (inv_id,)
                        )

                    allocated_invoices.append({
                        "invoice_id": inv_id,
                        "invoice_no": inv_no,
                        "allocated": alloc,
                        "new_status": new_status
                    })

                    remaining_to_allocate = round(remaining_to_allocate - alloc, 2)
                    total_allocated = round(total_allocated + alloc, 2)

                free_advance = 0.0
                if remaining_to_allocate > 0.009:
                    # Surplus non lettré en acompte libre
                    free_advance = remaining_to_allocate
                    query = """
                        INSERT INTO Client_Payments 
                        (Client_ID, Invoice_ID, Payment_Date, Amount, Payment_Method, Reference, Notes, Created_By) 
                        VALUES (%s, NULL, %s, %s, %s, %s, %s, %s)
                    """
                    surplus_notes = f"Acompte libre / surplus de règlement ({free_advance} DA). {notes or ''}".strip()
                    cursor.execute(query, (client_id, payment_date, free_advance, payment_method, reference, surplus_notes, user_id))
                    pay_id = cursor.lastrowid
                    created_payment_ids.append(pay_id)

                logging.info(
                    f"Global payment of {amount} DA recorded for Client {client_id}: "
                    f"Allocated: {total_allocated} DA across {len(allocated_invoices)} invoices, Free advance: {free_advance} DA."
                )

                return {
                    "success": True,
                    "client_id": client_id,
                    "payment_ids": created_payment_ids,
                    "total_amount": amount,
                    "allocated_to_invoices": total_allocated,
                    "free_advance": free_advance,
                    "invoices_affected": allocated_invoices
                }
        except Exception as ex:
            logging.error(f"Error in add_global_payment: {ex}", exc_info=True)
            return None

    def get_payments_by_client(self, client_id):
        """
        جلب جميع المدفوعات الخاصة بعميل محدد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT * FROM Client_Payments WHERE Client_ID = %s ORDER BY Payment_Date DESC"
                cursor.execute(query, (client_id,))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching payments for client {client_id}: {e}")
            raise

    def get_all_payments(self):
        """
        جلب جميع المدفوعات لجميع العملاء.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT p.*, c.Client_Name 
                    FROM Client_Payments p
                    JOIN Clients c ON p.Client_ID = c.Client_ID
                    ORDER BY p.Payment_Date DESC, p.Payment_ID DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching all payments: {e}")
            raise
