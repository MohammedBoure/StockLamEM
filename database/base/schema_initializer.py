# database/schema_initializer.py

import mysql.connector
import logging
import json
import hashlib

# =============================================================================
# 1. PERMISSIONS DEFINITION (Granular Control)
# =============================================================================
_ALL_PERMISSIONS = [
    # --- التنقل الرئيسي (Sidebar Modules) ---
    "nav_dashboard",
    "nav_data",
    "nav_procurement",
    "nav_inventory",
    "nav_services",
    "nav_history",
    "nav_inventaire",
    "nav_settings",
    "nav_market",
    "nav_sales",
    "nav_pos",
    "nav_wholesale",
    "nav_sales_history",
    "nav_debts",
    "debts_management:view",
    "debts_management:settle",

    # --- تبويبات لوحة التحكم (Dashboard) ---
    "tab_dash_overview",
    "tab_dash_reception",
    "tab_dash_consumption",
    "tab_dash_valuation",
    "tab_dash_waste",
    "tab_dash_alerts",

    # --- تبويبات البيانات الأساسية (Master Data) ---
    "tab_data_products",
    "tab_data_families",
    "tab_data_units",
    "tab_data_suppliers",
    "tab_data_manufacturers",
    "tab_data_partners",
    "tab_data_automates",
    "tab_data_locations",
    "tab_data_waste_reasons",
    "tab_clients",
    "tab_data_caisses",
    "tab_data_colors",
    "nav_clients",

    # --- تبويبات المشتريات (Procurement) ---
    "tab_proc_po",
    "tab_proc_reception",
    "tab_proc_credit",
    "tab_proc_reclamation",

    # --- تبويبات المخزن (Inventory) ---
    "tab_inv_list",
    "tab_inv_dispatch",
    "tab_inv_financials",

    # --- تبويبات السجل والتتبع (History) ---
    "tab_inv_history",

    # --- تبويبات المبيعات والتجارة (Sales, Wholesale & Invoices) ---
    "tab_wholesale_sales",
    "tab_sales_invoices",
    "tab_sales_returns",
    "tab_sales_payments",

    # --- تبويبات الإعدادات (Settings) ---
    "tab_config",
    "tab_auto_backup",
    "tab_set_db",
    "tab_set_printer",
    "tab_set_system",
    "tab_system_logs",
    "tab_set_pdf",
    "tab_users",

    # --- إجراءات المنتجات والمشتريات ---
    "act_add_product",
    "act_edit_product",
    "act_delete_product",
    "act_create_po",
    "act_approve_po",
    "act_receive_po",

    # --- إجراءات الجرد والمخزن ---
    "act_inventory_create",
    "act_inventory_scan",
    "act_inventory_apply",
    "act_inventory_cancel",
    "act_inventory_export",
    "act_manage_stamps",

    # --- إجراءات مبيعات الجملة (Wholesale B2B Actions) ---
    "act_wholesale_create",
    "act_wholesale_validate",
    "act_wholesale_credit_override",
    "act_wholesale_pdf_export",

    # --- إجراءات نقطة البيع والكاشير (POS Actions) ---
    "act_create_sale",
    "act_validate_sale",
    "act_return_sale",
    "act_pos_open_session",
    "act_pos_close_session",
    "act_sale_without_client",
    "act_cancel_sale",
    "act_edit_sale",
    "act_edit_closed_cash_session",
    "act_pos_multi_payment",
    "act_pos_credit_sale",
    "act_pos_hold_sale",
    "act_pos_resume_sale",
    "act_pos_quote",
    "act_pos_discount",
    "act_pos_price_override",
    "act_pos_return",
    "act_pos_return_without_invoice",
    "act_pos_refund",
    "act_pos_exchange",
    "act_pos_cash_movement",
    "act_pos_reopen_session",
    "act_pos_view_profit",
    "act_pos_manage_promotions",
    "act_pos_manage_loyalty",
    "act_pos_reprint_invoice",
    "act_pos_audit",
    "nav_appliance_workflow",
    "tab_desk_order",
    "tab_desk_caisse",
    "tab_desk_dispatch",
    "nav_sav",
    "tab_sav_all",
    "tab_sav_received",
    "tab_sav_atelier",
    "tab_sav_returned",
    "tab_sav_closed",
    "tab_sav_irreparable",
    "tab_desk_sav",
    "tab_serial_registry",
    "CATALOG_VIEW_PRICING",
    "CATALOG_VIEW_COST_MARGIN",
    "SALES_ORDER_CREATE",
    "SALES_PRICE_OVERRIDE",
    "CASH_SESSION_OPEN_CLOSE",
    "PAYMENT_VALIDATE_CASH",
    "VERSEMENT_DEPOSIT_CREATE",
    "CREDIT_INITIATE",
    "CREDIT_ADMIN_AUTHORIZE",
    "LIVRAISON_VALIDATE_ADVANCE",
    "LIVRAISON_SETTLE_REMAINING",
    "DISPATCH_QUEUE_VIEW",
    "SERIAL_SCAN_DISPATCH",
    "RETURN_INTAKE_INSPECT",
    "WALLET_ISSUE_CREDIT",
    "SAV_TICKET_CREATE",
    "SAV_TECH_DISPATCH",
    "SAV_DIAGNOSTIC_RETURN",
    "SAV_RESTITUTION_CLOSE",
    "SAV_COMPENSATION_AUTO",
    "STOCK_SCRAP_DECOMMISSION"
]
# =============================================================================
# 2. SCHEMA QUERIES (With Inline Alters)
# =============================================================================
SCHEMA_QUERIES = [

    """CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'root';""",
    """GRANT ALL PRIVILEGES ON Lab_Inventory_Enterprise_DB.* TO 'root'@'%';""",
    """FLUSH PRIVILEGES;""",

    # --- 1. Users & Auth ---
    """CREATE TABLE IF NOT EXISTS Users (
        User_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Username VARCHAR(50) NOT NULL UNIQUE,
        Password VARCHAR(255) NOT NULL,
        Role ENUM('Admin', 'Manager', 'Technician', 'Viewer') DEFAULT 'Technician',
        Full_Name VARCHAR(100),
        Is_Active BOOLEAN DEFAULT TRUE,
        Permissions JSON DEFAULT NULL,
        Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    # [Migration]: Ensure Permissions column exists for older DBs
    """ALTER TABLE Users ADD COLUMN Permissions JSON DEFAULT NULL;""",

    # --- 1.1 Company/PDF Settings ---
    """CREATE TABLE IF NOT EXISTS Company_Settings (
        Settings_ID INT PRIMARY KEY DEFAULT 1,
        Settings_Data JSON,
        Banner_Image LONGBLOB
    );""",

    """CREATE TABLE IF NOT EXISTS Company_Stamps (
        Stamp_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Stamp_Name VARCHAR(150) NOT NULL,
        Image_Data LONGBLOB NOT NULL,
        Position_X_CM DECIMAL(7,2) NOT NULL DEFAULT 13.00,
        Position_Y_CM DECIMAL(7,2) NOT NULL DEFAULT 22.00,
        Width_CM DECIMAL(7,2) NOT NULL DEFAULT 4.00,
        Height_CM DECIMAL(7,2) NOT NULL DEFAULT 4.00,
        Is_Active BOOLEAN NOT NULL DEFAULT FALSE,
        Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        Updated_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );""",

    # --- 2. Master Data ---
    """CREATE TABLE IF NOT EXISTS Location_Types (
        Type_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Type_Name VARCHAR(50) NOT NULL UNIQUE,
        Description VARCHAR(150) NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Product_Families (
        Family_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Family_Name VARCHAR(100) NOT NULL UNIQUE,
        Deleted_At DATETIME NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Packaging_Units (
        Unit_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Unit_Name VARCHAR(50) NOT NULL UNIQUE,
        Description VARCHAR(150) NULL,
        Deleted_At DATETIME NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Manufacturers (
        Manuf_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Manuf_Name VARCHAR(150) NOT NULL UNIQUE,
        Country_of_Origin VARCHAR(100) NULL,
        Website VARCHAR(200) NULL,
        Deleted_At DATETIME NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Suppliers (
        Supplier_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Supplier_Name VARCHAR(255) NOT NULL UNIQUE,
        Contact_Person VARCHAR(150) NULL,
        Phone VARCHAR(50) NULL,
        Email VARCHAR(150) NULL,
        Website VARCHAR(200) NULL,
        Address_Line1 VARCHAR(255) NULL,
        Address_Line2 VARCHAR(255) NULL,
        City VARCHAR(100) NULL,
        Postal_Code VARCHAR(20) NULL,
        Tax_ID_Number VARCHAR(100) NULL,
        Commercial_Reg_No VARCHAR(100) NULL,
        Bank_Name VARCHAR(150) NULL,
        Bank_Account_IBAN VARCHAR(150) NULL,
        Deleted_At DATETIME NULL
    );""",

    """CREATE TABLE IF NOT EXISTS External_Partners (
        Partner_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Partner_Name VARCHAR(255) NOT NULL UNIQUE,
        Partner_Type ENUM('Laboratory', 'Doctor', 'Hospital', 'Other') DEFAULT 'Laboratory',
        Agrement_Number VARCHAR(100) NULL,
        Contact_Person VARCHAR(150) NULL,
        Phone VARCHAR(50) NULL,
        Email VARCHAR(150) NULL,
        Website VARCHAR(200) NULL,
        Address_Line1 VARCHAR(255) NULL,
        Address_Line2 VARCHAR(255) NULL,
        City VARCHAR(100) NULL,
        Postal_Code VARCHAR(20) NULL,
        Tax_ID_Number VARCHAR(100) NULL,
        Commercial_Reg_No VARCHAR(100) NULL,
        Bank_Name VARCHAR(150) NULL,
        Bank_Account_IBAN VARCHAR(150) NULL,
        Deleted_At DATETIME NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Locations (
        Location_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Location_Name VARCHAR(100) NOT NULL,
        Parent_Location_ID INT UNSIGNED NULL,
        Type_ID INT UNSIGNED NULL,
        Temperature_Zone ENUM('Room Temp', 'Refrigerated 2-8', 'Frozen -20', 'Deep Freeze -80') NOT NULL DEFAULT 'Room Temp',
        Deleted_At DATETIME NULL,
        FOREIGN KEY (Parent_Location_ID) REFERENCES Locations(Location_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Type_ID) REFERENCES Location_Types(Type_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """INSERT IGNORE INTO Location_Types (Type_Name) VALUES
       ('Bâtiment'), ('Étage'), ('Salle'), ('Réfrigérateur'), ('Congélateur'), ('Étagère'), ('Boîte');""",

    """CREATE TABLE IF NOT EXISTS Automates (
        Automate_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Automate_Name VARCHAR(150) NOT NULL UNIQUE,
        Model_Number VARCHAR(100) NULL,
        Serial_Number VARCHAR(100) NULL,
        Date_of_Purchase DATE NULL,
        Location_ID INT UNSIGNED NULL,
        Deleted_At DATETIME NULL,
        FOREIGN KEY (Location_ID) REFERENCES Locations(Location_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS Waste_Reasons (
        Reason_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Reason_Name VARCHAR(100) NOT NULL,
        Is_Active BOOLEAN DEFAULT TRUE
    );""",

    """CREATE TABLE IF NOT EXISTS Products_Master (
        Product_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Product_Name VARCHAR(255) NOT NULL,
        Family_ID INT UNSIGNED NOT NULL DEFAULT 1,
        Barcode VARCHAR(100) NULL,
        Ordering_Unit VARCHAR(50) NOT NULL DEFAULT 'Carton',
        Stock_Unit VARCHAR(50) NOT NULL DEFAULT 'Box/Kit',
        Stock_Qty_Per_Order_Unit INT UNSIGNED NOT NULL DEFAULT 1,
        Usage_Unit VARCHAR(50) NOT NULL DEFAULT 'Test',
        Usage_Qty_Per_Stock_Unit DECIMAL(10, 2) NOT NULL DEFAULT 1.00,
        Manuf_Cat_No VARCHAR(100) NULL,
        Minimum_Stock_Level INT UNSIGNED NOT NULL DEFAULT 5,
        Alert_Before_Expiry_Days INT UNSIGNED DEFAULT 30,
        Open_Vial_Stability_Days INT UNSIGNED NULL,
        Manuf_ID INT UNSIGNED NOT NULL,
        Preferred_Automate_ID INT UNSIGNED NULL,
        Storage_Temp_Req VARCHAR(50) NULL,
        Is_Billable BOOLEAN DEFAULT FALSE,
        Show_In_Alerts BOOLEAN DEFAULT FALSE,
        Default_Selling_Price_HT DECIMAL(15, 2) DEFAULT 0.00,
        Selling_Price_HT_2 DECIMAL(15, 2) DEFAULT 0.00,
        Selling_Price_HT_3 DECIMAL(15, 2) DEFAULT 0.00,
        Selling_Price_HT_4 DECIMAL(15, 2) DEFAULT 0.00,
        Selling_TVA_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Deleted_At DATETIME NULL,
        FOREIGN KEY (Family_ID) REFERENCES Product_Families(Family_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Manuf_ID) REFERENCES Manufacturers(Manuf_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Preferred_Automate_ID) REFERENCES Automates(Automate_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """ALTER TABLE Products_Master ADD COLUMN Default_Selling_Price_HT DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Products_Master ADD COLUMN Selling_Price_HT_2 DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Products_Master ADD COLUMN Selling_Price_HT_3 DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Products_Master ADD COLUMN Selling_Price_HT_4 DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Products_Master ADD COLUMN Selling_TVA_Percent DECIMAL(5, 2) DEFAULT 0.00;""",
    """ALTER TABLE Products_Master ADD COLUMN Show_In_Alerts BOOLEAN NULL DEFAULT NULL;""",
    """UPDATE Products_Master SET Show_In_Alerts = TRUE WHERE Show_In_Alerts IS NULL;""",
    """ALTER TABLE Products_Master MODIFY COLUMN Show_In_Alerts BOOLEAN NOT NULL DEFAULT FALSE;""",

    """CREATE TABLE IF NOT EXISTS Product_Documents (
        Doc_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Product_ID INT UNSIGNED NOT NULL,
        Doc_Type ENUM('COA', 'MSDS', 'Package Insert', 'Contract') NOT NULL,
        File_Path VARCHAR(255) NOT NULL,
        Upload_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON DELETE CASCADE ON UPDATE CASCADE
    );""",

    # --- 3. Procurement Cycle ---
    """
    CREATE TABLE IF NOT EXISTS Purchase_Orders (
        PO_ID BIGINT UNSIGNED PRIMARY KEY,
        Supplier_ID INT UNSIGNED NOT NULL,
        Order_Date DATE NOT NULL,
        Expected_Delivery_Date DATE,
        Status ENUM('Draft', 'Sent', 'Partial_Received', 'Completed', 'Cancelled') DEFAULT 'Draft',
        Notes TEXT,
        Created_By INT UNSIGNED,
        Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
        Total_Tax_Amount DECIMAL(15, 2) DEFAULT 0.00,
        Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Supplier_Invoice_Ref VARCHAR(150) NULL,
        Reception_Date DATETIME NULL,
        Updated_At DATETIME NULL,
        Deleted_At DATETIME NULL,
        FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
    );
    """,

    # [Migration]: Purchase_Orders
    """ALTER TABLE Purchase_Orders ADD COLUMN Supplier_Invoice_Ref VARCHAR(150) NULL;""",
    """ALTER TABLE Purchase_Orders ADD COLUMN Deleted_At DATETIME NULL;""",

    """CREATE TABLE IF NOT EXISTS PO_Details (
        ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        PO_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Qty_Ordered INT UNSIGNED NOT NULL,
        Ordering_Unit VARCHAR(50) DEFAULT NULL,
        Unit_Price_HT DECIMAL(10, 2) DEFAULT 0.00,
        Discount_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Tax_Rate_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Line_Total_HT DECIMAL(15, 2) DEFAULT 0.00,
        Line_Total_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Item_Note VARCHAR(255) NULL,
        FOREIGN KEY (PO_ID) REFERENCES Purchase_Orders(PO_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE
    );""",

    # --- 4. Inventory & Reception ---
    """
    CREATE TABLE IF NOT EXISTS Reception_Log (
        BR_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        PO_ID BIGINT UNSIGNED DEFAULT NULL,
        Supplier_Invoice_Ref VARCHAR(150) NULL,
        Supplier_BL_Ref VARCHAR(150) NULL,
        Document_Type ENUM('Facture', 'BL', 'Both', 'None') NOT NULL DEFAULT 'Facture',
        Reception_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        Supplier_ID INT UNSIGNED DEFAULT NULL,
        Invoice_Total_HT DECIMAL(15, 2) DEFAULT 0.00,
        Invoice_Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
        Invoice_Total_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Status ENUM('Completed', 'Variance Detected', 'Pending Audit') DEFAULT 'Completed',
        Variance_Notes TEXT NULL,
        Receiver_User_ID INT UNSIGNED DEFAULT NULL,
        Received_By INT UNSIGNED DEFAULT NULL,
        Total_Discount DECIMAL(15, 2) DEFAULT 0.00,
        UNIQUE KEY uq_supplier_bl (Supplier_ID, Supplier_BL_Ref),
        UNIQUE KEY uq_supplier_invoice (Supplier_ID, Supplier_Invoice_Ref),
        FOREIGN KEY (PO_ID) REFERENCES Purchase_Orders(PO_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Received_By) REFERENCES Users(User_ID)
    );
    """,

    # [Migration]: Reception_Log
    """ALTER TABLE Reception_Log ADD COLUMN Variance_Notes TEXT NULL;""",
    """ALTER TABLE Reception_Log ADD COLUMN Total_Discount DECIMAL(15,2) DEFAULT 0.00;""",

    """CREATE TABLE IF NOT EXISTS Reception_Details (
        Detail_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        BR_ID INT UNSIGNED NOT NULL,
        PO_Detail_ID INT UNSIGNED NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Qty_Ordered INT UNSIGNED NULL,
        Qty_Received INT UNSIGNED NOT NULL,
        Unit_Price_Received DECIMAL(10, 2) DEFAULT 0.00,
        Line_Note TEXT NULL,
        FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (PO_Detail_ID) REFERENCES PO_Details(ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS Inventory_Batches (
        Batch_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        Internal_Barcode VARCHAR(50) NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Location_ID INT UNSIGNED NOT NULL,
        Lot_Number VARCHAR(100) NOT NULL,
        Expiry_Date DATE NULL,
        Quantity_Initial INT UNSIGNED NOT NULL,
        Quantity_Current INT UNSIGNED NOT NULL,
        Unit_Price_Received DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        Tax_Rate_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Discount_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Selling_Price_HT DECIMAL(15, 2) DEFAULT 0.00,
        Selling_Price_HT_2 DECIMAL(15, 2) DEFAULT 0.00,
        Selling_Price_HT_3 DECIMAL(15, 2) DEFAULT 0.00,
        Selling_Price_HT_4 DECIMAL(15, 2) DEFAULT 0.00,
        Selling_TVA_Percent DECIMAL(5, 2) DEFAULT 0.00,
        PO_ID BIGINT UNSIGNED NULL,
        BR_ID INT UNSIGNED NULL,
        Status ENUM('Available', 'Quarantined', 'Expired', 'Depleted') DEFAULT 'Available',
        Reception_Note TEXT NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (Batch_ID),
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Location_ID) REFERENCES Locations(Location_ID) ON UPDATE CASCADE,
        FOREIGN KEY (PO_ID) REFERENCES Purchase_Orders(PO_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """ALTER TABLE Inventory_Batches DROP INDEX uq_inventory_internal_barcode;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Selling_Price_HT DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Selling_Price_HT_2 DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Selling_Price_HT_3 DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Selling_Price_HT_4 DECIMAL(15, 2) DEFAULT 0.00;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Selling_TVA_Percent DECIMAL(5, 2) DEFAULT 0.00;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN External_Barcode VARCHAR(100) NULL;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Supplier_ID INT UNSIGNED NULL;""",
    """ALTER TABLE Inventory_Batches ADD CONSTRAINT fk_batch_supplier FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON DELETE SET NULL ON UPDATE CASCADE;""",
    """ALTER TABLE Products_Master ADD COLUMN POS_Priority_Group INT NULL DEFAULT NULL;""",
    """ALTER TABLE Products_Master ADD INDEX idx_pos_priority_group (POS_Priority_Group);""",

    """CREATE TABLE IF NOT EXISTS Price_Change_Log (
        Log_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NULL,
        Lot_Number VARCHAR(100) NULL,
        Price_Type VARCHAR(50) NOT NULL,
        Old_Price DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        New_Price DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Reason VARCHAR(255) NULL,
        Changed_By_User_ID INT UNSIGNED NULL,
        Changed_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_product_price (Product_ID),
        INDEX idx_batch_price (Batch_ID),
        INDEX idx_changed_at (Changed_At),
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Changed_By_User_ID) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    """CREATE TABLE IF NOT EXISTS Inventory_Count_Sessions (
        Session_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_Name VARCHAR(150) NOT NULL,
        Scope_Type ENUM('ALL', 'LOCATION', 'FAMILY', 'PRODUCT') NOT NULL DEFAULT 'ALL',
        Scope_ID BIGINT UNSIGNED NULL,
        Status ENUM('Draft', 'Counting', 'Review', 'Applied', 'Cancelled') NOT NULL DEFAULT 'Draft',
        Started_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Completed_At DATETIME NULL,
        Applied_At DATETIME NULL,
        Created_By INT UNSIGNED NULL,
        Applied_By INT UNSIGNED NULL,
        Notes TEXT NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Applied_By) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """ALTER TABLE Inventory_Count_Sessions ADD COLUMN Applied_At DATETIME NULL;""",
    """ALTER TABLE Inventory_Count_Sessions ADD COLUMN Applied_By INT UNSIGNED NULL;""",

    """CREATE TABLE IF NOT EXISTS Inventory_Count_Lines (
        Line_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_ID BIGINT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NULL,
        Product_ID INT UNSIGNED NULL,
        Internal_Barcode VARCHAR(100) NULL,
        Program_Qty_Snapshot DECIMAL(15, 2) NOT NULL DEFAULT 0,
        Counted_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0,
        Difference_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0,
        Line_Status ENUM('OK', 'SHORT', 'EXCESS', 'NOT_COUNTED', 'UNKNOWN') NOT NULL DEFAULT 'NOT_COUNTED',
        Last_Scanned_At DATETIME NULL,
        Comment TEXT NULL,
        FOREIGN KEY (Session_ID) REFERENCES Inventory_Count_Sessions(Session_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        UNIQUE KEY uq_inventory_count_line_batch (Session_ID, Batch_ID)
    );""",

    """CREATE TABLE IF NOT EXISTS Inventory_Count_Scans (
        Scan_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_ID BIGINT UNSIGNED NOT NULL,
        Line_ID BIGINT UNSIGNED NULL,
        Scanned_Barcode VARCHAR(100) NOT NULL,
        Qty DECIMAL(15, 2) NOT NULL DEFAULT 1,
        Scan_Status ENUM('MATCHED', 'UNKNOWN', 'IGNORED') NOT NULL DEFAULT 'MATCHED',
        Scanned_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Scanned_By INT UNSIGNED NULL,
        FOREIGN KEY (Session_ID) REFERENCES Inventory_Count_Sessions(Session_ID) ON DELETE CASCADE ON UPDATE CASCADE,
        FOREIGN KEY (Line_ID) REFERENCES Inventory_Count_Lines(Line_ID) ON DELETE SET NULL ON UPDATE CASCADE,
        FOREIGN KEY (Scanned_By) REFERENCES Users(User_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS Active_Containers (
        Container_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Parent_Batch_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Date_Opened DATETIME DEFAULT CURRENT_TIMESTAMP,
        Open_Expiration_Date DATE NOT NULL,
        Initial_Usage_Qty DECIMAL(10, 2) NOT NULL,
        Remaining_Usage_Qty DECIMAL(10, 2) NOT NULL,
        Current_Location_ID INT UNSIGNED NULL,
        Status ENUM('In_Use', 'Empty', 'Discarded') DEFAULT 'In_Use',
        FOREIGN KEY (Parent_Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Current_Location_ID) REFERENCES Locations(Location_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    # --- 5. External & Transfers ---
    """CREATE TABLE IF NOT EXISTS External_Transfer_Log (
        Transfer_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Transaction_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        Partner_ID INT UNSIGNED NOT NULL,
        Transfer_Type ENUM('Outbound', 'Return', 'Free', 'Paid') DEFAULT 'Outbound',
        Total_Amount DECIMAL(15, 2) DEFAULT 0.00,
        Status ENUM('Draft', 'Completed', 'Cancelled') DEFAULT 'Draft',
        Notes TEXT,
        Ref_Transfer_ID INT UNSIGNED NULL DEFAULT NULL,
        Created_By INT UNSIGNED,
        FOREIGN KEY (Partner_ID) REFERENCES External_Partners(Partner_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Ref_Transfer_ID) REFERENCES External_Transfer_Log(Transfer_ID) ON DELETE SET NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
    );""",
    """ALTER TABLE External_Transfer_Log MODIFY COLUMN Transfer_Type ENUM('Outbound', 'Return', 'Free', 'Paid') DEFAULT 'Outbound';""",
    """ALTER TABLE External_Transfer_Log ADD COLUMN Ref_Transfer_ID INT UNSIGNED NULL DEFAULT NULL;""",
    """ALTER TABLE External_Transfer_Log ADD CONSTRAINT fk_ref_transfer FOREIGN KEY (Ref_Transfer_ID) REFERENCES External_Transfer_Log(Transfer_ID) ON DELETE SET NULL;""",
    """ALTER TABLE external_partners MODIFY COLUMN Partner_Type ENUM('Laboratory', 'Doctor', 'Hospital', 'Pharmacy', 'CareRoom', 'Clinic', 'Other');""",

    """CREATE TABLE IF NOT EXISTS External_Transfer_Details (
        Detail_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Transfer_ID INT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NOT NULL,
        Qty_Transferred DECIMAL(10, 2) NOT NULL,
        Unit_Price DECIMAL(10, 2) DEFAULT 0.00,
        Line_Total DECIMAL(15, 2) DEFAULT 0.00,
        Line_Note TEXT NULL,
        FOREIGN KEY (Transfer_ID) REFERENCES External_Transfer_Log(Transfer_ID) ON DELETE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID)
    );""",

    # --- 6. Sales & Clients ---
    """CREATE TABLE IF NOT EXISTS Clients (
        Client_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Client_Code VARCHAR(32) NULL UNIQUE,
        Client_Name VARCHAR(255) NOT NULL UNIQUE,
        Contact_Person VARCHAR(150) NULL,
        Phone VARCHAR(50) NULL,
        Email VARCHAR(150) NULL,
        Address VARCHAR(255) NULL,
        City VARCHAR(100) NULL,
        Tax_ID_Number VARCHAR(100) NULL,
        Commercial_Reg_No VARCHAR(100) NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Deleted_At DATETIME NULL
    );""",

    """CREATE TABLE IF NOT EXISTS POS_Terminals (
        Terminal_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Terminal_Code VARCHAR(100) NOT NULL UNIQUE,
        Terminal_Name VARCHAR(150) NOT NULL,
        Is_Active BOOLEAN DEFAULT TRUE,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP
    );""",

    """CREATE TABLE IF NOT EXISTS POS_Cash_Sessions (
        Cash_Session_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Session_No VARCHAR(100) NOT NULL UNIQUE,
        Terminal_ID INT UNSIGNED NOT NULL,
        Opened_By INT UNSIGNED NULL,
        Closed_By INT UNSIGNED NULL,
        Status ENUM('Open', 'Closed', 'Cancelled') NOT NULL DEFAULT 'Open',
        Opening_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Expected_Cash DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Expected_Card DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Expected_Transfer DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Counted_Cash DECIMAL(15, 2) NULL,
        Cash_Difference DECIMAL(15, 2) NULL,
        Notes TEXT NULL,
        Opened_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Closed_At DATETIME NULL,
        Next_Invoice_Seq INT UNSIGNED NOT NULL DEFAULT 1,
        FOREIGN KEY (Terminal_ID) REFERENCES POS_Terminals(Terminal_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Opened_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
        FOREIGN KEY (Closed_By) REFERENCES Users(User_ID) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Sales_Invoice_Sequences (
        Year_Num INT UNSIGNED NOT NULL PRIMARY KEY,
        Next_Seq INT UNSIGNED NOT NULL DEFAULT 1,
        Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );""",

    """CREATE TABLE IF NOT EXISTS Sales_Invoices (
        Invoice_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Invoice_No VARCHAR(100) NULL,
        Client_ID INT UNSIGNED NULL,
        Invoice_Date DATE NOT NULL,
        Status ENUM('Draft', 'Validated', 'Paid', 'Cancelled') DEFAULT 'Draft',
        Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
        Total_Discount DECIMAL(15, 2) DEFAULT 0.00,
        Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
        Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Notes TEXT NULL,
        Created_By INT UNSIGNED,
        Terminal_ID INT UNSIGNED NULL,
        Cash_Session_ID BIGINT UNSIGNED NULL,
        Sale_UUID VARCHAR(64) NULL,
        Payment_Method ENUM('Cash', 'Card', 'Transfer', 'Versement', 'Other') DEFAULT 'Cash',
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Updated_At DATETIME NULL,
        FOREIGN KEY (Client_ID) REFERENCES Clients(Client_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
        FOREIGN KEY (Terminal_ID) REFERENCES POS_Terminals(Terminal_ID) ON DELETE SET NULL,
        FOREIGN KEY (Cash_Session_ID) REFERENCES POS_Cash_Sessions(Cash_Session_ID) ON DELETE SET NULL
    );""",

    """ALTER TABLE Sales_Invoices MODIFY COLUMN Client_ID INT UNSIGNED NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Invoice_No VARCHAR(100) NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Terminal_ID INT UNSIGNED NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Cash_Session_ID BIGINT UNSIGNED NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Sale_UUID VARCHAR(64) NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Payment_Method ENUM('Cash', 'Card', 'Transfer', 'Versement', 'Other') DEFAULT 'Cash';""",
    """ALTER TABLE Sales_Invoices ADD CONSTRAINT fk_sales_terminal FOREIGN KEY (Terminal_ID) REFERENCES POS_Terminals(Terminal_ID) ON DELETE SET NULL;""",
    """ALTER TABLE Sales_Invoices ADD CONSTRAINT fk_sales_cash_session FOREIGN KEY (Cash_Session_ID) REFERENCES POS_Cash_Sessions(Cash_Session_ID) ON DELETE SET NULL;""",

    """CREATE TABLE IF NOT EXISTS Sales_Details (
        Detail_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Invoice_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NOT NULL,
        Qty_Sold DECIMAL(10, 2) NOT NULL,
        Unit_Price_HT DECIMAL(15, 2) NOT NULL,
        Discount_Percent DECIMAL(5, 2) DEFAULT 0.00,
        TVA_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Line_Total_HT DECIMAL(15, 2) NOT NULL,
        Line_Total_TTC DECIMAL(15, 2) NOT NULL,
        FOREIGN KEY (Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE
    );""",

    """CREATE TABLE IF NOT EXISTS Client_Payments (
        Payment_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Client_ID INT UNSIGNED NOT NULL,
        Invoice_ID BIGINT UNSIGNED NULL,
        Payment_Date DATE NOT NULL,
        Amount DECIMAL(15, 2) NOT NULL,
        Payment_Method ENUM('Espèce', 'Chèque', 'Virement', 'Versement', 'Autre') DEFAULT 'Espèce',
        Reference VARCHAR(100) NULL,
        Notes TEXT NULL,
        Created_By INT UNSIGNED NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (Client_ID) REFERENCES Clients(Client_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE SET NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Client_Credit_Notes (
        Credit_Note_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Client_ID INT UNSIGNED NOT NULL,
        Invoice_ID BIGINT UNSIGNED NULL,
        Return_Date DATE NOT NULL,
        Status ENUM('Draft', 'Validated') DEFAULT 'Draft',
        Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
        Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
        Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Notes TEXT NULL,
        Created_By INT UNSIGNED NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (Client_ID) REFERENCES Clients(Client_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Invoice_ID) REFERENCES Sales_Invoices(Invoice_ID) ON DELETE SET NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Client_Credit_Note_Details (
        Detail_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Credit_Note_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NULL,
        Qty_Returned DECIMAL(10, 2) NOT NULL,
        Unit_Price_HT DECIMAL(15, 2) NOT NULL,
        TVA_Percent DECIMAL(5, 2) DEFAULT 0.00,
        Line_Total_HT DECIMAL(15, 2) NOT NULL,
        Line_Total_TTC DECIMAL(15, 2) NOT NULL,
        FOREIGN KEY (Credit_Note_ID) REFERENCES Client_Credit_Notes(Credit_Note_ID) ON DELETE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL
    );""",

    # --- 7. Audit Trail ---
    """CREATE TABLE IF NOT EXISTS Stock_Movement_Log (
        Movement_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Transaction_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        User_ID INT UNSIGNED DEFAULT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NULL,
        Container_ID BIGINT UNSIGNED NULL,
        Movement_Type ENUM(
            'Purchase_Receive', 'Open_Pack', 'Patient_Test', 'QC_Run',
            'Calibration', 'Adjustment', 'Waste', 'Transfer',
            'External_Transfer', 'Transfer_Return', 'Return_To_Supplier', 'Sale', 'Sale_Return'
        ) NOT NULL,
        Reason_ID INT UNSIGNED NULL,
        Qty_Change DECIMAL(10, 2) NOT NULL,
        Unit_Used VARCHAR(50) NOT NULL,
        Notes TEXT NULL,
        Stock_After DECIMAL(15, 2) DEFAULT NULL,
        FOREIGN KEY (User_ID) REFERENCES Users(User_ID),
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Container_ID) REFERENCES Active_Containers(Container_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Reason_ID) REFERENCES Waste_Reasons(Reason_ID) ON DELETE SET NULL ON UPDATE CASCADE
    );""",

    """ALTER TABLE Stock_Movement_Log MODIFY COLUMN Movement_Type ENUM('Purchase_Receive', 'Open_Pack', 'Patient_Test', 'QC_Run', 'Calibration', 'Adjustment', 'Waste', 'Transfer', 'External_Transfer', 'Transfer_Return', 'Return_To_Supplier', 'Sale', 'Sale_Return') NOT NULL;""",

    """CREATE TABLE IF NOT EXISTS Supplier_Credit_Notes (
        Credit_Note_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Credit_Note_Ref VARCHAR(150) NOT NULL,
        Supplier_ID INT UNSIGNED NOT NULL,
        BR_ID INT UNSIGNED NULL,
        Credit_Date DATE NOT NULL,
        Type ENUM('Return_Goods', 'Price_Correction', 'Billing_Error') DEFAULT 'Return_Goods',
        Status ENUM('Draft', 'Validated', 'Used') DEFAULT 'Draft',
        Total_Amount_HT DECIMAL(15, 2) DEFAULT 0.00,
        Total_TVA DECIMAL(15, 2) DEFAULT 0.00,
        Total_Amount_TTC DECIMAL(15, 2) DEFAULT 0.00,
        Notes TEXT NULL,
        Created_By INT UNSIGNED NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
        FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
    );""",

    """CREATE TABLE IF NOT EXISTS Credit_Note_Details (
        Detail_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Credit_Note_ID INT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NULL,
        Lot_Number VARCHAR(100) NULL,
        Expiry_Date DATE NULL,
        Qty_Returned DECIMAL(10, 2) DEFAULT 0.00,
        Unit_Price DECIMAL(10, 2) NOT NULL,
        Line_Total DECIMAL(15, 2) NOT NULL,
        FOREIGN KEY (Credit_Note_ID) REFERENCES Supplier_Credit_Notes(Credit_Note_ID) ON DELETE CASCADE,
        FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID),
        FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Supplier_Payments (
        Payment_ID INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        Supplier_ID INT UNSIGNED NOT NULL,
        Payment_Date DATE NOT NULL,
        Amount DECIMAL(15, 2) NOT NULL,
        Payment_Method ENUM('Espèce', 'Chèque', 'Virement', 'Versement', 'Autre') DEFAULT 'Espèce',
        Reference VARCHAR(100) NULL,
        Notes TEXT NULL,
        Created_By INT UNSIGNED NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (Supplier_ID) REFERENCES Suppliers(Supplier_ID) ON UPDATE CASCADE,
        FOREIGN KEY (Created_By) REFERENCES Users(User_ID)
    );""",

    # [Migration]: Supplier_Payments
    """ALTER TABLE Supplier_Payments ADD COLUMN BR_ID INT UNSIGNED NULL;""",
    """ALTER TABLE Supplier_Payments ADD CONSTRAINT fk_payment_br FOREIGN KEY (BR_ID) REFERENCES Reception_Log(BR_ID) ON DELETE SET NULL;""",

    """CREATE TABLE IF NOT EXISTS SystemLogs (
        id INT PRIMARY KEY AUTO_INCREMENT,
        user_id INT UNSIGNED,
        log_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        module VARCHAR(50),
        action VARCHAR(100),
        details TEXT,
        ip_address VARCHAR(50),
        FOREIGN KEY (user_id) REFERENCES Users(User_ID) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Print_Templates (
        id INT PRIMARY KEY AUTO_INCREMENT,
        template_type VARCHAR(50) NOT NULL,
        name VARCHAR(100) NOT NULL,
        settings_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY idx_type_name (template_type, name)
    );""",

    # [Migration]: Expand Barcode columns for multiple barcodes support
    """ALTER TABLE Products_Master MODIFY COLUMN Barcode VARCHAR(255) NULL;""",
    """ALTER TABLE Inventory_Batches MODIFY COLUMN External_Barcode VARCHAR(255) NULL;""",

    # [Migration]: Wholesale & Retail Architecture Schema Enhancements
    """ALTER TABLE Locations ADD COLUMN Visibility ENUM('Private', 'Public') NOT NULL DEFAULT 'Private';""",
    """ALTER TABLE Locations ADD COLUMN Allow_POS_Sales BOOLEAN NOT NULL DEFAULT FALSE;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Parent_Batch_ID BIGINT UNSIGNED NULL;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Batch_Type ENUM('Standard_Bulk', 'Extracted_Retail') NOT NULL DEFAULT 'Standard_Bulk';""",
    """ALTER TABLE Inventory_Batches ADD CONSTRAINT fk_batch_parent_batch FOREIGN KEY (Parent_Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL ON UPDATE CASCADE;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Sale_Type ENUM('Retail_POS', 'Wholesale') NOT NULL DEFAULT 'Retail_POS';""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Due_Date DATE NULL;""",
    """ALTER TABLE Clients ADD COLUMN Price_Tier ENUM('Prix_1', 'Prix_2', 'Prix_3', 'Prix_4') NOT NULL DEFAULT 'Prix_1';""",
    """ALTER TABLE Clients ADD COLUMN Credit_Limit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Clients ADD COLUMN Current_Debt DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Clients ADD COLUMN Client_Code VARCHAR(32) NULL UNIQUE;""",
    """ALTER TABLE Products_Master ADD COLUMN Brand_Mark VARCHAR(100) NULL;""",
    """ALTER TABLE Products_Master ADD COLUMN Category_Name VARCHAR(100) NULL;""",
    """ALTER TABLE Products_Master ADD COLUMN Color_Finish VARCHAR(64) NULL;""",
    """ALTER TABLE Products_Master ADD COLUMN Requires_Serial_Tracking BOOLEAN NOT NULL DEFAULT TRUE;""",
    """ALTER TABLE Products_Master ADD COLUMN Warranty_Months INT UNSIGNED NOT NULL DEFAULT 24;""",
    """ALTER TABLE Products_Master ADD COLUMN Energy_Efficiency_Class VARCHAR(16) NULL DEFAULT 'A+';""",
    """ALTER TABLE Products_Master ADD COLUMN Electrical_Power_Watts INT NULL;""",
    """ALTER TABLE Products_Master ADD COLUMN Dimensions_HxWxD_CM VARCHAR(50) NULL;""",
    """ALTER TABLE Products_Master ADD COLUMN Extensible_Attributes JSON NULL;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Theoretical_Reserved_Qty INT NOT NULL DEFAULT 0;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Freight_Customs_Allocation DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Inventory_Batches ADD COLUMN Supplier_Warranty_Months INT UNSIGNED NOT NULL DEFAULT 24;""",
    """CREATE TABLE IF NOT EXISTS Product_Serials (
        Serial_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Product_ID INT UNSIGNED NOT NULL,
        Batch_ID BIGINT UNSIGNED NOT NULL,
        Serial_Number VARCHAR(128) NOT NULL,
        Barcode_Serial_Composite VARCHAR(160) NOT NULL UNIQUE,
        IMEI_MAC_Identifier VARCHAR(64) NULL,
        Status ENUM('IN_STOCK', 'RESERVED', 'DISPATCHED', 'RETURNED', 'IN_SAV', 'SCRAPPED') NOT NULL DEFAULT 'IN_STOCK',
        Current_Location_ID INT UNSIGNED NULL,
        Customer_Warranty_Start DATE NULL,
        Customer_Warranty_End DATE NULL,
        Original_Sales_Invoice_ID BIGINT UNSIGNED NULL,
        Original_Client_ID INT UNSIGNED NULL,
        Last_Inspected_At DATETIME NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        CONSTRAINT uq_prod_serial UNIQUE (Product_ID, Serial_Number),
        CONSTRAINT fk_serial_prod FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
        CONSTRAINT fk_serial_batch FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Product_Serial_History (
        History_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Serial_ID BIGINT UNSIGNED NOT NULL,
        Previous_Status ENUM('IN_STOCK', 'RESERVED', 'DISPATCHED', 'RETURNED', 'IN_SAV', 'SCRAPPED') NULL,
        New_Status ENUM('IN_STOCK', 'RESERVED', 'DISPATCHED', 'RETURNED', 'IN_SAV', 'SCRAPPED') NOT NULL,
        Voucher_Type ENUM('RECEPTION', 'ORDER_RESERVATION', 'BON_SORTIE', 'BON_RETOUR', 'BON_REPARATION', 'SAV_TECH_DISPATCH', 'SAV_RESTITUTION', 'SCRAP_VOUCHER') NOT NULL,
        Voucher_ID BIGINT UNSIGNED NOT NULL,
        From_Location_ID INT UNSIGNED NULL,
        To_Location_ID INT UNSIGNED NULL,
        Changed_By_User_ID INT UNSIGNED NOT NULL,
        Change_Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        Action_Notes VARCHAR(255) NULL,
        CONSTRAINT fk_hist_serial FOREIGN KEY (Serial_ID) REFERENCES Product_Serials(Serial_ID) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Sales_Orders_Theoretical (
        Order_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Order_Number VARCHAR(64) NOT NULL UNIQUE,
        Client_ID INT UNSIGNED NOT NULL,
        Order_Desk_User_ID INT UNSIGNED NOT NULL,
        Scanner_Session_ID VARCHAR(64) NULL,
        Order_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        Bond_Type ENUM('BON_C', 'BON_CREDIT', 'BON_LIVRAISON') NOT NULL DEFAULT 'BON_C',
        Total_Amount_HT DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Total_Amount_TTC DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Status ENUM(
            'DRAFT',
            'CONFIRMED_PENDING_PAYMENT',
            'PAID_PENDING_DISPATCH',
            'APPROVED_CREDIT_PENDING_DISPATCH',
            'APPROVED_LIVRAISON_PENDING_DISPATCH',
            'PARTIALLY_DISPATCHED',
            'DISPATCHED_PENDING_COD',
            'COMPLETED',
            'CANCELLED'
        ) NOT NULL DEFAULT 'CONFIRMED_PENDING_PAYMENT',
        Payment_Method_Requested ENUM('CASH', 'CREDIT', 'LIVRAISON_COD', 'CARD', 'WALLET_AVOIR', 'MIXED') NOT NULL DEFAULT 'CASH',
        Delivery_Address VARCHAR(255) NULL,
        Delivery_Phone VARCHAR(50) NULL,
        Delivery_Notes VARCHAR(255) NULL,
        Cancellation_Reason VARCHAR(255) NULL,
        Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Sales_Order_Lines_Theoretical (
        Line_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Order_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Preferred_Batch_ID BIGINT UNSIGNED NULL,
        Requested_Color VARCHAR(64) NULL,
        Quantity_Ordered INT NOT NULL,
        Quantity_Dispatched INT NOT NULL DEFAULT 0,
        Unit_Price_HT DECIMAL(15, 2) NOT NULL,
        Tax_Rate DECIMAL(5, 2) DEFAULT 19.00,
        Unit_Price_TTC DECIMAL(15, 2) NOT NULL,
        Line_Total_TTC DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        CONSTRAINT fk_sol_order FOREIGN KEY (Order_ID) REFERENCES Sales_Orders_Theoretical(Order_ID) ON DELETE CASCADE,
        CONSTRAINT fk_sol_prod FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Order_ID BIGINT UNSIGNED NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Bond_Settlement_Type ENUM('BON_C_CASH', 'BON_CREDIT', 'BON_LIVRAISON', 'BON_WALLET_AVOIR', 'BON_MIXED') NULL;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Amount_Paid_Cash DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Amount_Paid_Card DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Amount_Paid_Wallet DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Amount_Remaining_Credit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;""",
    """ALTER TABLE Sales_Invoices ADD COLUMN Delivery_Status ENUM('NONE', 'PENDING_DISPATCH', 'OUT_FOR_DELIVERY', 'DELIVERED_PAID') NOT NULL DEFAULT 'NONE';""",
    """CREATE TABLE IF NOT EXISTS Sales_Invoices_Credit_Approvals (
        Approval_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Invoice_ID BIGINT UNSIGNED NOT NULL UNIQUE,
        Order_ID BIGINT UNSIGNED NULL,
        Client_ID INT UNSIGNED NOT NULL,
        Admin_User_ID INT UNSIGNED NOT NULL,
        Authorization_Code_Hash VARCHAR(255) NOT NULL,
        Client_Prior_Debt DECIMAL(15, 2) NOT NULL,
        Client_Credit_Limit DECIMAL(15, 2) NOT NULL,
        Approved_Credit_Amount DECIMAL(15, 2) NOT NULL,
        Downpayment_Amount DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Approval_Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        Admin_Notes TEXT NOT NULL,
        Terminal_IP VARCHAR(45) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Client_Payment_Schedules (
        Schedule_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Invoice_ID BIGINT UNSIGNED NOT NULL,
        Client_ID INT UNSIGNED NOT NULL,
        Installment_Number INT NOT NULL,
        Due_Date DATE NOT NULL,
        Amount_Due DECIMAL(15, 2) NOT NULL,
        Amount_Paid DECIMAL(15, 2) DEFAULT 0.00,
        Status ENUM('PENDING', 'PARTIAL', 'PAID', 'OVERDUE') DEFAULT 'PENDING',
        Settled_Date DATE NULL,
        Receipt_Voucher_Ref VARCHAR(64) NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Delivery_Exit_Bonds (
        Exit_Bond_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Exit_Bond_Number VARCHAR(64) NOT NULL UNIQUE,
        Order_ID BIGINT UNSIGNED NOT NULL,
        Invoice_ID BIGINT UNSIGNED NOT NULL,
        Storekeeper_User_ID INT UNSIGNED NOT NULL,
        Exit_Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        Security_Gate_Pass_Barcode VARCHAR(64) NOT NULL UNIQUE,
        Security_Officer_Verified BOOLEAN DEFAULT FALSE,
        Security_Verification_Timestamp DATETIME NULL,
        Exit_Status ENUM('SCANNING_IN_PROGRESS', 'VALIDATED_EXIT', 'CANCELLED') NOT NULL DEFAULT 'SCANNING_IN_PROGRESS',
        Logistics_Notes TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Delivery_Exit_Serials (
        Exit_Serial_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Exit_Bond_ID BIGINT UNSIGNED NOT NULL,
        Order_Line_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Serial_ID BIGINT UNSIGNED NOT NULL,
        Scanned_Barcode VARCHAR(150) NOT NULL,
        Scanned_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        Scanned_By_User_ID INT UNSIGNED NOT NULL,
        CONSTRAINT fk_des_bond FOREIGN KEY (Exit_Bond_ID) REFERENCES Delivery_Exit_Bonds(Exit_Bond_ID) ON DELETE CASCADE,
        CONSTRAINT fk_des_serial FOREIGN KEY (Serial_ID) REFERENCES Product_Serials(Serial_ID),
        CONSTRAINT uq_bond_serial UNIQUE (Exit_Bond_ID, Serial_ID)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Client_Wallets (
        Wallet_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Client_ID INT UNSIGNED NOT NULL UNIQUE,
        Current_Balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Real_Deposit_Balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Virtual_Credit_Balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Total_Lifetime_Credited DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Total_Lifetime_Debited DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Wallet_Status ENUM('ACTIVE', 'FROZEN', 'CLOSED') DEFAULT 'ACTIVE',
        Last_Transaction_At DATETIME NULL,
        Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Client_Wallet_Transactions (
        Transaction_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Wallet_ID INT UNSIGNED NOT NULL,
        Client_ID INT UNSIGNED NOT NULL,
        Transaction_Type ENUM(
            'REAL_CASH_VERSEMENT',
            'RETURN_VIRTUAL_CREDIT',
            'SAV_IRREPARABLE_COMPENSATION',
            'SALES_PURCHASE_DEBIT',
            'ADMIN_ADJUSTMENT',
            'CASH_DISBURSEMENT_REFUND'
        ) NOT NULL,
        Amount DECIMAL(15, 2) NOT NULL,
        Balance_Before DECIMAL(15, 2) NOT NULL,
        Balance_After DECIMAL(15, 2) NOT NULL,
        Source_Document_Type ENUM('VERSEMENT_CAISSE', 'BON_RETOUR', 'SAV_TICKET', 'SALES_INVOICE', 'MANUAL_OVERRIDE') NOT NULL,
        Source_Document_ID BIGINT UNSIGNED NOT NULL,
        Authorized_By_User_ID INT UNSIGNED NOT NULL,
        Affects_Physical_Caisse BOOLEAN NOT NULL DEFAULT FALSE,
        Cash_Session_ID BIGINT UNSIGNED NULL,
        Transaction_Notes VARCHAR(255) NULL,
        Created_At DATETIME DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT fk_cwt_wallet FOREIGN KEY (Wallet_ID) REFERENCES Client_Wallets(Wallet_ID)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Return_Bonds (
        Return_Bond_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Return_Bond_Number VARCHAR(64) NOT NULL UNIQUE,
        Original_Invoice_ID BIGINT UNSIGNED NOT NULL,
        Client_ID INT UNSIGNED NOT NULL,
        Received_By_User_ID INT UNSIGNED NOT NULL,
        Return_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        Return_Reason VARCHAR(255) NOT NULL,
        Total_Return_Value DECIMAL(15, 2) NOT NULL,
        Wallet_Credit_Transaction_ID BIGINT UNSIGNED NULL,
        Return_Status ENUM('PENDING_INSPECTION', 'APPROVED_VIRTUAL_CREDITED', 'REJECTED') DEFAULT 'PENDING_INSPECTION'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Return_Bond_Serials (
        Return_Detail_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Return_Bond_ID BIGINT UNSIGNED NOT NULL,
        Serial_ID BIGINT UNSIGNED NOT NULL,
        Inspection_Condition ENUM('LIKE_NEW_RESTOCK', 'MINOR_BLEMISH_RESTOCK', 'DEFECTIVE_NEEDS_SAV', 'SCRAP_TOTAL_LOSS') NOT NULL,
        Unit_Credit_Value DECIMAL(15, 2) NOT NULL,
        Target_Batch_ID BIGINT UNSIGNED NULL,
        CONSTRAINT fk_rbs_bond FOREIGN KEY (Return_Bond_ID) REFERENCES Return_Bonds(Return_Bond_ID) ON DELETE CASCADE,
        CONSTRAINT fk_rbs_serial FOREIGN KEY (Serial_ID) REFERENCES Product_Serials(Serial_ID)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS SAV_Technicians (
        Technician_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Tech_Code VARCHAR(32) NOT NULL UNIQUE,
        Full_Name VARCHAR(100) NOT NULL,
        Affiliation_Type ENUM('INTERNAL_WORKSHOP', 'BRAND_AUTHORIZED_CENTER', 'EXTERNAL_CONTRACTOR') NOT NULL,
        Organization_Name VARCHAR(150) DEFAULT 'Atelier SAV Interne',
        Phone_Number VARCHAR(50) NULL,
        Specialty_Categories VARCHAR(255) NULL,
        Is_Active BOOLEAN DEFAULT TRUE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS SAV_Tickets (
        SAV_Ticket_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Ticket_Number VARCHAR(64) NOT NULL UNIQUE,
        Bon_Reparation_Barcode VARCHAR(64) NOT NULL UNIQUE,
        Serial_ID BIGINT UNSIGNED NOT NULL,
        Product_ID INT UNSIGNED NOT NULL,
        Client_ID INT UNSIGNED NOT NULL,
        Original_Invoice_ID BIGINT UNSIGNED NULL,
        Reception_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
        Received_By_User_ID INT UNSIGNED NOT NULL,
        Customer_Stated_Symptom TEXT NOT NULL,
        Cosmetic_Condition_Notes TEXT NOT NULL,
        Accessories_Included TEXT NULL,
        Is_Under_Warranty BOOLEAN NOT NULL DEFAULT TRUE,
        Current_Stage ENUM('SAV_RECEIVED', 'SAV_SENT_TO_TECH', 'SAV_RETURNED_FROM_TECH', 'SAV_CLOSED_DELIVERED') NOT NULL DEFAULT 'SAV_RECEIVED',
        Resolution_Status ENUM('PENDING_EVALUATION', 'REPAIRED', 'IRREPARABLE', 'CLIENT_REFUSED_ESTIMATE') NOT NULL DEFAULT 'PENDING_EVALUATION',
        Assigned_Technician_ID INT UNSIGNED NULL,
        Sent_To_Tech_At DATETIME NULL,
        Returned_From_Tech_At DATETIME NULL,
        Diagnostic_Summary TEXT NULL,
        Parts_Total_Cost DECIMAL(15, 2) DEFAULT 0.00,
        Labor_Fee DECIMAL(15, 2) DEFAULT 0.00,
        Customer_Charge_Total DECIMAL(15, 2) DEFAULT 0.00,
        Irreparable_Wallet_Transaction_ID BIGINT UNSIGNED NULL,
        Delivered_To_Client_Date DATETIME NULL,
        Delivery_Acknowledgment_Signature VARCHAR(255) NULL,
        CONSTRAINT fk_sav_serial FOREIGN KEY (Serial_ID) REFERENCES Product_Serials(Serial_ID),
        CONSTRAINT fk_sav_prod FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS SAV_Ticket_History (
        Event_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        SAV_Ticket_ID BIGINT UNSIGNED NOT NULL,
        From_Stage ENUM('SAV_RECEIVED', 'SAV_SENT_TO_TECH', 'SAV_RETURNED_FROM_TECH', 'SAV_CLOSED_DELIVERED') NULL,
        To_Stage ENUM('SAV_RECEIVED', 'SAV_SENT_TO_TECH', 'SAV_RETURNED_FROM_TECH', 'SAV_CLOSED_DELIVERED') NOT NULL,
        Action_Performed_By_User_ID INT UNSIGNED NOT NULL,
        Event_Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        Stage_Notes TEXT NULL,
        CONSTRAINT fk_sth_ticket FOREIGN KEY (SAV_Ticket_ID) REFERENCES SAV_Tickets(SAV_Ticket_ID) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS SAV_Ticket_Parts (
        Part_Entry_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        SAV_Ticket_ID BIGINT UNSIGNED NOT NULL,
        Part_Code VARCHAR(64) NOT NULL,
        Part_Description VARCHAR(255) NOT NULL,
        Quantity_Used INT NOT NULL DEFAULT 1,
        Unit_Cost_Price DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Unit_Billed_Price DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
        Is_Covered_By_Warranty BOOLEAN NOT NULL DEFAULT TRUE,
        CONSTRAINT fk_stp_ticket FOREIGN KEY (SAV_Ticket_ID) REFERENCES SAV_Tickets(SAV_Ticket_ID) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",
    """CREATE TABLE IF NOT EXISTS Workstation_Scanner_Bindings (
        Binding_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        Workstation_Name VARCHAR(64) NOT NULL,
        Scanner_Device_ID VARCHAR(190) NOT NULL UNIQUE,
        Scanner_Label VARCHAR(100) NOT NULL,
        Target_Desk_Type ENUM('ORDER_DESK', 'CAISSE_DESK', 'DISPATCH_DESK', 'SAV_DESK') NOT NULL DEFAULT 'ORDER_DESK',
        Target_Session_Key VARCHAR(64) NOT NULL,
        Assigned_User_ID INT UNSIGNED NULL,
        Is_Active BOOLEAN NOT NULL DEFAULT TRUE,
        Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"""
]

INDEX_QUERIES = [
    "CREATE INDEX idx_product_barcode ON Products_Master(Barcode);",
    "CREATE INDEX idx_batch_expiry ON Inventory_Batches(Expiry_Date);",
    "CREATE INDEX idx_batch_lot ON Inventory_Batches(Lot_Number);",
    "CREATE INDEX idx_internal_barcode ON Inventory_Batches(Internal_Barcode);",
    "CREATE UNIQUE INDEX idx_barcode_location ON Inventory_Batches(Internal_Barcode, Location_ID);",
    "CREATE INDEX idx_inventory_count_session_status ON Inventory_Count_Sessions(Status);",
    "CREATE INDEX idx_inventory_count_session_started ON Inventory_Count_Sessions(Started_At);",
    "CREATE INDEX idx_inventory_count_line_session_status ON Inventory_Count_Lines(Session_ID, Line_Status);",
    "CREATE INDEX idx_inventory_count_line_barcode ON Inventory_Count_Lines(Internal_Barcode);",
    "CREATE INDEX idx_inventory_count_line_batch ON Inventory_Count_Lines(Batch_ID);",
    "CREATE INDEX idx_inventory_count_scan_session_status ON Inventory_Count_Scans(Session_ID, Scan_Status);",
    "CREATE INDEX idx_inventory_count_scan_barcode ON Inventory_Count_Scans(Scanned_Barcode);",
    "CREATE INDEX idx_reception_invoice_ref ON Reception_Log(Supplier_Invoice_Ref);",
    "CREATE INDEX idx_reception_po_id ON Reception_Log(PO_ID);",
    "CREATE INDEX idx_movement_date ON Stock_Movement_Log(Transaction_Date);",
    "CREATE INDEX idx_movement_type ON Stock_Movement_Log(Movement_Type);",
    "CREATE INDEX idx_reception_details_br ON Reception_Details(BR_ID);",
    "CREATE INDEX idx_reception_details_product ON Reception_Details(Product_ID);",
    "CREATE INDEX idx_partner_name ON External_Partners(Partner_Name);",
    "CREATE INDEX idx_transfer_date ON External_Transfer_Log(Transaction_Date);",
    "CREATE INDEX idx_transfer_partner ON External_Transfer_Log(Partner_ID);",
    "CREATE UNIQUE INDEX uq_sales_invoice_no ON Sales_Invoices(Invoice_No);",
    "CREATE UNIQUE INDEX uq_sales_sale_uuid ON Sales_Invoices(Sale_UUID);",
    "CREATE INDEX idx_sales_client ON Sales_Invoices(Client_ID);",
    "CREATE INDEX idx_sales_date ON Sales_Invoices(Invoice_Date);",
    "CREATE INDEX idx_sales_terminal ON Sales_Invoices(Terminal_ID);",
    "CREATE INDEX idx_sales_cash_session ON Sales_Invoices(Cash_Session_ID);",
    "CREATE INDEX idx_sales_details_invoice ON Sales_Details(Invoice_ID);",
    "CREATE INDEX idx_sales_invoice_sequences_updated ON Sales_Invoice_Sequences(Updated_At);",
    "CREATE INDEX idx_pos_cash_terminal_status ON POS_Cash_Sessions(Terminal_ID, Status);",
    "CREATE INDEX idx_client_payments_client ON Client_Payments(Client_ID);",
    "CREATE INDEX idx_client_credit_client ON Client_Credit_Notes(Client_ID);",
    "CREATE INDEX idx_locations_visibility_pos ON Locations(Visibility, Allow_POS_Sales);",
    "CREATE INDEX idx_batch_parent_type ON Inventory_Batches(Parent_Batch_ID, Batch_Type);",
    "CREATE INDEX idx_sales_type_due_date ON Sales_Invoices(Sale_Type, Due_Date);"
]

class SchemaInitializerMixin:
    """Mixin that provides _initialize_schema() to the Database class."""

    def _create_default_admin(self, cursor):
        cursor.execute("SELECT User_ID FROM Users WHERE Username = 'admin'")
        admin_exists = cursor.fetchone()

        perms_dict = {perm: True for perm in _ALL_PERMISSIONS}
        perms_json = json.dumps(perms_dict)

        plain_pw = "admin123"

        if not admin_exists:
            logging.info("Creating default Admin account...")
            query = """
                INSERT INTO Users (Username, Password, Role, Full_Name, Permissions)
                VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, ('admin', plain_pw, 'Admin', 'Administrateur Système', perms_json))
        else:
            cursor.execute("SELECT Permissions FROM Users WHERE Username = 'admin'")
            res = cursor.fetchone()
            current_perms = {}
            if res and res[0]:
                try:
                    if isinstance(res[0], str):
                        current_perms = json.loads(res[0])
                    elif isinstance(res[0], dict):
                        current_perms = res[0]
                except Exception:
                    current_perms = {}

            updated = False
            for perm in _ALL_PERMISSIONS:
                if perm not in current_perms:
                    current_perms[perm] = True
                    updated = True

            if updated:
                cursor.execute(
                    "UPDATE Users SET Permissions = %s WHERE Username = 'admin'",
                    (json.dumps(current_perms),)
                )

    def _initialize_schema(self):
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

                logging.info("Initializing schema tables and migrations...")

                # Execute all schema creation and migration queries in one go
                for query in SCHEMA_QUERIES:
                    try:
                        cursor.execute(query)
                        while cursor.nextset():
                            pass
                    except mysql.connector.Error as err:
                        # Log but ignore errors related to ALTER TABLE if column already exists
                        # Error 1060: Duplicate column name
                        # Error 1061/1826: Duplicate key/foreign-key name.
                        # Error 1091: Key does not exist during DROP INDEX migrations.
                        if err.errno in (1060, 1061, 1091, 1826):
                            pass
                        elif err.errno == 1022:
                            logging.info(
                                "Skipped a schema constraint because existing rows "
                                "would conflict; no existing data was changed."
                            )
                        else:
                            logging.warning(f"Schema warning during query '{query[:30]}...': {err}")

                logging.info("Creating performance indexes...")
                for query in INDEX_QUERIES:
                    try:
                        cursor.execute(query)
                        while cursor.nextset():
                            pass
                    except mysql.connector.Error as err:
                        if err.errno == 1061: # Duplicate index name
                            pass
                        elif err.errno == 1022:
                            logging.info(
                                "Skipped a unique index because existing rows contain "
                                "duplicate values; no rows were deleted or rewritten."
                            )
                        else:
                            logging.warning(f"Index creation warning: {err}")

                # Create Default Admin User
                self._create_default_admin(cursor)

                cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
                logging.info("✅ Schema initialized successfully.")

        except mysql.connector.Error as err:
            logging.error(f"❌ Failed to initialize schema: {err}")
