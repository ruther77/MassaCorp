#!/bin/bash
# ============================================
# Script WireGuard PostUp
# Mode isolation complete - tout le trafic via WG
# ============================================

set -euo pipefail

WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_NETWORK="${WG_NETWORK:-10.10.0.0/24}"
ETH_INTERFACE="${ETH_INTERFACE:-eth0}"

echo "[WG PostUp] Configuration du pare-feu pour isolation complete..."

# ============================================
# 1. Activer le routage IP
# ============================================
sysctl -w net.ipv4.ip_forward=1

# ============================================
# 2. NAT pour le trafic sortant (si necessaire)
# ============================================
iptables -t nat -A POSTROUTING -s ${WG_NETWORK} -o ${ETH_INTERFACE} -j MASQUERADE

# ============================================
# 3. Autoriser le trafic WireGuard
# ============================================
# Accepter les connexions WireGuard entrantes
iptables -A INPUT -p udp --dport ${WG_LISTEN_PORT:-51820} -j ACCEPT

# Autoriser les connexions etablies
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -m state --state ESTABLISHED,RELATED -j ACCEPT

# ============================================
# 4. Autoriser le trafic dans le reseau WireGuard
# ============================================
# Communication inter-peers
iptables -A FORWARD -i ${WG_INTERFACE} -o ${WG_INTERFACE} -j ACCEPT

# WG vers externe (si necessaire)
iptables -A FORWARD -i ${WG_INTERFACE} -o ${ETH_INTERFACE} -j ACCEPT
iptables -A FORWARD -i ${ETH_INTERFACE} -o ${WG_INTERFACE} -m state --state RELATED,ESTABLISHED -j ACCEPT

# ============================================
# 5. ISOLATION COMPLETE - Bloquer acces direct
# ============================================
# Bloquer acces direct a l'API (uniquement via WireGuard)
iptables -A INPUT -p tcp --dport 8000 -i ${ETH_INTERFACE} -j DROP

# Bloquer acces direct a PostgreSQL
iptables -A INPUT -p tcp --dport 5432 -i ${ETH_INTERFACE} -j DROP

# Bloquer acces direct a Redis (si existant)
iptables -A INPUT -p tcp --dport 6379 -i ${ETH_INTERFACE} -j DROP

# ============================================
# 6. Autoriser localhost
# ============================================
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# ============================================
# 7. Autoriser SSH pour administration (optionnel, supprimer en prod)
# ============================================
# iptables -A INPUT -p tcp --dport 22 -j ACCEPT

echo "[WG PostUp] Pare-feu configure avec succes"
echo "[WG PostUp] Services accessibles UNIQUEMENT via tunnel WireGuard"
