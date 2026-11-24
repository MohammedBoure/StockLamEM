# ui/widgets/inventory/tabs_batches/_combos.py
"""
تعبئة القوائم المنسدلة: العائلات، الماركات، الأتمتة
"""


from ui.icons import get_duotone_icon


def _adjust_combo_view_width(combo):
    """توسيع قائمة العرض لتلائم أطول نص"""
    width = combo.width()
    fm    = combo.fontMetrics()
    for i in range(combo.count()):
        text_width = fm.horizontalAdvance(combo.itemText(i)) + 52
        if text_width > width:
            width = text_width
    combo.view().setMinimumWidth(width)


def populate_families(self):
    self.combo_family.clear()
    self.combo_family.addItem(get_duotone_icon("tag_family", 15), "Toutes les Familles", None)
    try:
        if hasattr(self.manager, 'families'):
            for f in self.manager.families.get_all_families():
                self.combo_family.addItem(f['Family_Name'], f['Family_ID'])
        _adjust_combo_view_width(self.combo_family)
    except Exception:
        pass


def populate_manufacturers(self):
    self.combo_manuf.clear()
    self.combo_manuf.addItem(get_duotone_icon("brand_badge", 15), "Toutes les Marques", None)
    try:
        if hasattr(self.manager, 'manufacturers'):
            for m in self.manager.manufacturers.get_all_manufacturers():
                self.combo_manuf.addItem(m['Manuf_Name'], m['Manuf_ID'])
        _adjust_combo_view_width(self.combo_manuf)
    except Exception:
        pass


def populate_automates(self):
    self.combo_automate.clear()
    self.combo_automate.addItem(get_duotone_icon("cpu_automate", 15), "Tous les Automates", None)
    try:
        if hasattr(self.manager, 'automates'):
            for a in self.manager.automates.get_all_automates():
                self.combo_automate.addItem(a['Automate_Name'], a['Automate_ID'])
        _adjust_combo_view_width(self.combo_automate)
    except Exception:
        pass


def populate_suppliers(self):
    if not hasattr(self, 'combo_supplier'):
        return
    self.combo_supplier.clear()
    self.combo_supplier.addItem(get_duotone_icon("supplier", 15), "Tous les Fournisseurs", None)
    try:
        conn = self.manager.db.get_raw_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT Supplier_ID, Supplier_Name FROM Suppliers WHERE Deleted_At IS NULL ORDER BY Supplier_Name")
        for row in cursor.fetchall():
            self.combo_supplier.addItem(row['Supplier_Name'], row['Supplier_ID'])
        conn.close()
        _adjust_combo_view_width(self.combo_supplier)
    except Exception as e:
        print(f"Error loading suppliers: {e}")


def populate_priority_groups(self):
    if not hasattr(self, 'combo_priority_group'):
        return
    curr_data = self.combo_priority_group.currentData()
    self.combo_priority_group.blockSignals(True)
    self.combo_priority_group.clear()
    self.combo_priority_group.addItem(get_duotone_icon("tag_family", 15), "Groupes Vente", None)
    self.combo_priority_group.addItem(get_duotone_icon("trophy_best", 15), "Tous Prioritaires", "ALL_PRIORITY")

    groups = set()
    if hasattr(self.manager, 'products') and hasattr(self.manager.products, 'get_assigned_pos_priority_groups'):
        try:
            groups.update(self.manager.products.get_assigned_pos_priority_groups())
        except Exception:
            pass
    for row in getattr(self, 'all_data', []):
        grp = row.get('POS_Priority_Group')
        if grp is not None:
            try:
                g_int = int(grp)
                if g_int > 0:
                    groups.add(g_int)
            except (ValueError, TypeError):
                pass

    for g in sorted(list(groups)):
        self.combo_priority_group.addItem(f"Groupe {g}", g)

    idx = self.combo_priority_group.findData(curr_data)
    if idx >= 0:
        self.combo_priority_group.setCurrentIndex(idx)
    else:
        self.combo_priority_group.setCurrentIndex(0)

    _adjust_combo_view_width(self.combo_priority_group)
    self.combo_priority_group.blockSignals(False)

