// mobile_inventory_scanner/lib/views/order_sessions_view.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api_client.dart';
import '../models.dart';
import 'scanner_camera_widget.dart';

class OrderSessionsView extends StatefulWidget {
  const OrderSessionsView({
    super.key,
    required this.api,
    required this.connected,
    this.currentUser,
  });

  final ApiClient api;
  final bool connected;
  final AuthUser? currentUser;

  @override
  State<OrderSessionsView> createState() => _OrderSessionsViewState();
}

class _OrderSessionsViewState extends State<OrderSessionsView> {
  final TextEditingController _barcodeController = TextEditingController();
  final TextEditingController _searchController = TextEditingController();

  List<OrderSession> _sessions = const [];
  String? _selectedSessionId;
  List<OrderCatalogProduct> _catalogResults = const [];

  bool _loadingSessions = false;
  bool _loadingCatalog = false;
  bool _submitting = false;
  bool _cameraOpen = false;
  int _qty = 1;
  String? _status;

  OrderSession? get _selectedSession {
    if (_selectedSessionId == null) return null;
    for (final s in _sessions) {
      if (s.sessionId == _selectedSessionId) return s;
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    if (widget.connected) {
      unawaited(_refreshSessions());
    }
  }

  @override
  void didUpdateWidget(covariant OrderSessionsView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.connected && !oldWidget.connected) {
      unawaited(_refreshSessions());
    }
  }

  @override
  void dispose() {
    _barcodeController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  String get _actorName =>
      widget.currentUser?.fullName ?? widget.currentUser?.username ?? 'Mobile';

  Future<void> _refreshSessions({String? selectSessionId}) async {
    if (!widget.connected) return;
    setState(() => _loadingSessions = true);
    try {
      final list = await widget.api.fetchOrderSessions();
      if (!mounted) return;
      String? nextId = selectSessionId ?? _selectedSessionId;
      if (nextId == null || !list.any((s) => s.sessionId == nextId)) {
        nextId = list.isNotEmpty ? list.first.sessionId : null;
      }
      setState(() {
        _sessions = list;
        _selectedSessionId = nextId;
        _status = list.isEmpty
            ? 'Aucune session ouverte sur le poste serveur.'
            : null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _status = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loadingSessions = false);
    }
  }

  Future<void> _openCreateSessionDialog() async {
    if (!widget.connected) {
      setState(() => _status = 'Connectez d’abord le téléphone au PC serveur.');
      return;
    }

    List<OrderClient> clients = const [];
    try {
      clients = await widget.api.fetchOrderClients();
    } catch (_) {}

    if (!mounted) return;
    int selectedClientId = clients.isNotEmpty ? clients.first.clientId : 1;
    final labelCtrl = TextEditingController();
    final clientFilterCtrl = TextEditingController();

    final created = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDlgState) {
          final q = clientFilterCtrl.text.trim().toLowerCase();
          final filtered = clients.where((c) {
            if (q.isEmpty) return true;
            return c.fullName.toLowerCase().contains(q) ||
                c.phone.toLowerCase().contains(q);
          }).toList();
          if (filtered.isNotEmpty &&
              !filtered.any((c) => c.clientId == selectedClientId)) {
            selectedClientId = filtered.first.clientId;
          }

          return AlertDialog(
            title: const Text('Nouvelle Session Client'),
            content: SizedBox(
              width: double.maxFinite,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: clientFilterCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Rechercher un client',
                      prefixIcon: Icon(Icons.search),
                      isDense: true,
                    ),
                    onChanged: (_) => setDlgState(() {}),
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<int>(
                    initialValue: filtered.any((c) => c.clientId == selectedClientId)
                        ? selectedClientId
                        : null,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Client / Utilisateur',
                      isDense: true,
                    ),
                    items: filtered
                        .map(
                          (c) => DropdownMenuItem<int>(
                            value: c.clientId,
                            child: Text(
                              c.phone.isNotEmpty
                                  ? '${c.fullName} (${c.phone})'
                                  : c.fullName,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (v) {
                      if (v != null) setDlgState(() => selectedClientId = v);
                    },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: labelCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Nom de session (optionnel)',
                      hintText: 'Ex: Client Ahmed - Salle 2',
                      isDense: true,
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Annuler'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Créer'),
              ),
            ],
          );
        },
      ),
    );

    if (created != true) {
      labelCtrl.dispose();
      clientFilterCtrl.dispose();
      return;
    }

