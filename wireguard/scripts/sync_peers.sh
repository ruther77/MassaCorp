#!/bin/bash
# ============================================
# Script de synchronisation des peers WireGuard
# Synchronise les peers depuis la base de donnees
# ============================================

set -euo pipefail

WG_INTERFACE="${WG_INTERFACE:-wg0}"
DATABASE_URL="${DATABASE_URL:-postgresql://massa:jemmysev@db:5432/MassaCorp}"

echo "[WG Sync] Synchronisation des peers depuis la base de donnees..."

# Fonction pour ajouter un peer
ajouter_peer() {
    local cle_publique="$1"
    local ips_autorisees="$2"
    local cle_partagee="${3:-}"

    echo "[WG Sync] Ajout du peer: ${cle_publique:0:20}..."

    if [ -n "$cle_partagee" ]; then
        wg set ${WG_INTERFACE} peer "$cle_publique" \
            allowed-ips "$ips_autorisees" \
            preshared-key <(echo "$cle_partagee")
    else
        wg set ${WG_INTERFACE} peer "$cle_publique" \
            allowed-ips "$ips_autorisees"
    fi
}

# Fonction pour supprimer un peer
supprimer_peer() {
    local cle_publique="$1"
    echo "[WG Sync] Suppression du peer: ${cle_publique:0:20}..."
    wg set ${WG_INTERFACE} peer "$cle_publique" remove
}

# Recuperer les peers actifs depuis la DB
obtenir_peers_actifs() {
    psql "${DATABASE_URL}" -t -A -F'|' -c "
        SELECT public_key, array_to_string(allowed_ips, ',')
        FROM wg_peers
        WHERE enabled = true AND revoked_at IS NULL
    "
}

# Recuperer les peers actuellement configures
obtenir_peers_actuels() {
    wg show ${WG_INTERFACE} peers 2>/dev/null || echo ""
}

# Synchronisation principale
synchroniser_peers() {
    local peers_db=$(obtenir_peers_actifs)
    local peers_actuels=$(obtenir_peers_actuels)

    # Ajouter les nouveaux peers
    echo "$peers_db" | while IFS='|' read -r cle_publique ips_autorisees; do
        if [ -n "$cle_publique" ]; then
            if ! echo "$peers_actuels" | grep -q "$cle_publique"; then
                ajouter_peer "$cle_publique" "$ips_autorisees"
            fi
        fi
    done

    # Supprimer les peers non autorises
    echo "$peers_actuels" | while read -r cle_actuelle; do
        if [ -n "$cle_actuelle" ]; then
            if ! echo "$peers_db" | grep -q "$cle_actuelle"; then
                supprimer_peer "$cle_actuelle"
            fi
        fi
    done

    echo "[WG Sync] Synchronisation terminee"
    echo "[WG Sync] Peers actifs: $(wg show ${WG_INTERFACE} peers | wc -l)"
}

# Mettre a jour les statistiques de handshake dans la DB
mettre_a_jour_stats() {
    wg show ${WG_INTERFACE} dump | tail -n +2 | while IFS=$'\t' read -r cle_publique psk endpoint ips_autorisees dernier_handshake octets_recus octets_envoyes keepalive; do
        if [ "$dernier_handshake" != "0" ]; then
            local temps_handshake=$(date -d "@$dernier_handshake" '+%Y-%m-%d %H:%M:%S')
            psql "${DATABASE_URL}" -c "
                UPDATE wg_peers
                SET last_handshake_at = '$temps_handshake'::TIMESTAMPTZ
                WHERE public_key = '$cle_publique'
            " 2>/dev/null || true
        fi
    done
}

# Point d'entree principal
case "${1:-sync}" in
    sync)
        synchroniser_peers
        ;;
    stats)
        mettre_a_jour_stats
        ;;
    full)
        synchroniser_peers
        mettre_a_jour_stats
        ;;
    *)
        echo "Usage: $0 {sync|stats|full}"
        exit 1
        ;;
esac
