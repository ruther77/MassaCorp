#!/bin/bash
# ============================================
# Script WireGuard PostDown
# Nettoyage des regles pare-feu
# ============================================

set -euo pipefail

WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_NETWORK="${WG_NETWORK:-10.10.0.0/24}"
ETH_INTERFACE="${ETH_INTERFACE:-eth0}"

echo "[WG PostDown] Nettoyage des regles pare-feu..."

# Supprimer regle NAT
iptables -t nat -D POSTROUTING -s ${WG_NETWORK} -o ${ETH_INTERFACE} -j MASQUERADE 2>/dev/null || true

# Supprimer regle port WireGuard
iptables -D INPUT -p udp --dport ${WG_LISTEN_PORT:-51820} -j ACCEPT 2>/dev/null || true

# Supprimer regles de routage
iptables -D FORWARD -i ${WG_INTERFACE} -o ${WG_INTERFACE} -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i ${WG_INTERFACE} -o ${ETH_INTERFACE} -j ACCEPT 2>/dev/null || true
iptables -D FORWARD -i ${ETH_INTERFACE} -o ${WG_INTERFACE} -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true

# Supprimer regles d'isolation
iptables -D INPUT -p tcp --dport 8000 -i ${ETH_INTERFACE} -j DROP 2>/dev/null || true
iptables -D INPUT -p tcp --dport 5432 -i ${ETH_INTERFACE} -j DROP 2>/dev/null || true
iptables -D INPUT -p tcp --dport 6379 -i ${ETH_INTERFACE} -j DROP 2>/dev/null || true

echo "[WG PostDown] Regles pare-feu nettoyees"
