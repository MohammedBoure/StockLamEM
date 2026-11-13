# -*- coding: utf-8 -*-
"""
database/product_reference_manager.py
=====================================
Product References Manager (إدارة مراجع المنتجات Réf).

A product (Products_Master) can own several `Réf` codes (manufacturer ref, supplier ref,
legacy ref...). Réf is distinct from the scanner Barcode. Each Réf code is globally unique
so that a lookup by Réf always resolves to exactly one product.

Provides:
- Lazy creation of the `Product_References` table + one-shot migration of the legacy
  `Products_Master.Manuf_Cat_No` values as primary references.
- CRUD (add / update / delete / set primary) with global uniqueness validation.
- Lookups: references of one product, global listing with search, product ids matching a Réf.
"""

import logging
from typing import Any, Dict, List, Optional

import mysql.connector

logger = logging.getLogger("StockLam.Backend.ProductReferences")

MAX_REF_LENGTH = 100

# Reusable SQL fragments (alias `p` = Products_Master) so every product query can expose Réf data.
PRIMARY_REF_SQL = (
    "(SELECT pr.Ref_Code FROM Product_References pr WHERE pr.Product_ID = p.Product_ID "
    "ORDER BY pr.Is_Primary DESC, pr.Ref_ID ASC LIMIT 1) AS Primary_Ref"
)
ALL_REFS_SQL = (
    "(SELECT GROUP_CONCAT(pr.Ref_Code ORDER BY pr.Is_Primary DESC, pr.Ref_ID ASC SEPARATOR ' | ') "
    "FROM Product_References pr WHERE pr.Product_ID = p.Product_ID) AS All_Refs"
)
REF_SEARCH_EXISTS_SQL = (
    "EXISTS (SELECT 1 FROM Product_References pr WHERE pr.Product_ID = p.Product_ID AND pr.Ref_Code LIKE %s)"
)


