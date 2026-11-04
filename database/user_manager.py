# database/managers/user_manager.py

import mysql.connector
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional
from .system_logger import log_methods 

@log_methods()
class UserManager:
    """إدارة عمليات جدول المستخدمين (Users) والصلاحيات والأدوار متعددة المكاتب."""

    ROLE_PERMISSION_PRESETS = {
        "Order_Desk": {
            "nav_appliance_workflow": True,
            "tab_desk_order": True,
            "CATALOG_VIEW_PRICING": True,
            "CATALOG_VIEW_COST_MARGIN": False,
            "SALES_ORDER_CREATE": True,
            "CREDIT_INITIATE": True,
            "PAYMENT_VALIDATE_CASH": False,
            "CREDIT_ADMIN_AUTHORIZE": False,
            "SERIAL_SCAN_DISPATCH": False,
            "SAV_TICKET_CREATE": False,
        },
        "Cashier_Desk": {
            "nav_appliance_workflow": True,
            "tab_desk_caisse": True,
            "CATALOG_VIEW_PRICING": True,
            "CATALOG_VIEW_COST_MARGIN": False,
            "CASH_SESSION_OPEN_CLOSE": True,
            "PAYMENT_VALIDATE_CASH": True,
            "VERSEMENT_DEPOSIT_CREATE": True,
            "CREDIT_INITIATE": True,
            "CREDIT_ADMIN_AUTHORIZE": False,
            "LIVRAISON_VALIDATE_ADVANCE": True,
            "LIVRAISON_SETTLE_REMAINING": True,
            "WALLET_ISSUE_CREDIT": True,
            "SERIAL_SCAN_DISPATCH": False,
        },
        "Dispatch_Desk": {
            "nav_appliance_workflow": True,
            "tab_desk_dispatch": True,
            "tab_serial_registry": True,
            "CATALOG_VIEW_PRICING": True,
            "CATALOG_VIEW_COST_MARGIN": False,
            "DISPATCH_QUEUE_VIEW": True,
            "SERIAL_SCAN_DISPATCH": True,
            "RETURN_INTAKE_INSPECT": True,
            "PAYMENT_VALIDATE_CASH": False,
        },
        "SAV_Desk": {
            "nav_appliance_workflow": True,
            "tab_desk_sav": True,
            "CATALOG_VIEW_PRICING": True,
            "CATALOG_VIEW_COST_MARGIN": False,
            "RETURN_INTAKE_INSPECT": True,
            "SAV_TICKET_CREATE": True,
            "SAV_TECH_DISPATCH": True,
            "SAV_DIAGNOSTIC_RETURN": True,
            "SAV_RESTITUTION_CLOSE": True,
            "SAV_COMPENSATION_AUTO": False,
        },
        "Admin": {
            "nav_appliance_workflow": True,
            "tab_desk_order": True,
            "tab_desk_caisse": True,
            "tab_desk_dispatch": True,
            "tab_desk_sav": True,
            "tab_serial_registry": True,
            "CATALOG_VIEW_PRICING": True,
            "CATALOG_VIEW_COST_MARGIN": True,
            "SALES_ORDER_CREATE": True,
            "SALES_PRICE_OVERRIDE": True,
            "CASH_SESSION_OPEN_CLOSE": True,
            "PAYMENT_VALIDATE_CASH": True,
            "VERSEMENT_DEPOSIT_CREATE": True,
            "CREDIT_INITIATE": True,
            "CREDIT_ADMIN_AUTHORIZE": True,
            "LIVRAISON_VALIDATE_ADVANCE": True,
            "LIVRAISON_SETTLE_REMAINING": True,
            "DISPATCH_QUEUE_VIEW": True,
            "SERIAL_SCAN_DISPATCH": True,
            "RETURN_INTAKE_INSPECT": True,
            "WALLET_ISSUE_CREDIT": True,
            "SAV_TICKET_CREATE": True,
            "SAV_TECH_DISPATCH": True,
            "SAV_DIAGNOSTIC_RETURN": True,
            "SAV_RESTITUTION_CLOSE": True,
            "SAV_COMPENSATION_AUTO": True,
            "STOCK_SCRAP_DECOMMISSION": True,
        },
    }

    @classmethod
    def get_role_preset_permissions(cls, role_key: str) -> Dict[str, bool]:
        """إرجاع الصلاحيات المسبقة لدور مكتب معين (Order_Desk, Cashier_Desk, Dispatch_Desk, SAV_Desk, Admin)."""
        return dict(cls.ROLE_PERMISSION_PRESETS.get(role_key, {}))

    def __init__(self, db_instance):
        self.db = db_instance

    def authenticate(self, username, password) -> Optional[Dict]:
        """التحقق من بيانات الدخول (مقارنة النصوص العادية بدون تشفير)."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                # استخدام password كما هي للمطابقة
                query = "SELECT * FROM Users WHERE Username = %s AND Password = %s AND Is_Active = 1"
                cursor.execute(query, (username, password))
                user = cursor.fetchone()
                
                if user:
                    # تحويل نص JSON للصلاحيات إلى قاموس (Dictionary)
                    if user.get('Permissions') and isinstance(user['Permissions'], str):
                        try:
                            user['Permissions'] = json.loads(user['Permissions'])
                        except json.JSONDecodeError:
                            user['Permissions'] = {}
                    elif not user.get('Permissions'):
                        user['Permissions'] = {}

                    logging.info(f"User '{username}' logged in successfully.")
                    return user
                else:
                    logging.warning(f"Login failed: No match for '{username}' with provided password.")
                    return None
        except mysql.connector.Error as e:
            logging.error(f"Database error during authentication: {e}")
            return None

    def add_user(self, username, password, role='Technician', full_name=None, permissions=None):
        """إضافة مستخدم جديد للنظام وتخزين كلمة المرور كنص عادي."""
        if permissions is None:
            permissions = {}
            
        try:
            # تحويل قاموس الصلاحيات إلى نص JSON
            perms_json = json.dumps(permissions)

            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    INSERT INTO Users (Username, Password, Role, Full_Name, Permissions) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                # تمرير password مباشرة
                cursor.execute(query, (username, password, role, full_name, perms_json))
                user_id = cursor.lastrowid
                logging.info(f"User '{username}' created with ID {user_id}.")
                return user_id
        except mysql.connector.Error as err:
            if err.errno == 1062:
                logging.warning(f"Username '{username}' already exists.")
                return -1
            logging.error(f"Error adding user: {err}")
            return None

    def update_user(self, user_id, **kwargs):
        """تحديث بيانات المستخدم بشكل ديناميكي (الاسم، الدور، الحالة، كلمة المرور، الصلاحيات)."""
        updates = []
        params = []
        
        # الحقول المسموح بتحديثها
        allowed_fields = ['Username', 'Role', 'Full_Name', 'Is_Active', 'Password', 'Permissions']
        for key, value in kwargs.items():
            if key in allowed_fields:
                # معالجة خاصة للصلاحيات (تحويل إلى JSON)
                if key == 'Permissions':
                    if isinstance(value, dict):
                        value = json.dumps(value)

                # سيتم تمرير كلمة المرور الجديدة (إن وجدت) كما هي بدون تشفير
                updates.append(f"{key} = %s")
                params.append(value)
        
        if not updates: 
            return False
        
        params.append(user_id)
        query = f"UPDATE Users SET {', '.join(updates)} WHERE User_ID = %s"
        
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(params))
                return cursor.rowcount > 0
        except mysql.connector.Error as e:
            logging.error(f"Error updating user {user_id}: {e}")
            return False

    def get_all_users(self, include_inactive=False):
        """جلب قائمة المستخدمين لإدارة النظام مع جلب الصلاحيات."""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT User_ID, Username, Role, Full_Name, Is_Active, Permissions, Created_At FROM Users"
                if not include_inactive:
                    query += " WHERE Is_Active = TRUE"
                query += " ORDER BY Username"
                cursor.execute(query)
                users = cursor.fetchall()

                # تحويل حقل الصلاحيات من JSON String إلى Dictionary لجميع المستخدمين
                for user in users:
                    if user.get('Permissions') and isinstance(user['Permissions'], str):
                        try:
                            user['Permissions'] = json.loads(user['Permissions'])
                        except json.JSONDecodeError:
                            user['Permissions'] = {}
                    elif not user.get('Permissions'):
                        user['Permissions'] = {}

                return users
        except mysql.connector.Error as e:
            logging.error(f"Error fetching users: {e}")
            return []

    def get_user_events(self, user_id, limit=100):
        """
        جلب سجل الأحداث (العمليات) التي قام بها مستخدم معين.
        تربط بين سجل الحركات وجدول المنتجات.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT sml.*, pm.Product_Name 
                    FROM Stock_Movement_Log sml
                    JOIN Products_Master pm ON sml.Product_ID = pm.Product_ID
                    WHERE sml.User_ID = %s
                    ORDER BY sml.Transaction_Date DESC
                    LIMIT %s
                """
                cursor.execute(query, (user_id, limit))
                return cursor.fetchall()
        except mysql.connector.Error as e:
            logging.error(f"Error fetching events for user {user_id}: {e}")
            return []