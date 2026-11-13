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
  final TextEditingController _inputController = TextEditingController();
  final FocusNode _inputFocus = FocusNode();

  Timer? _searchDebounce;
  List<OrderSession> _sessions = const [];
  String? _selectedSessionId;
  List<OrderCatalogProduct> _searchResults = const [];

  bool _loadingSessions = false;
  bool _searching = false;
  bool _submitting = false;
  bool _cameraOpen = false;
  int _qty = 1;
  String? _feedback;
  bool _feedbackIsError = false;

  OrderSession? get _activeSession {
    if (_selectedSessionId == null) return null;
    for (final s in _sessions) {
      if (s.sessionId == _selectedSessionId) return s;
    }
    return null;
  }

  String get _actorName =>
      widget.currentUser?.fullName ?? widget.currentUser?.username ?? 'Mobile';

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
    _searchDebounce?.cancel();
    _inputController.dispose();
    _inputFocus.dispose();
    super.dispose();
  }

  void _setFeedback(String? msg, {bool isError = false}) {
    setState(() {
      _feedback = msg;
      _feedbackIsError = isError;
    });
  }

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
      });
    } catch (e) {
      if (!mounted) return;
      _setFeedback(e.toString().replaceFirst('Exception: ', ''), isError: true);
    } finally {
      if (mounted) setState(() => _loadingSessions = false);
    }
  }

  /// Création instantanée en 1 clic sans demander le client (le bureau choisit le client).
  Future<void> _quickCreateSession() async {
    if (!widget.connected) {
      _setFeedback('Connectez d’abord le téléphone au serveur PC.', isError: true);
      return;
    }
    setState(() => _submitting = true);
    try {
      final session = await widget.api.createOrderSession(
        createdBy: _actorName,
      );
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      await _refreshSessions(selectSessionId: session.sessionId);
      if (!mounted) return;
      _setFeedback('${session.label} prête — scannez ou ajoutez des produits.');
    } catch (e) {
      if (!mounted) return;
      _setFeedback(e.toString().replaceFirst('Exception: ', ''), isError: true);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    final q = value.trim();
    if (q.isEmpty) {
      setState(() => _searchResults = const []);
      return;
    }
    _searchDebounce = Timer(const Duration(milliseconds: 250), () {
      unawaited(_searchCatalog(q));
    });
  }

  Future<void> _searchCatalog(String q) async {
    if (!widget.connected || q.isEmpty) return;
    setState(() => _searching = true);
    try {
      final list = await widget.api.searchOrderCatalog(search: q, limit: 15);
      if (!mounted) return;
      setState(() => _searchResults = list);
    } catch (_) {
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  Future<void> _submitInputOrBarcode([String? raw]) async {
    final text = (raw ?? _inputController.text).trim();
    if (text.isEmpty) return;
    await _addItem(barcode: text);
  }

  Future<void> _addItem({int? productId, String? barcode}) async {
    if (!widget.connected) {
      _setFeedback('Connectez d’abord le téléphone au serveur PC.', isError: true);
      return;
    }
    String? sid = _selectedSessionId;
    if (sid == null) {
      await _quickCreateSession();
      sid = _selectedSessionId;
      if (sid == null) return;
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
      _inputController.clear();
      setState(() {
        _qty = 1;
        _searchResults = const [];
        _sessions = _sessions
            .map((s) => s.sessionId == updated.sessionId ? updated : s)
            .toList();
      });
      _setFeedback('Ajouté à ${updated.label} (${updated.itemCount} art.)');
    } catch (e) {
      if (!mounted) return;
      HapticFeedback.heavyImpact();
      _setFeedback(e.toString().replaceFirst('Exception: ', ''), isError: true);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _changeCartQty(OrderSessionItem item, int delta) async {
    final sid = _selectedSessionId;
    if (sid == null || _submitting) return;
    setState(() => _submitting = true);
    try {
      final updated = await widget.api.updateOrderSessionItemQty(
        sid,
        productId: item.productId,
        delta: delta,
        actor: _actorName,
      );
      if (!mounted) return;
      HapticFeedback.selectionClick();
      setState(() {
        _sessions = _sessions
            .map((s) => s.sessionId == updated.sessionId ? updated : s)
            .toList();
      });
    } catch (e) {
      if (!mounted) return;
      _setFeedback(e.toString().replaceFirst('Exception: ', ''), isError: true);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = _activeSession;

    return Column(
      children: [
        // 1. Barre horizontale des sessions (changement en 1 clic + création en 1 clic)
        Container(
          color: Colors.white,
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          child: Row(
            children: [
              FilledButton.icon(
                onPressed: (!widget.connected || _submitting)
                    ? null
                    : _quickCreateSession,
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF007572),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                icon: const Icon(Icons.add, size: 18),
                label: const Text(
                  'Nouvelle',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: SizedBox(
                  height: 38,
                  child: _sessions.isEmpty
                      ? Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            widget.connected
                                ? 'Aucune session — touchez + Nouvelle'
                                : 'Hors ligne',
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFF64748B),
                            ),
                          ),
                        )
                      : ListView.separated(
                          scrollDirection: Axis.horizontal,
                          itemCount: _sessions.length,
                          separatorBuilder: (_, __) => const SizedBox(width: 6),
                          itemBuilder: (_, idx) {
                            final s = _sessions[idx];
                            final selected = s.sessionId == _selectedSessionId;
                            return ChoiceChip(
                              selected: selected,
                              onSelected: (_) {
                                setState(() {
                                  _selectedSessionId = s.sessionId;
                                  _feedback = null;
                                });
                              },
                              showCheckmark: false,
                              selectedColor: const Color(0xFF007572),
                              backgroundColor: const Color(0xFFF1F5F9),
                              side: BorderSide(
                                color: selected
                                    ? const Color(0xFF007572)
                                    : const Color(0xFFCBD5E1),
                              ),
                              label: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    s.label,
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                      color: selected
                                          ? Colors.white
                                          : const Color(0xFF1E293B),
                                    ),
                                  ),
                                  const SizedBox(width: 6),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 6,
                                      vertical: 1,
                                    ),
                                    decoration: BoxDecoration(
                                      color: selected
                                          ? Colors.white.withValues(alpha: 0.25)
                                          : const Color(0xFFE2E8F0),
                                      borderRadius: BorderRadius.circular(10),
                                    ),
                                    child: Text(
                                      '${s.itemCount}',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.bold,
                                        color: selected
                                            ? Colors.white
                                            : const Color(0xFF334155),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),
              ),
              IconButton(
                onPressed: (!widget.connected || _loadingSessions)
                    ? null
                    : () => _refreshSessions(),
                icon: _loadingSessions
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.sync, size: 20),
                tooltip: 'Actualiser les sessions',
              ),
            ],
          ),
        ),
        const Divider(height: 1),

        // 2. Zone principale : Scan / Recherche rapide + Panier de la session active
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(12),
            children: [
              // Carte de scan & recherche rapide
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _inputController,
                              focusNode: _inputFocus,
                              decoration: InputDecoration(
                                hintText: 'Scanner ou chercher (Nom, Réf, Code)...',
                                isDense: true,
                                prefixIcon: const Icon(Icons.search, size: 20),
                                suffixIcon: _inputController.text.isNotEmpty
                                    ? IconButton(
                                        icon: const Icon(Icons.clear, size: 18),
                                        onPressed: () {
                                          _inputController.clear();
                                          setState(() => _searchResults = const []);
                                        },
                                      )
                                    : null,
                              ),
                              onChanged: _onSearchChanged,
                              onSubmitted: _submitInputOrBarcode,
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton.filled(
                            onPressed: () =>
                                setState(() => _cameraOpen = !_cameraOpen),
                            style: IconButton.styleFrom(
                              backgroundColor: _cameraOpen
                                  ? const Color(0xFFC0392B)
                                  : const Color(0xFF007572),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                            icon: Icon(
                              _cameraOpen ? Icons.close : Icons.qr_code_scanner,
                              color: Colors.white,
                            ),
                            tooltip: 'Scanner caméra',
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          const Text(
                            'Quantité :',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF475569),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Container(
                            decoration: BoxDecoration(
                              color: const Color(0xFFF1F5F9),
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: const Color(0xFFCBD5E1)),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                InkWell(
                                  onTap: _qty > 1
                                      ? () => setState(() => _qty--)
                                      : null,
                                  child: const Padding(
                                    padding: EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 5,
                                    ),
                                    child: Icon(Icons.remove, size: 16),
                                  ),
                                ),
                                Padding(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                  ),
                                  child: Text(
                                    '$_qty',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                    ),
                                  ),
                                ),
                                InkWell(
                                  onTap: () => setState(() => _qty++),
                                  child: const Padding(
                                    padding: EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 5,
                                    ),
                                    child: Icon(Icons.add, size: 16),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const Spacer(),
                          if (_searching)
                            const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          else if (_inputController.text.trim().isNotEmpty)
                            FilledButton.tonal(
                              onPressed: (!widget.connected || _submitting)
                                  ? null
                                  : () => _submitInputOrBarcode(),
                              child: const Text('Ajouter Code'),
                            ),
                        ],
                      ),
                      if (_cameraOpen) ...[
                        const SizedBox(height: 10),
                        SizedBox(
                          height: 190,
                          child: ScannerCameraWidget(
                            onCodeDetected: (code) {
                              setState(() => _cameraOpen = false);
                              unawaited(_addItem(barcode: code));
                            },
                            onClose: () => setState(() => _cameraOpen = false),
                          ),
                        ),
                      ],
                      if (_searchResults.isNotEmpty) ...[
                        const Divider(height: 18),
                        ..._searchResults.map(
                          (p) => ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            title: Text(
                              p.productName,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 13,
                              ),
                            ),
                            subtitle: Text(
                              'Réf: ${p.ref}  •  Dispo: ${p.availableQty}',
                              style: const TextStyle(fontSize: 11),
                            ),
                            trailing: FilledButton(
                              onPressed: _submitting
                                  ? null
                                  : () => _addItem(productId: p.productId),
                              style: FilledButton.styleFrom(
                                backgroundColor: const Color(0xFF007572),
                                visualDensity: VisualDensity.compact,
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 12,
                                ),
                              ),
                              child: const Text('+'),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),

              if (_feedback != null) ...[
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: _feedbackIsError
                        ? const Color(0xFFFEE2E2)
                        : const Color(0xFFE6F4F1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _feedbackIsError
                          ? const Color(0xFFFCA5A5)
                          : const Color(0xFF99F6E4),
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _feedbackIsError
                            ? Icons.error_outline
                            : Icons.check_circle_outline,
                        size: 16,
                        color: _feedbackIsError
                            ? const Color(0xFFB91C1C)
                            : const Color(0xFF007572),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          _feedback!,
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: _feedbackIsError
                                ? const Color(0xFFB91C1C)
                                : const Color(0xFF005A57),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],

              const SizedBox(height: 10),

              // Carte du panier de la session sélectionnée
              if (active != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Text(
                                '${active.label}  •  ${active.itemCount} article(s)',
                                style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 14,
                                  color: Color(0xFF0F172A),
                                ),
                              ),
                            ),
                            Text(
                              '${active.totalTtc.toStringAsFixed(0)} DA',
                              style: const TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 14,
                                color: Color(0xFF007572),
                              ),
                            ),
                          ],
                        ),
                        const Divider(height: 14),
                        if (active.items.isEmpty)
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 12),
                            child: Center(
                              child: Text(
                                'Session vide — scannez ou recherchez un produit.',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF94A3B8),
                                ),
                              ),
                            ),
                          )
                        else
                          ...active.items.map(
                            (it) => Padding(
                              padding: const EdgeInsets.symmetric(vertical: 4),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          it.name,
                                          style: const TextStyle(
                                            fontWeight: FontWeight.w600,
                                            fontSize: 13,
                                          ),
                                        ),
                                        Text(
                                          'Réf: ${it.ref}  •  ${it.lineTotal.toStringAsFixed(0)} DA',
                                          style: const TextStyle(
                                            fontSize: 11,
                                            color: Color(0xFF64748B),
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  IconButton(
                                    visualDensity: VisualDensity.compact,
                                    onPressed: _submitting
                                        ? null
                                        : () => _changeCartQty(it, -1),
                                    icon: Icon(
                                      it.quantity <= 1
                                          ? Icons.delete_outline
                                          : Icons.remove_circle_outline,
                                      size: 20,
                                      color: it.quantity <= 1
                                          ? const Color(0xFFDC2626)
                                          : const Color(0xFF475569),
                                    ),
                                  ),
                                  Text(
                                    '${it.quantity}',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 14,
                                    ),
                                  ),
                                  IconButton(
                                    visualDensity: VisualDensity.compact,
                                    onPressed: _submitting
                                        ? null
                                        : () => _changeCartQty(it, 1),
                                    icon: const Icon(
                                      Icons.add_circle_outline,
                                      size: 20,
                                      color: Color(0xFF007572),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
