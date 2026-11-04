-- ============================================================================
-- Migration: 20261104_appliance_store_workflow.sql
-- Purpose: Complete schema support for Electrical Appliance Store workflow:
--   1. Product attributes (Mark, Name, Categorie, Coloure, N° de Série) & Batches
--   2. Theoretical vs. Actual Stock Designation (Theoretical_Reserved_Qty)
--   3. 6 Bond Types (Bon C, Bon Crédit, Bon de Livraison, Versement, Bon de Sortie, Bon de Retour)
--   4. Client Wallets (Real Versement vs. Virtual Credit / Versement Virtuel)
--   5. 4-Stage SAV / Repair Lifecycle & Irreparable Virtual Compensation
--   6. Multi-Scanner / Workstation Session Profiles & Granular RBAC
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

-- 1. Enhance Products_Master with Appliance Attributes (Mark, Categorie, Coloure, Serial tracking)
ALTER TABLE Products_Master ADD COLUMN Brand_Mark VARCHAR(100) NULL;
ALTER TABLE Products_Master ADD COLUMN Category_Name VARCHAR(100) NULL;
ALTER TABLE Products_Master ADD COLUMN Color_Finish VARCHAR(64) NULL;
ALTER TABLE Products_Master ADD COLUMN Requires_Serial_Tracking BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE Products_Master ADD COLUMN Warranty_Months INT UNSIGNED NOT NULL DEFAULT 24;
ALTER TABLE Products_Master ADD COLUMN Energy_Efficiency_Class VARCHAR(16) NULL DEFAULT 'A+';
ALTER TABLE Products_Master ADD COLUMN Electrical_Power_Watts INT NULL;
ALTER TABLE Products_Master ADD COLUMN Dimensions_HxWxD_CM VARCHAR(50) NULL;
ALTER TABLE Products_Master ADD COLUMN Extensible_Attributes JSON NULL;

-- 2. Enhance Inventory_Batches for Theoretical Reservations & Landed Cost
ALTER TABLE Inventory_Batches ADD COLUMN Theoretical_Reserved_Qty INT NOT NULL DEFAULT 0;
ALTER TABLE Inventory_Batches ADD COLUMN Freight_Customs_Allocation DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE Inventory_Batches ADD COLUMN Supplier_Warranty_Months INT UNSIGNED NOT NULL DEFAULT 24;

-- 3. Enhance Clients with Current_Debt tracking if not present
ALTER TABLE Clients ADD COLUMN Current_Debt DECIMAL(15, 2) NOT NULL DEFAULT 0.00;

