# -*- coding: utf-8 -*-
"""
database/product_color_manager.py
=================================
Product Colors Manager (إدارة ألوان المنتجات).
Provides:
- CRUD operations for appliance & product color finishes (Inox, Blanc, Noir, Silver, etc.)
- Hex color code storage and visual badge previews
- Active/Inactive status toggle
- Auto-seeding of standard industry color finishes
"""

import logging
from typing import Any, Dict, List, Optional
import mysql.connector

logger = logging.getLogger("StockLam.Backend.ProductColors")

DEFAULT_PRODUCT_COLORS = [
    ("Inox", "#8A9EA7", "Finition acier inoxydable brossé"),
    ("Blanc", "#FFFFFF", "Finition émail blanc standard"),
    ("Noir", "#1E293B", "Finition noir mat / laqué"),
    ("Silver", "#CBD5E1", "Finition gris argent métallisé"),
    ("Gris Anthracite", "#475569", "Finition gris foncé contemporain"),
    ("Beige", "#F5F5DC", "Finition crème / ivoire"),
    ("Rouge", "#DC2626", "Finition rouge brillant"),
    ("Marron", "#78350F", "Finition brun / aspect bois"),
]


class ProductColorManager:
    """Manages available product colors and finishes in the Master Data registry."""

    _schema_checked = False

    def __init__(self, db_instance):
        self.db = db_instance
        self._ensure_table()

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

    def _ensure_table(self) -> None:
        """Ensures the Product_Colors table exists and contains standard default colors."""
        if ProductColorManager._schema_checked:
            return
        try:
            conn = self._get_connection()
            cursor = conn.cursor(dictionary=True) if hasattr(conn, "cursor") else None
            if not cursor:
                return
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Product_Colors (
                    Color_ID INT AUTO_INCREMENT PRIMARY KEY,
                    Color_Name VARCHAR(100) NOT NULL UNIQUE,
                    Color_Code VARCHAR(20) DEFAULT '#FFFFFF',
                    Description VARCHAR(255) NULL,
                    Is_Active BOOLEAN DEFAULT TRUE,
                    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("SELECT COUNT(*) AS cnt FROM Product_Colors")
            row = cursor.fetchone()
            count = row.get("cnt") if isinstance(row, dict) else (row[0] if row else 0)

            if count == 0:
                for name, hex_code, desc in DEFAULT_PRODUCT_COLORS:
                    try:
                        cursor.execute(
                            """
                            INSERT IGNORE INTO Product_Colors (Color_Name, Color_Code, Description, Is_Active)
                            VALUES (%s, %s, %s, TRUE)
                            """,
                            (name, hex_code, desc),
                        )
                    except Exception:
                        pass

            if hasattr(conn, "commit"):
                conn.commit()
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()
            ProductColorManager._schema_checked = True
        except Exception as err:
            logger.debug(f"Product_Colors schema check skipped or deferred: {err}")

    def get_all_colors(self, search: Optional[str] = None, active_only: bool = False) -> List[Dict[str, Any]]:
        """Returns all registered product colors with optional search and active status filters."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            clauses = ["1=1"]
            params: List[Any] = []

            if active_only:
                clauses.append("Is_Active = TRUE")

            if search and search.strip():
                clauses.append("(Color_Name LIKE %s OR Description LIKE %s OR Color_Code LIKE %s)")
                term = f"%{search.strip()}%"
                params.extend([term, term, term])

            query = f"""
                SELECT Color_ID, Color_Name, COALESCE(Color_Code, '#FFFFFF') AS Color_Code,
                       COALESCE(Description, '') AS Description, Is_Active, Created_At
                FROM Product_Colors
                WHERE {' AND '.join(clauses)}
                ORDER BY Is_Active DESC, Color_Name ASC
            """
            cursor.execute(query, tuple(params) if params else None)
            rows = cursor.fetchall() or []
            return rows
        except Exception as err:
            logger.error(f"Error fetching product colors: {err}")
            # Fallback in-memory list
            items = []
            s_low = (search or "").strip().lower()
            for idx, (name, code, desc) in enumerate(DEFAULT_PRODUCT_COLORS, start=1):
                if s_low and not (s_low in name.lower() or s_low in desc.lower() or s_low in code.lower()):
                    continue
                items.append({
                    "Color_ID": idx,
                    "Color_Name": name,
                    "Color_Code": code,
                    "Description": desc,
                    "Is_Active": True,
                })
            return items
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def get_active_color_names(self) -> List[str]:
        """Returns list of active color names for populating dropdown combos."""
        colors = self.get_all_colors(active_only=True)
        return [str(c["Color_Name"]) for c in colors if c.get("Color_Name")]

    def add_color(self, color_name: str, color_code: str = "#FFFFFF", description: str = "") -> Dict[str, Any]:
        """Adds a new color finish to the registry."""
        name = (color_name or "").strip()
        if not name:
            raise ValueError("Le nom de la couleur est obligatoire.")

        code = (color_code or "#FFFFFF").strip().upper()
        if not code.startswith("#"):
            code = f"#{code}"

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                INSERT INTO Product_Colors (Color_Name, Color_Code, Description, Is_Active)
                VALUES (%s, %s, %s, TRUE)
                """,
                (name, code, description.strip() if description else None),
            )
            color_id = cursor.lastrowid
            if hasattr(conn, "commit"):
                conn.commit()
            return {
                "success": True,
                "color_id": color_id,
                "color_name": name,
                "color_code": code,
                "description": description.strip(),
            }
        except mysql.connector.IntegrityError:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise ValueError(f"La couleur '{name}' existe déjà dans le référentiel.")
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error adding color '{name}': {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def update_color(
        self,
        color_id: int,
        color_name: str,
        color_code: str = "#FFFFFF",
        description: str = "",
        is_active: bool = True,
    ) -> bool:
        """Updates an existing color finish."""
        name = (color_name or "").strip()
        if not name:
            raise ValueError("Le nom de la couleur est obligatoire.")

        code = (color_code or "#FFFFFF").strip().upper()
        if not code.startswith("#"):
            code = f"#{code}"

        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute(
                """
                UPDATE Product_Colors
                SET Color_Name = %s, Color_Code = %s, Description = %s, Is_Active = %s
                WHERE Color_ID = %s
                """,
                (name, code, description.strip() if description else None, bool(is_active), int(color_id)),
            )
            if hasattr(conn, "commit"):
                conn.commit()
            return cursor.rowcount > 0
        except mysql.connector.IntegrityError:
            if hasattr(conn, "rollback"):
                conn.rollback()
            raise ValueError(f"La couleur '{name}' existe déjà dans le référentiel.")
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error updating color {color_id}: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()

    def delete_color(self, color_id: int) -> bool:
        """Deletes a color finish or marks it inactive if referenced."""
        conn = self._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            if hasattr(conn, "start_transaction"):
                conn.start_transaction()

            cursor.execute("DELETE FROM Product_Colors WHERE Color_ID = %s", (int(color_id),))
            if hasattr(conn, "commit"):
                conn.commit()
            return cursor.rowcount > 0
        except mysql.connector.Error:
            # If foreign key or referenced, soft delete by disabling
            if hasattr(conn, "rollback"):
                conn.rollback()
            return self.update_color(color_id, color_name="Inactif", is_active=False)
        except Exception as err:
            if hasattr(conn, "rollback"):
                conn.rollback()
            logger.error(f"Error deleting color {color_id}: {err}")
            raise
        finally:
            cursor.close()
            if hasattr(self.db, "get_raw_connection"):
                conn.close()