    setState(() => _submitting = true);
    try {
      final session = await widget.api.createOrderSession(
        clientId: selectedClientId,
        label: labelCtrl.text,
        createdBy: _actorName,
      );
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      setState(() {
        _status = '✅ Session « ${session.label} » créée pour ${session.clientName}.';
      });
      await _refreshSessions(selectSessionId: session.sessionId);
    } catch (e) {
      if (!mounted) return;
      setState(() => _status = '❌ ${e.toString().replaceFirst('Exception: ', '')}');
    } finally {
      labelCtrl.dispose();
      clientFilterCtrl.dispose();
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _searchCatalog([String? query]) async {
    if (!widget.connected) return;
    setState(() => _loadingCatalog = true);
    try {
      final list = await widget.api.searchOrderCatalog(
        search: query ?? _searchController.text,
        limit: 25,
      );
      if (!mounted) return;
      setState(() => _catalogResults = list);
    } catch (e) {
      if (!mounted) return;
      setState(() => _status = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _loadingCatalog = false);
    }
  }

  Future<void> _addItemToSelectedSession({
    int? productId,
    String? barcode,
  }) async {
    final sid = _selectedSessionId;
    if (sid == null) {
      setState(() => _status = 'Sélectionnez ou créez d’abord une session.');
      return;
    }
    setState(() => _submitting = true);
    try {
      final updated = await widget.api.addOrderSessionItem(
        sid,
        productId: productId,
        barcode: barcode,
        quantity: _qty,
        addedBy: _actorName,
      );
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      _barcodeController.clear();
      setState(() {
        _sessions = _sessions
            .map((s) => s.sessionId == updated.sessionId ? updated : s)
            .toList();
        _status = '✅ Produit ajouté à ${updated.label} (${updated.itemCount} art.).';
      });
    } catch (e) {
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      setState(() => _status = '❌ ${e.toString().replaceFirst('Exception: ', '')}');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final activeSession = _selectedSession;

    return ListView(
      padding: const EdgeInsets.all(14),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Icon(Icons.shopping_cart_checkout, color: Color(0xFF007572)),
                    const SizedBox(width: 8),
                    const Expanded(
                      child: Text(
                        'Sessions Commandes (Serveur PC)',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                    ),
                    IconButton(
                      onPressed: (!widget.connected || _loadingSessions)
                          ? null
                          : () => _refreshSessions(),
                      icon: const Icon(Icons.refresh),
                      tooltip: 'Actualiser les sessions',
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        initialValue: activeSession?.sessionId,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Session cible',
                          isDense: true,
                        ),
                        items: _sessions
                            .map(
                              (s) => DropdownMenuItem<String>(
                                value: s.sessionId,
                                child: Text(
                                  '${s.label} • ${s.clientName} (${s.itemCount} art.)',
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: (v) => setState(() => _selectedSessionId = v),
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton.icon(
                      onPressed: (!widget.connected || _submitting)
                          ? null
                          : _openCreateSessionDialog,
                      icon: const Icon(Icons.add, size: 18),
                      label: const Text('Nouvelle'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const Text('Quantité :', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(width: 8),
                    IconButton(
                      onPressed: _qty > 1 ? () => setState(() => _qty--) : null,
                      icon: const Icon(Icons.remove_circle_outline),
                    ),
                    Text('$_qty', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
                    IconButton(
                      onPressed: () => setState(() => _qty++),
                      icon: const Icon(Icons.add_circle_outline),
                    ),
                    const Spacer(),
                    OutlinedButton.icon(
                      onPressed: () => setState(() => _cameraOpen = !_cameraOpen),
                      icon: Icon(_cameraOpen ? Icons.close : Icons.qr_code_scanner),
                      label: Text(_cameraOpen ? 'Fermer' : 'Caméra'),
                    ),
                  ],
                ),
                if (_cameraOpen) ...[
                  const SizedBox(height: 8),
                  SizedBox(
                    height: 200,
                    child: ScannerCameraWidget(
                      onCodeDetected: (code) {
                        setState(() => _cameraOpen = false);
                        unawaited(_addItemToSelectedSession(barcode: code));
                      },
                      onClose: () => setState(() => _cameraOpen = false),
                    ),
                  ),
                ],
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _barcodeController,
                        decoration: const InputDecoration(
                          labelText: 'Code-barres / Réf',
                          isDense: true,
                          prefixIcon: Icon(Icons.qr_code_2),
                        ),
                        onSubmitted: (v) {
                          if (v.trim().isNotEmpty) {
                            unawaited(_addItemToSelectedSession(barcode: v.trim()));
                          }
                        },
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton(
                      onPressed: (!widget.connected || _submitting)
                          ? null
                          : () {
                              final bc = _barcodeController.text.trim();
                              if (bc.isNotEmpty) {
                                unawaited(_addItemToSelectedSession(barcode: bc));
                              }
                            },
                      child: const Text('Ajouter'),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _searchController,
                        decoration: const InputDecoration(
                          labelText: 'Rechercher un produit (Nom, Réf...)',
                          isDense: true,
                          prefixIcon: Icon(Icons.search),
                        ),
                        onSubmitted: (_) => unawaited(_searchCatalog()),
                      ),
                    ),
                    const SizedBox(width: 8),
                    FilledButton.tonal(
                      onPressed: (!widget.connected || _loadingCatalog)
                          ? null
                          : () => _searchCatalog(),
                      child: const Text('Chercher'),
                    ),
                  ],
                ),
                if (_catalogResults.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  ..._catalogResults.map(
                    (p) => ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(p.productName, style: const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text('Réf: ${p.ref} • Stock: ${p.availableQty} • ${p.price1.toStringAsFixed(0)} DA'),
                      trailing: IconButton(
                        icon: const Icon(Icons.add_shopping_cart, color: Color(0xFF007572)),
                        onPressed: _submitting
                            ? null
                            : () => _addItemToSelectedSession(productId: p.productId),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        if (_status != null) ...[
          const SizedBox(height: 10),
          Text(
            _status!,
            style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF007572)),
          ),
        ],
        if (activeSession != null) ...[
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Panier ${activeSession.label} (${activeSession.totalTtc.toStringAsFixed(0)} DA)',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const Divider(),
                  if (activeSession.items.isEmpty)
                    const Text('Panier vide.', style: TextStyle(color: Colors.grey))
                  else
                    ...activeSession.items.map(
                      (it) => ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        title: Text(it.name),
                        subtitle: Text('Réf: ${it.ref} • Qté: ${it.quantity}'),
                        trailing: Text(
                          '${it.lineTotal.toStringAsFixed(0)} DA',
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ],
    );
  }
}