-- 4. Unique Serial Number Registry & Immutable Audit History
CREATE TABLE IF NOT EXISTS Product_Serials (
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
    CONSTRAINT fk_serial_batch FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON UPDATE CASCADE,
    INDEX idx_serial_status (Status),
    INDEX idx_serial_num (Serial_Number),
    INDEX idx_serial_warranty (Customer_Warranty_End)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Product_Serial_History (
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
    CONSTRAINT fk_hist_serial FOREIGN KEY (Serial_ID) REFERENCES Product_Serials(Serial_ID) ON DELETE CASCADE,
    INDEX idx_hist_serial_date (Serial_ID, Change_Timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Theoretical Orders (Order Desk - Comptoir de Vente)
CREATE TABLE IF NOT EXISTS Sales_Orders_Theoretical (
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
    Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_order_status (Status),
    INDEX idx_order_client (Client_ID),
    INDEX idx_order_bond_type (Bond_Type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Sales_Order_Lines_Theoretical (
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
    CONSTRAINT fk_sol_prod FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON UPDATE CASCADE,
    INDEX idx_sol_order (Order_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Cashier Settlement Extensions & Credit Dual-Custody Approvals
ALTER TABLE Sales_Invoices ADD COLUMN Order_ID BIGINT UNSIGNED NULL;
ALTER TABLE Sales_Invoices ADD COLUMN Bond_Settlement_Type ENUM('BON_C_CASH', 'BON_CREDIT', 'BON_LIVRAISON', 'BON_WALLET_AVOIR', 'BON_MIXED') NULL;
ALTER TABLE Sales_Invoices ADD COLUMN Amount_Paid_Cash DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE Sales_Invoices ADD COLUMN Amount_Paid_Card DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE Sales_Invoices ADD COLUMN Amount_Paid_Wallet DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE Sales_Invoices ADD COLUMN Amount_Remaining_Credit DECIMAL(15, 2) NOT NULL DEFAULT 0.00;
ALTER TABLE Sales_Invoices ADD COLUMN Delivery_Status ENUM('NONE', 'PENDING_DISPATCH', 'OUT_FOR_DELIVERY', 'DELIVERED_PAID') NOT NULL DEFAULT 'NONE';

CREATE TABLE IF NOT EXISTS Sales_Invoices_Credit_Approvals (
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
    Terminal_IP VARCHAR(45) NOT NULL,
    INDEX idx_credit_appr_client (Client_ID),
    INDEX idx_credit_appr_admin (Admin_User_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Client_Payment_Schedules (
    Schedule_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Invoice_ID BIGINT UNSIGNED NOT NULL,
    Client_ID INT UNSIGNED NOT NULL,
    Installment_Number INT NOT NULL,
    Due_Date DATE NOT NULL,
    Amount_Due DECIMAL(15, 2) NOT NULL,
    Amount_Paid DECIMAL(15, 2) DEFAULT 0.00,
    Status ENUM('PENDING', 'PARTIAL', 'PAID', 'OVERDUE') DEFAULT 'PENDING',
    Settled_Date DATE NULL,
    Receipt_Voucher_Ref VARCHAR(64) NULL,
    INDEX idx_cps_due (Client_ID, Due_Date, Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Logistical Exit & Physical Dispatch (Bon de Sortie)
CREATE TABLE IF NOT EXISTS Delivery_Exit_Bonds (
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
    Logistics_Notes TEXT NULL,
    INDEX idx_deb_order (Order_ID),
    INDEX idx_deb_gate (Security_Gate_Pass_Barcode)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Delivery_Exit_Serials (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Client Wallets (Real Versement & Virtual Credit / Bon de Retour)
CREATE TABLE IF NOT EXISTS Client_Wallets (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Client_Wallet_Transactions (
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
    CONSTRAINT fk_cwt_wallet FOREIGN KEY (Wallet_ID) REFERENCES Client_Wallets(Wallet_ID),
    INDEX idx_cwt_client_date (Client_ID, Created_At)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Return_Bonds (
    Return_Bond_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Return_Bond_Number VARCHAR(64) NOT NULL UNIQUE,
    Original_Invoice_ID BIGINT UNSIGNED NOT NULL,
    Client_ID INT UNSIGNED NOT NULL,
    Received_By_User_ID INT UNSIGNED NOT NULL,
    Return_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
    Return_Reason VARCHAR(255) NOT NULL,
    Total_Return_Value DECIMAL(15, 2) NOT NULL,
    Wallet_Credit_Transaction_ID BIGINT UNSIGNED NULL,
    Return_Status ENUM('PENDING_INSPECTION', 'APPROVED_VIRTUAL_CREDITED', 'REJECTED') DEFAULT 'PENDING_INSPECTION',
    INDEX idx_rb_inv (Original_Invoice_ID),
    INDEX idx_rb_client (Client_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Return_Bond_Serials (
    Return_Detail_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Return_Bond_ID BIGINT UNSIGNED NOT NULL,
    Serial_ID BIGINT UNSIGNED NOT NULL,
    Inspection_Condition ENUM('LIKE_NEW_RESTOCK', 'MINOR_BLEMISH_RESTOCK', 'DEFECTIVE_NEEDS_SAV', 'SCRAP_TOTAL_LOSS') NOT NULL,
    Unit_Credit_Value DECIMAL(15, 2) NOT NULL,
    Target_Batch_ID BIGINT UNSIGNED NULL,
    CONSTRAINT fk_rbs_bond FOREIGN KEY (Return_Bond_ID) REFERENCES Return_Bonds(Return_Bond_ID) ON DELETE CASCADE,
    CONSTRAINT fk_rbs_serial FOREIGN KEY (Serial_ID) REFERENCES Product_Serials(Serial_ID)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 9. After-Sales Service (SAV / 4-Stage Repair Engine)
CREATE TABLE IF NOT EXISTS SAV_Technicians (
    Technician_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Tech_Code VARCHAR(32) NOT NULL UNIQUE,
    Full_Name VARCHAR(100) NOT NULL,
    Affiliation_Type ENUM('INTERNAL_WORKSHOP', 'BRAND_AUTHORIZED_CENTER', 'EXTERNAL_CONTRACTOR') NOT NULL,
    Organization_Name VARCHAR(150) DEFAULT 'Atelier SAV Interne',
    Phone_Number VARCHAR(50) NULL,
    Specialty_Categories VARCHAR(255) NULL,
    Is_Active BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS SAV_Tickets (
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
    CONSTRAINT fk_sav_prod FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID),
    INDEX idx_sav_stage (Current_Stage),
    INDEX idx_sav_res (Resolution_Status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS SAV_Ticket_History (
    Event_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    SAV_Ticket_ID BIGINT UNSIGNED NOT NULL,
    From_Stage ENUM('SAV_RECEIVED', 'SAV_SENT_TO_TECH', 'SAV_RETURNED_FROM_TECH', 'SAV_CLOSED_DELIVERED') NULL,
    To_Stage ENUM('SAV_RECEIVED', 'SAV_SENT_TO_TECH', 'SAV_RETURNED_FROM_TECH', 'SAV_CLOSED_DELIVERED') NOT NULL,
    Action_Performed_By_User_ID INT UNSIGNED NOT NULL,
    Event_Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    Stage_Notes TEXT NULL,
    CONSTRAINT fk_sth_ticket FOREIGN KEY (SAV_Ticket_ID) REFERENCES SAV_Tickets(SAV_Ticket_ID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS SAV_Ticket_Parts (
    Part_Entry_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    SAV_Ticket_ID BIGINT UNSIGNED NOT NULL,
    Part_Code VARCHAR(64) NOT NULL,
    Part_Description VARCHAR(255) NOT NULL,
    Quantity_Used INT NOT NULL DEFAULT 1,
    Unit_Cost_Price DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    Unit_Billed_Price DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    Is_Covered_By_Warranty BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_stp_ticket FOREIGN KEY (SAV_Ticket_ID) REFERENCES SAV_Tickets(SAV_Ticket_ID) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 10. Workstation & Multi-Scanner Session Profiles
CREATE TABLE IF NOT EXISTS Workstation_Scanner_Bindings (
    Binding_ID INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    Workstation_Name VARCHAR(64) NOT NULL,
    Scanner_Device_ID VARCHAR(190) NOT NULL UNIQUE,
    Scanner_Label VARCHAR(100) NOT NULL,
    Target_Desk_Type ENUM('ORDER_DESK', 'CAISSE_DESK', 'DISPATCH_DESK', 'SAV_DESK') NOT NULL DEFAULT 'ORDER_DESK',
    Target_Session_Key VARCHAR(64) NOT NULL,
    Assigned_User_ID INT UNSIGNED NULL,
    Is_Active BOOLEAN NOT NULL DEFAULT TRUE,
    Updated_At DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