class ProductReferenceManager:
    """Manages the `Product_References` registry (several Réf codes per product)."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_table()

    # ------------------------------------------------------------------ schema
    def _ensure_table(self) -> None:
        """Creates Product_References (if missing) and migrates legacy Manuf_Cat_No once."""
        if ProductReferenceManager._schema_checked:
            return
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                base_columns = """
                    Ref_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    Product_ID INT UNSIGNED NOT NULL,
                    Ref_Code VARCHAR(100) NOT NULL,
                    Is_Primary BOOLEAN NOT NULL DEFAULT FALSE,
                    Notes VARCHAR(255) NULL,
                    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_product_ref_code (Ref_Code),
                    KEY idx_product_ref_product (Product_ID)
                """
                try:
                    cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS Product_References (
                            {base_columns},
                            CONSTRAINT fk_product_ref_product FOREIGN KEY (Product_ID)
                                REFERENCES Products_Master(Product_ID) ON DELETE CASCADE
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                        """
                    )
                except mysql.connector.Error as fk_err:
                    # Fallback without FK (e.g. incompatible legacy Products_Master definition)
                    logger.warning("Product_References FK creation skipped: %s", fk_err)
                    cursor.execute(
                        f"CREATE TABLE IF NOT EXISTS Product_References ({base_columns}) "
                        "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                    )

                cursor.execute("SELECT COUNT(*) AS cnt FROM Product_References")
                row = cursor.fetchone()
                count = row.get("cnt") if isinstance(row, dict) else (row[0] if row else 0)
                if not count:
                    # One-shot migration of the legacy manufacturer catalogue number
                    cursor.execute(
                        """
                        INSERT IGNORE INTO Product_References (Product_ID, Ref_Code, Is_Primary, Notes)
                        SELECT Product_ID, TRIM(Manuf_Cat_No), TRUE, 'Migré depuis la fiche produit'
                        FROM Products_Master
                        WHERE Manuf_Cat_No IS NOT NULL AND TRIM(Manuf_Cat_No) <> ''
                        """
                    )
            ProductReferenceManager._schema_checked = True
        except Exception as err:
            logger.debug("Product_References schema check skipped or deferred: %s", err)

    # --------------------------------------------------------------- utilities
    @staticmethod
    def normalize_ref_code(ref_code: Optional[str]) -> str:
        """Trims and validates a Réf code; raises ValueError when empty or too long."""
        clean = str(ref_code or "").strip()
        if not clean:
            raise ValueError("Le code Réf est obligatoire.")
        if len(clean) > MAX_REF_LENGTH:
            raise ValueError(f"Le code Réf ne doit pas dépasser {MAX_REF_LENGTH} caractères.")
        return clean

    # ------------------------------------------------------------------- reads
    def get_all_references(self, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists every Réf joined with its product (optionally filtered by Réf / product / brand)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                params: List[Any] = []
                where = "p.Deleted_At IS NULL"
                if search and search.strip():
                    term = f"%{search.strip()}%"
                    where += (
                        " AND (r.Ref_Code LIKE %s OR p.Product_Name LIKE %s"
                        " OR COALESCE(p.Brand_Mark, '') LIKE %s OR COALESCE(r.Notes, '') LIKE %s)"
                    )
                    params.extend([term, term, term, term])
                cursor.execute(
                    f"""
                    SELECT r.Ref_ID, r.Product_ID, r.Ref_Code, r.Is_Primary, r.Notes, r.Created_At,
                           p.Product_Name, COALESCE(p.Brand_Mark, '') AS Brand_Mark,
                           COALESCE(p.Barcode, '') AS Barcode
                    FROM Product_References r
                    JOIN Products_Master p ON p.Product_ID = r.Product_ID
                    WHERE {where}
                    ORDER BY p.Product_Name ASC, r.Is_Primary DESC, r.Ref_ID ASC
                    """,
                    tuple(params),
                )
                return cursor.fetchall() or []
        except mysql.connector.Error as err:
            logger.error("Error loading product references: %s", err)
            return []

    def get_references_for_product(self, product_id: int) -> List[Dict[str, Any]]:
        """Returns the Réf codes of one product (primary first)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(
                    """
                    SELECT Ref_ID, Product_ID, Ref_Code, Is_Primary, Notes, Created_At
                    FROM Product_References
                    WHERE Product_ID = %s
                    ORDER BY Is_Primary DESC, Ref_ID ASC
                    """,
                    (int(product_id),),
                )
                return cursor.fetchall() or []
        except mysql.connector.Error as err:
            logger.error("Error loading references of product %s: %s", product_id, err)
            return []

    def find_product_ids_by_ref(self, query: str, exact: bool = False) -> List[int]:
        """Returns the ids of products owning a Réf matching `query` (substring unless exact)."""
        q = str(query or "").strip()
        if not q:
            return []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                if exact:
                    cursor.execute("SELECT DISTINCT Product_ID FROM Product_References WHERE Ref_Code = %s", (q,))
                else:
                    cursor.execute(
                        "SELECT DISTINCT Product_ID FROM Product_References WHERE Ref_Code LIKE %s",
                        (f"%{q}%",),
                    )
                return [int(r["Product_ID"]) for r in (cursor.fetchall() or [])]
        except mysql.connector.Error as err:
            logger.error("Error searching product ids by Réf '%s': %s", q, err)
            return []

    # ------------------------------------------------------------------ writes
    def add_reference(
        self,
        product_id: int,
        ref_code: str,
        is_primary: bool = False,
        notes: str = "",
    ) -> int:
        """
        Adds a Réf to a product and returns its Ref_ID.
        The first Réf of a product automatically becomes primary.
        Raises ValueError if the code is empty or already used (by any product).
        """
        code = self.normalize_ref_code(ref_code)
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT r.Ref_ID, p.Product_Name
                FROM Product_References r
                JOIN Products_Master p ON p.Product_ID = r.Product_ID
                WHERE r.Ref_Code = %s
                """,
                (code,),
            )
            dup = cursor.fetchone()
            if dup:
                raise ValueError(f"La Réf « {code} » est déjà utilisée par le produit « {dup['Product_Name']} ».")

            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM Product_References WHERE Product_ID = %s", (int(product_id),)
            )
            row = cursor.fetchone()
            existing = int(row.get("cnt") or 0) if isinstance(row, dict) else int(row[0] if row else 0)
            make_primary = bool(is_primary) or existing == 0
            if make_primary and existing:
                cursor.execute(
                    "UPDATE Product_References SET Is_Primary = FALSE WHERE Product_ID = %s", (int(product_id),)
                )
            cursor.execute(
                """
                INSERT INTO Product_References (Product_ID, Ref_Code, Is_Primary, Notes)
                VALUES (%s, %s, %s, %s)
                """,
                (int(product_id), code, make_primary, (notes or "").strip() or None),
            )
            return int(cursor.lastrowid)

    def update_reference(
        self,
        ref_id: int,
        ref_code: str,
        is_primary: bool = False,
        notes: str = "",
    ) -> None:
        """Edits a Réf (code / primary flag / notes) while keeping global uniqueness."""
        code = self.normalize_ref_code(ref_code)
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT Product_ID FROM Product_References WHERE Ref_ID = %s", (int(ref_id),))
            current = cursor.fetchone()
            if not current:
                raise ValueError("Réf introuvable.")
            cursor.execute(
                """
                SELECT r.Ref_ID, p.Product_Name
                FROM Product_References r
                JOIN Products_Master p ON p.Product_ID = r.Product_ID
                WHERE r.Ref_Code = %s AND r.Ref_ID <> %s
                """,
                (code, int(ref_id)),
            )
            dup = cursor.fetchone()
            if dup:
                raise ValueError(f"La Réf « {code} » est déjà utilisée par le produit « {dup['Product_Name']} ».")
            product_id = int(current["Product_ID"])
            if is_primary:
                cursor.execute(
                    "UPDATE Product_References SET Is_Primary = FALSE WHERE Product_ID = %s", (product_id,)
                )
            cursor.execute(
                """
                UPDATE Product_References
                SET Ref_Code = %s, Is_Primary = %s, Notes = %s
                WHERE Ref_ID = %s
                """,
                (code, bool(is_primary), (notes or "").strip() or None, int(ref_id)),
            )
            self._ensure_primary_exists(cursor, product_id)

    def set_primary_reference(self, ref_id: int) -> None:
        """Marks a Réf as the primary one of its product."""
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT Product_ID FROM Product_References WHERE Ref_ID = %s", (int(ref_id),))
            current = cursor.fetchone()
            if not current:
                raise ValueError("Réf introuvable.")
            cursor.execute(
                "UPDATE Product_References SET Is_Primary = (Ref_ID = %s) WHERE Product_ID = %s",
                (int(ref_id), int(current["Product_ID"])),
            )

    def delete_reference(self, ref_id: int) -> None:
        """Deletes a Réf; promotes the oldest remaining Réf of the product to primary if needed."""
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT Product_ID FROM Product_References WHERE Ref_ID = %s", (int(ref_id),))
            current = cursor.fetchone()
            if not current:
                return
            cursor.execute("DELETE FROM Product_References WHERE Ref_ID = %s", (int(ref_id),))
            self._ensure_primary_exists(cursor, int(current["Product_ID"]))

    @staticmethod
    def _ensure_primary_exists(cursor, product_id: int) -> None:
        """Guarantees that a product owning at least one Réf has exactly one primary Réf."""
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM Product_References WHERE Product_ID = %s AND Is_Primary = TRUE",
            (int(product_id),),
        )
        row = cursor.fetchone()
        primaries = int(row.get("cnt") or 0) if isinstance(row, dict) else int(row[0] if row else 0)
        if primaries == 0:
            cursor.execute(
                """
                UPDATE Product_References SET Is_Primary = TRUE
                WHERE Product_ID = %s ORDER BY Ref_ID ASC LIMIT 1
                """,
                (int(product_id),),
            )
