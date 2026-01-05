#!/bin/bash
# ============================================
# Generation de configuration client WireGuard
# ============================================

set -euo pipefail

# Arguments
NOM_CLIENT="${1:-}"
CLE_PUBLIQUE_CLIENT="${2:-}"
IP_ASSIGNEE="${3:-}"

if [ -z "$NOM_CLIENT" ] || [ -z "$CLE_PUBLIQUE_CLIENT" ] || [ -z "$IP_ASSIGNEE" ]; then
    echo "Usage: $0 <nom_client> <cle_publique_client> <ip_assignee>"
    exit 1
fi

# Configuration
CLE_PUBLIQUE_SERVEUR="${WG_SERVER_PUBLIC_KEY:-$(cat /etc/wireguard/server_public.key)}"
ENDPOINT_SERVEUR="${WG_SERVER_ENDPOINT:-vpn.massacorp.com:51820}"
RESEAU_WG="${WG_NETWORK:-10.10.0.0/24}"
SERVEURS_DNS="${DNS_SERVERS:-10.10.0.1, 1.1.1.1}"

# Generer la configuration client
cat << EOF
# ============================================
# Configuration Client WireGuard
# Client: ${NOM_CLIENT}
# Genere le: $(date -Iseconds)
# ============================================

[Interface]
# Cle privee du client (GARDEZ-LA SECRETE!)
PrivateKey = <VOTRE_CLE_PRIVEE_ICI>

# Adresse IP dans le tunnel VPN
Address = ${IP_ASSIGNEE}/32

# Serveurs DNS (optionnel)
DNS = ${SERVEURS_DNS}

# MTU optimise
MTU = 1420

[Peer]
# Serveur MassaCorp
PublicKey = ${CLE_PUBLIQUE_SERVEUR}

# Endpoint du serveur (IP publique ou domaine)
Endpoint = ${ENDPOINT_SERVEUR}

# Reseaux accessibles via le tunnel
# ${RESEAU_WG} = Tout le reseau interne MassaCorp
AllowedIPs = ${RESEAU_WG}

# Keepalive pour maintenir la connexion
PersistentKeepalive = 25
EOF
