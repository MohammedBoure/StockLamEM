# database/sav_workflow_manager.py
"""
After-Sales Service & Repair (SAV / Réparation) 4-Stage Workflow Manager.
Implements:
1. Stage 1 (SAV_RECEIVED): Customer reception & Bon de Réparation emission (Serial -> IN_SAV).
2. Stage 2 (SAV_SENT_TO_TECH): Transfer to external maintenance center or specialist technician.
3. Stage 3 (SAV_RETURNED_FROM_TECH): Return from technician & diagnostic verification (REPAIRED vs IRREPARABLE).
4. Stage 4 (SAV_CLOSED_DELIVERED): Final delivery to customer & ticket closure (Serial -> DISPATCHED).
5. Irreparable Defect Protocol: Automated Versement Virtuel into Client Wallet (Serial -> SCRAPPED, Δ Till_Balance = 0.00 DA).
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .serial_tracking_manager import SerialTrackingManager

logger = logging.getLogger("StockLam.Backend.SAVWorkflow")


class SAVWorkflowManager:
    """Manages the 4-stage SAV repair state machine and irreparable virtual wallet compensation."""

    VALID_STAGES = (
        "SAV_RECEIVED",
        "SAV_SENT_TO_TECH",
        "SAV_RETURNED_FROM_TECH",
        "SAV_CLOSED_DELIVERED",
    )

    def __init__(self, db_instance):
        self.db = db_instance

    def _get_connection(self):
        if hasattr(self.db, "get_raw_connection"):
            conn = self.db.get_raw_connection()
            if conn is not None:
                return conn
        if hasattr(self.db, "get_connection"):
            return self.db.get_connection()
        if hasattr(self.db, "cursor"):
            return self.db
        raise RuntimeError("No valid database connection provider found.")

    # =========================================================================
    # STAGE 1: استقبال المنتج من الزبون (SAV_RECEIVED - Bon de Réparation)
    # =========================================================================

    def check_in_reception(
        self,
        serial_number: str,
        symptom: str,
        cosmetic_condition: str,
        accessories: str,
        received_by_user_id: int,
        client_id_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Stage 1: Receives defective appliance from customer, emits Bon de Réparation,
        and transitions physical serial to IN_SAV.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            sn_clean = SerialTrackingManager.sanitize_serial_number(serial_number)
            cursor.execute(
                """
                SELECT Serial_ID, Product_ID, Original_Client_ID, Original_Sales_Invoice_ID,
                       Customer_Warranty_End, Status
                FROM Product_Serials
                WHERE Serial_Number = %s
                FOR UPDATE
                """,
                (sn_clean,),
            )
            s = cursor.fetchone()
            if not s:
                raise ValueError(f"Serial '{sn_clean}' not found in system.")

            is_under_warranty = True
            w_end = s.get("Customer_Warranty_End")
            if w_end:
                if isinstance(w_end, str):
                    try:
                        w_end = date.fromisoformat(w_end[:10])
                    except ValueError:
                        w_end = None
                if isinstance(w_end, date):
                    is_under_warranty = date.today() <= w_end

            client_id = int(client_id_override or s.get("Original_Client_ID") or 1)
            ts_suffix = int(datetime.now().timestamp() * 1000) % 100000
            ticket_num = f"SAV-{datetime.now().strftime('%Y%m%d')}-{ts_suffix:05d}"
            bon_rep_code = f"BREP-{datetime.now().strftime('%Y%m%d')}-{ts_suffix:05d}"

            cursor.execute(
                """
                INSERT INTO SAV_Tickets (
                    Ticket_Number, Bon_Reparation_Barcode, Serial_ID, Product_ID,
                    Client_ID, Original_Invoice_ID, Received_By_User_ID,
                    Customer_Stated_Symptom, Cosmetic_Condition_Notes,
                    Accessories_Included, Is_Under_Warranty,
                    Current_Stage, Resolution_Status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'SAV_RECEIVED', 'PENDING_EVALUATION')
                """,
                (
                    ticket_num,
                    bon_rep_code,
                    s["Serial_ID"],
                    s["Product_ID"],
                    client_id,
                    s.get("Original_Sales_Invoice_ID"),
                    int(received_by_user_id),
                    symptom,
                    cosmetic_condition,
                    accessories,
                    bool(is_under_warranty),
                ),
            )
            ticket_id = cursor.lastrowid

            cursor.execute(
                "UPDATE Product_Serials SET Status = 'IN_SAV' WHERE Serial_ID = %s",
                (s["Serial_ID"],),
            )

            cursor.execute(
                """
                INSERT INTO Product_Serial_History (
                    Serial_ID, Previous_Status, New_Status, Voucher_Type,
                    Voucher_ID, Changed_By_User_ID, Action_Notes
                ) VALUES (%s, %s, 'IN_SAV', 'BON_REPARATION', %s, %s, 'SAV Stage 1 Intake - Bon de Réparation')
                """,
                (s["Serial_ID"], s["Status"], ticket_id, int(received_by_user_id)),
            )

            cursor.execute(
                """
                INSERT INTO SAV_Ticket_History (
                    SAV_Ticket_ID, From_Stage, To_Stage, Action_Performed_By_User_ID, Stage_Notes
                ) VALUES (%s, NULL, 'SAV_RECEIVED', %s, %s)
                """,
                (ticket_id, int(received_by_user_id), f"Bon de Réparation {bon_rep_code}: {symptom}"),
            )

            conn.commit()
            return {
                "success": True,
                "ticket_id": ticket_id,
                "ticket_number": ticket_num,
                "bon_reparation_barcode": bon_rep_code,
                "current_stage": "SAV_RECEIVED",
                "under_warranty": bool(is_under_warranty),
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error in SAV Stage 1 reception: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # STAGE 2: إرسال المنتج للمصلح (SAV_SENT_TO_TECH)
    # =========================================================================

    def dispatch_to_technician(
        self,
        sav_ticket_id: int,
        technician_id: Optional[int],
        user_id: int,
        notes: str = "Envoi atelier technique / réparateur agréé",
    ) -> Dict[str, Any]:
        """Stage 2: Transfers the unit from reception to the internal technician or external repair center."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                "SELECT SAV_Ticket_ID, Serial_ID, Current_Stage FROM SAV_Tickets WHERE SAV_Ticket_ID = %s FOR UPDATE",
                (int(sav_ticket_id),),
            )
            ticket = cursor.fetchone()
            if not ticket:
                raise ValueError("SAV Ticket not found.")
            if ticket["Current_Stage"] != "SAV_RECEIVED":
                raise ValueError(
                    f"Invalid SAV transition: expected 'SAV_RECEIVED', got '{ticket['Current_Stage']}'."
                )

            cursor.execute(
                """
                UPDATE SAV_Tickets
                SET Current_Stage = 'SAV_SENT_TO_TECH',
                    Assigned_Technician_ID = %s,
                    Sent_To_Tech_At = CURRENT_TIMESTAMP
                WHERE SAV_Ticket_ID = %s
                """,
                (int(technician_id) if technician_id else None, int(sav_ticket_id)),
            )

            cursor.execute(
                """
                INSERT INTO SAV_Ticket_History (
                    SAV_Ticket_ID, From_Stage, To_Stage, Action_Performed_By_User_ID, Stage_Notes
                ) VALUES (%s, 'SAV_RECEIVED', 'SAV_SENT_TO_TECH', %s, %s)
                """,
                (int(sav_ticket_id), int(user_id), notes),
            )

            conn.commit()
            return {
                "success": True,
                "ticket_id": int(sav_ticket_id),
                "current_stage": "SAV_SENT_TO_TECH",
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error in SAV Stage 2 technician dispatch: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # STAGE 3: العودة من المصلح (SAV_RETURNED_FROM_TECH)
    # =========================================================================

    def record_technician_return(
        self,
        sav_ticket_id: int,
        resolution_status: str,
        diagnostic_summary: str,
        user_id: int,
        parts_cost: Decimal = Decimal("0.00"),
        labor_fee: Decimal = Decimal("0.00"),
        customer_charge: Decimal = Decimal("0.00"),
    ) -> Dict[str, Any]:
        """
        Stage 3: Receives appliance back from technician and records repair evaluation:
        - resolution_status = 'REPAIRED' or 'IRREPARABLE'
        """
        res_clean = (resolution_status or "REPAIRED").strip().upper()
        if res_clean not in ("REPAIRED", "IRREPARABLE", "CLIENT_REFUSED_ESTIMATE"):
            raise ValueError(f"Unsupported SAV resolution status: {res_clean}")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                "SELECT SAV_Ticket_ID, Current_Stage FROM SAV_Tickets WHERE SAV_Ticket_ID = %s FOR UPDATE",
                (int(sav_ticket_id),),
            )
            ticket = cursor.fetchone()
            if not ticket:
                raise ValueError("SAV Ticket not found.")
            if ticket["Current_Stage"] != "SAV_SENT_TO_TECH":
                raise ValueError(
                    f"Invalid SAV transition: expected 'SAV_SENT_TO_TECH', got '{ticket['Current_Stage']}'."
                )

            cursor.execute(
                """
                UPDATE SAV_Tickets
                SET Current_Stage = 'SAV_RETURNED_FROM_TECH',
                    Resolution_Status = %s,
                    Diagnostic_Summary = %s,
                    Parts_Total_Cost = %s,
                    Labor_Fee = %s,
                    Customer_Charge_Total = %s,
                    Returned_From_Tech_At = CURRENT_TIMESTAMP
                WHERE SAV_Ticket_ID = %s
                """,
                (
                    res_clean,
                    diagnostic_summary,
                    Decimal(str(parts_cost or "0.00")),
                    Decimal(str(labor_fee or "0.00")),
                    Decimal(str(customer_charge or "0.00")),
                    int(sav_ticket_id),
                ),
            )

            cursor.execute(
                """
                INSERT INTO SAV_Ticket_History (
                    SAV_Ticket_ID, From_Stage, To_Stage, Action_Performed_By_User_ID, Stage_Notes
                ) VALUES (%s, 'SAV_SENT_TO_TECH', 'SAV_RETURNED_FROM_TECH', %s, %s)
                """,
                (int(sav_ticket_id), int(user_id), f"[{res_clean}] {diagnostic_summary}"),
            )

            conn.commit()
            return {
                "success": True,
                "ticket_id": int(sav_ticket_id),
                "current_stage": "SAV_RETURNED_FROM_TECH",
                "resolution_status": res_clean,
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error in SAV Stage 3 technician return: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # STAGE 4A: تسليم المنتج للزبون (SAV_CLOSED_DELIVERED - Repaired Unit)
    # =========================================================================

    def deliver_repaired_to_client(
        self,
        sav_ticket_id: int,
        user_id: int,
        customer_signature: str = "Signé par le client",
    ) -> Dict[str, Any]:
        """
        Stage 4A: Delivers repaired product back to customer, closes SAV ticket,
        and transitions serial status back to DISPATCHED.
        """
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                SELECT SAV_Ticket_ID, Serial_ID, Current_Stage, Resolution_Status
                FROM SAV_Tickets
                WHERE SAV_Ticket_ID = %s
                FOR UPDATE
                """,
                (int(sav_ticket_id),),
            )
            ticket = cursor.fetchone()
            if not ticket:
                raise ValueError("SAV Ticket not found.")
            if ticket["Current_Stage"] != "SAV_RETURNED_FROM_TECH":
                raise ValueError(
                    f"Cannot deliver ticket before return from technician (Current: {ticket['Current_Stage']})."
                )

            cursor.execute(
                """
                UPDATE SAV_Tickets
                SET Current_Stage = 'SAV_CLOSED_DELIVERED',
                    Resolution_Status = 'REPAIRED',
                    Delivered_To_Client_Date = CURRENT_TIMESTAMP,
                    Delivery_Acknowledgment_Signature = %s
                WHERE SAV_Ticket_ID = %s
                """,
                (customer_signature, int(sav_ticket_id)),
            )

            cursor.execute(
                "UPDATE Product_Serials SET Status = 'DISPATCHED' WHERE Serial_ID = %s",
                (ticket["Serial_ID"],),
            )

            cursor.execute(
                """
                INSERT INTO Product_Serial_History (
                    Serial_ID, Previous_Status, New_Status, Voucher_Type,
                    Voucher_ID, Changed_By_User_ID, Action_Notes
                ) VALUES (%s, 'IN_SAV', 'DISPATCHED', 'SAV_RESTITUTION', %s, %s, 'SAV Stage 4 Client Delivery')
                """,
                (ticket["Serial_ID"], int(sav_ticket_id), int(user_id)),
            )

            cursor.execute(
                """
                INSERT INTO SAV_Ticket_History (
                    SAV_Ticket_ID, From_Stage, To_Stage, Action_Performed_By_User_ID, Stage_Notes
                ) VALUES (%s, 'SAV_RETURNED_FROM_TECH', 'SAV_CLOSED_DELIVERED', %s, %s)
                """,
                (int(sav_ticket_id), int(user_id), f"Remis au client ({customer_signature})"),
            )

            conn.commit()
            return {
                "success": True,
                "ticket_id": int(sav_ticket_id),
                "current_stage": "SAV_CLOSED_DELIVERED",
                "serial_status": "DISPATCHED",
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error in SAV Stage 4 delivery: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    # =========================================================================
    # STAGE 4B: آلية عدم إمكانية الإصلاح (Irreparable Compensation -> Versement Virtuel)
    # =========================================================================

    def process_irreparable_compensation(
        self,
        sav_ticket_id: int,
        admin_user_id: int,
        compensation_amount: Decimal,
        notes: str = "Compensation SAV appareil irréparable (Versement Virtuel)",
    ) -> Dict[str, Any]:
        """
        Stage 4B: When an appliance is certified IRREPARABLE:
        - Issues an automated Versement Virtuel into the customer's wallet (Client_Wallets).
        - ZERO physical cash leaves the Caisse (Δ Till_Balance = 0.00 DA).
        - Permanently transitions physical serial status to SCRAPPED.
        - Closes the SAV ticket.
        """
        comp_dec = Decimal(str(compensation_amount)).quantize(Decimal("0.01"))
        if comp_dec <= Decimal("0.00"):
            raise ValueError("Compensation amount must be strictly positive.")

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                SELECT SAV_Ticket_ID, Serial_ID, Client_ID, Current_Stage
                FROM SAV_Tickets
                WHERE SAV_Ticket_ID = %s
                FOR UPDATE
                """,
                (int(sav_ticket_id),),
            )
            t = cursor.fetchone()
            if not t:
                raise ValueError("SAV ticket not found.")

            # Lock and fetch Client Wallet
            cursor.execute(
                """
                SELECT Wallet_ID, Current_Balance,
                       COALESCE(Virtual_Credit_Balance, 0.00) AS Virtual_Credit_Balance
                FROM Client_Wallets
                WHERE Client_ID = %s
                FOR UPDATE
                """,
                (int(t["Client_ID"]),),
            )
            wallet = cursor.fetchone()
            if not wallet:
                cursor.execute(
                    """
                    INSERT INTO Client_Wallets (
                        Client_ID, Current_Balance, Real_Deposit_Balance, Virtual_Credit_Balance
                    ) VALUES (%s, 0.00, 0.00, 0.00)
                    """,
                    (int(t["Client_ID"]),),
                )
                wallet_id = cursor.lastrowid
                bal_before = Decimal("0.00")
                virt_before = Decimal("0.00")
            else:
                wallet_id = wallet["Wallet_ID"]
                bal_before = Decimal(str(wallet.get("Current_Balance") or "0.00"))
                virt_before = Decimal(str(wallet.get("Virtual_Credit_Balance") or "0.00"))

            bal_after = (bal_before + comp_dec).quantize(Decimal("0.01"))
            virt_after = (virt_before + comp_dec).quantize(Decimal("0.01"))

            # Create Immutable Wallet Transaction (Affects_Physical_Caisse = FALSE)
            cursor.execute(
                """
                INSERT INTO Client_Wallet_Transactions (
                    Wallet_ID, Client_ID, Transaction_Type, Amount,
                    Balance_Before, Balance_After, Source_Document_Type,
                    Source_Document_ID, Authorized_By_User_ID,
                    Affects_Physical_Caisse, Transaction_Notes
                ) VALUES (%s, %s, 'SAV_IRREPARABLE_COMPENSATION', %s, %s, %s, 'SAV_TICKET', %s, %s, FALSE, %s)
                """,
                (
                    wallet_id,
                    int(t["Client_ID"]),
                    comp_dec,
                    bal_before,
                    bal_after,
                    int(sav_ticket_id),
                    int(admin_user_id),
                    notes,
                ),
            )
            tx_id = cursor.lastrowid

            # Update Wallet Balance
            cursor.execute(
                """
                UPDATE Client_Wallets
                SET Current_Balance = %s,
                    Virtual_Credit_Balance = %s,
                    Total_Lifetime_Credited = COALESCE(Total_Lifetime_Credited, 0.00) + %s,
                    Last_Transaction_At = CURRENT_TIMESTAMP
                WHERE Wallet_ID = %s
                """,
                (bal_after, virt_after, comp_dec, wallet_id),
            )

            # Transition Serial to SCRAPPED
            cursor.execute(
                "UPDATE Product_Serials SET Status = 'SCRAPPED' WHERE Serial_ID = %s",
                (t["Serial_ID"],),
            )

            cursor.execute(
                """
                INSERT INTO Product_Serial_History (
                    Serial_ID, Previous_Status, New_Status, Voucher_Type,
                    Voucher_ID, Changed_By_User_ID, Action_Notes
                ) VALUES (%s, 'IN_SAV', 'SCRAPPED', 'SCRAP_VOUCHER', %s, %s, 'Irreparable appliance scrap write-off')
                """,
                (t["Serial_ID"], int(sav_ticket_id), int(admin_user_id)),
            )

            # Close SAV Ticket
            cursor.execute(
                """
                UPDATE SAV_Tickets
                SET Current_Stage = 'SAV_CLOSED_DELIVERED',
                    Resolution_Status = 'IRREPARABLE',
                    Irreparable_Wallet_Transaction_ID = %s,
                    Delivered_To_Client_Date = CURRENT_TIMESTAMP
                WHERE SAV_Ticket_ID = %s
                """,
                (tx_id, int(sav_ticket_id)),
            )

            cursor.execute(
                """
                INSERT INTO SAV_Ticket_History (
                    SAV_Ticket_ID, From_Stage, To_Stage, Action_Performed_By_User_ID, Stage_Notes
                ) VALUES (%s, %s, 'SAV_CLOSED_DELIVERED', %s, %s)
                """,
                (int(sav_ticket_id), t.get("Current_Stage"), int(admin_user_id), f"Irréparable -> Versement Virtuel {comp_dec} DA"),
            )

            conn.commit()
            return {
                "success": True,
                "wallet_transaction_id": tx_id,
                "credited_amount": float(comp_dec),
                "new_wallet_balance": float(bal_after),
                "serial_status": "SCRAPPED",
                "physical_till_delta": 0.0,
            }
        except Exception as err:
            conn.rollback()
            logger.error(f"Error processing irreparable SAV compensation: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def get_all_sav_tickets(self, stage_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetches SAV tickets for the 4-stage Kanban board and SAV management table."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                where_sql = "WHERE t.Current_Stage = %s" if stage_filter else ""
                params = (stage_filter,) if stage_filter else ()
                query = f"""
                    SELECT
                        t.*,
                        ps.Serial_Number,
                        p.Product_Name,
                        COALESCE(p.Brand_Mark, '') AS Brand_Mark,
                        COALESCE(c.Client_Name, 'Client SAV') AS Client_Name,
                        COALESCE(tech.Full_Name, 'Non assigné') AS Technician_Name
                    FROM SAV_Tickets t
                    JOIN Product_Serials ps ON t.Serial_ID = ps.Serial_ID
                    JOIN Products_Master p ON t.Product_ID = p.Product_ID
                    LEFT JOIN Clients c ON t.Client_ID = c.Client_ID
                    LEFT JOIN SAV_Technicians tech ON t.Assigned_Technician_ID = tech.Technician_ID
                    {where_sql}
                    ORDER BY t.Reception_Date DESC
                    LIMIT 300
                """
                cursor.execute(query, params)
                return cursor.fetchall() or []
        except Exception as err:
            logger.error(f"Error fetching SAV tickets: {err}")
            return []


# Alias matching docs service layer name
SAVWorkflowService = SAVWorkflowManager
