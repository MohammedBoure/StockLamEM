# stocklamEM Mobile Companion & Order Desk Scanner

Application mobile Flutter compagne pour **stocklamEM** permettant de gérer les sessions `Commandes` directement sur site (création en 1 clic sans sélection de client, changement instantané entre sessions, ajout/ajustement de produits par scan ou recherche), ainsi que le stock direct, la saisie rapide, l'inventaire physique et le pont scanner bureau.

## Modes de Fonctionnement

### 1. 🛍️ Mode Commandes (Onglet par défaut — Sessions Clients sur Serveur PC)
- Consultez toutes les sessions ouvertes dans `Bureaux -> Commandes` sur le PC serveur via une barre horizontale à changement instantané en 1 clic.
- Créez une nouvelle session en 1 clic (`+ Nouvelle`) sans bloquer sur le choix du client (le caissier/opérateur de bureau attribue le client lorsque celui-ci se présente au bureau).
- Ajoutez ou ajustez (`+` / `-` / suppression) des produits au panier de la session par scan caméra, saisie code-barres ou recherche catalogue instantanée (`order_sessions_view.dart`).

### 2. 📦 Mode Stock Direct (Dispatch sur site)
- **Recherche par Code-Barres ou Saisie Manuelle** : Scan caméra ou saisie directe du numéro de code-barres / numéro de lot.
- **Fiche Produit et Consultation des Lots** : Affichage du nom, famille, fabricant, unité et de tous les lots actifs avec leurs emplacements respectifs et dates de péremption.
- **Priorité FEFO Intelligente** : Surlignage du lot prioritaire (**⭐ RECOMMANDÉ**) selon la règle First Expired First Out.
- **Consommation Directe Sécurisée** : Sortie de stock avec alerte interactive et protection contre les infractions FEFO.
- **Transfert d'Emplacement Direct** : Changement d'emplacement avec sélection dans la liste des zones de stockage.

### 2. 📋 Mode Inventaire Physique (Comptage & Audit sur site)
- **Gestion des Sessions d'Inventaire** : Création de session avec périmètre (Tout le stock, par emplacement/frigo, ou par famille), sélection de session active et suivi d'avancement chiffré en temps réel.
- **Comptage par Code-Barres en Continu** : Scan caméra ultra-rapide avec comparaison instantanée au stock attendu (Snapshot), détection des codes inconnus, retour haptique et modes remplacement / accumulation (+1, +5, +10).
- **Contrôle & Revue des Écarts** : Filtres rapides par statut (Manquants, Excédents, Non comptés, Inconnus, Conformes), recherche instantanée et édition manuelle directe de chaque ligne.
- **Clôture & Application au Stock Réel** : Passage en revue, choix de gestion des non-comptés (garder ou mettre à zéro) et application sécurisée des ajustements en base.

### 3. ⚡ Mode Saisie Rapide (Multi-Produits)
- Saisie groupée de multiples références avec basculement Consommation / Transfert et validation en un clic.

### 5. 📱 Mode Pont Bureau (Scanner sans fil)
- Scannez les codes-barres avec la caméra du téléphone pour les transmettre instantanément dans le champ actif du logiciel bureau.

## Connexion Réseau et Découverte

- **Découverte automatique (UDP)** : L'application détecte automatiquement les ordinateurs StockLam sur le réseau local (WiFi).
- **Configuration manuelle** : Saisie possible de l'adresse IP (`http://IP_DU_PC:8787`).

## Build et Développement

```powershell
flutter pub get
flutter analyze
flutter test

# Génération APK Release universel :
flutter build apk --release

# Génération APK par architecture (optimisé < 25 Mo) :
flutter build apk --split-per-abi --obfuscate --split-debug-info=build/symbols
```
