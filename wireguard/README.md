# WireGuard - Infrastructure Zero-Trust MassaCorp

## Vue d'ensemble

Infrastructure VPN WireGuard avec isolation complete.
Tous les services (API, DB, Redis) sont accessibles UNIQUEMENT via le tunnel WireGuard.

## Architecture

```
                           INTERNET
                               |
                               | (Port 51820/UDP uniquement)
                               v
                     +-------------------+
                     |    WireGuard      |
                     |   (Passerelle)    |
                     |   10.10.0.1       |
                     +-------------------+
                               |
               +---------------+---------------+
               |               |               |
               v               v               v
         +---------+     +---------+     +---------+
         |   API   |     |   DB    |     |  Redis  |
         |10.10.0.2|     |10.10.0.3|     |10.10.0.5|
         +---------+     +---------+     +---------+

    === RESEAU INTERNE ISOLE (10.10.0.0/24) ===
```

## Structure des fichiers

```
wireguard/
├── README.md                    <- Ce fichier
├── config/                      <- Configuration generee (monte par Docker)
│   ├── wg0.conf                 <- Config serveur generee
│   ├── server_privatekey        <- Cle privee serveur
│   └── server_publickey         <- Cle publique serveur
├── scripts/
│   ├── postup.sh                <- Regles iptables au demarrage
│   ├── postdown.sh              <- Nettoyage iptables a l'arret
│   ├── sync_peers.sh            <- Synchronisation peers depuis DB
│   └── generate_client_config.sh <- Generation config client
└── wg0.conf.template            <- Template de configuration
```

## Demarrage rapide

### 1. Preparer l'environnement
```bash
# Copier le fichier d'exemple
cp .env.wireguard.example .env

# Editer les valeurs (IMPORTANT: changer les mots de passe!)
nano .env
```

### 2. Demarrer l'infrastructure
```bash
# Avec le docker-compose WireGuard
docker-compose -f docker-compose.wireguard.yml up -d

# Verifier les logs
docker-compose -f docker-compose.wireguard.yml logs -f wireguard
```

### 3. Recuperer la cle publique du serveur
```bash
docker exec massacorp_wireguard cat /config/server_publickey
```

### 4. Creer un peer client
```bash
# Generer les cles client
wg genkey | tee client_private.key | wg pubkey > client_public.key

# La cle publique a ajouter cote serveur
cat client_public.key
```

## Gestion des peers

### Via API (recommande)
```bash
# Creer un nouveau peer
curl -X POST http://10.10.0.2:8000/api/v1/wg/peers \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "laptop-john",
    "public_key": "abc123...",
    "peer_type": "client"
  }'

# Lister les peers
curl http://10.10.0.2:8000/api/v1/wg/peers \
  -H "Authorization: Bearer <token>"

# Revoquer un peer
curl -X DELETE http://10.10.0.2:8000/api/v1/wg/peers/123 \
  -H "Authorization: Bearer <token>"
```

### Via ligne de commande
```bash
# Ajouter manuellement un peer
docker exec massacorp_wireguard wg set wg0 \
  peer <CLE_PUBLIQUE_CLIENT> \
  allowed-ips 10.10.0.10/32

# Voir les peers actifs
docker exec massacorp_wireguard wg show

# Supprimer un peer
docker exec massacorp_wireguard wg set wg0 \
  peer <CLE_PUBLIQUE_CLIENT> remove
```

## Configuration client

### Exemple de configuration
```ini
[Interface]
# Cle privee du client
PrivateKey = <VOTRE_CLE_PRIVEE>
Address = 10.10.0.10/32
DNS = 10.10.0.1

[Peer]
# Serveur MassaCorp
PublicKey = <CLE_PUBLIQUE_SERVEUR>
Endpoint = vpn.massacorp.com:51820
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
```

### Installation client
```bash
# Linux
sudo apt install wireguard
sudo cp client.conf /etc/wireguard/wg0.conf
sudo wg-quick up wg0

# macOS (via Homebrew)
brew install wireguard-tools
sudo wg-quick up ./client.conf

# Windows/macOS/Android/iOS
# Importer le fichier .conf ou scanner le QR code
```

## Allocation IP

| Adresse | Attribution |
|---------|-------------|
| 10.10.0.1 | Serveur WireGuard |
| 10.10.0.2 | API FastAPI |
| 10.10.0.3 | PostgreSQL |
| 10.10.0.4 | Service sync peers |
| 10.10.0.5 | Redis |
| 10.10.0.6-253 | Clients dynamiques |
| 10.10.0.254 | Gateway Docker |

## Securite

### Points cles
1. **Seul le port 51820/UDP est expose** - Tout le reste est isole
2. **Cles privees jamais en clair** - Chiffrees en DB avec AES-256
3. **PSK optionnel** - Couche de securite supplementaire
4. **Revocation instantanee** - Suppression immediate du peer
5. **Audit complet** - Tous les handshakes sont logues

### Regles iptables appliquees
```bash
# Bloquer acces direct a l'API
iptables -A INPUT -p tcp --dport 8000 -i eth0 -j DROP

# Bloquer acces direct a PostgreSQL
iptables -A INPUT -p tcp --dport 5432 -i eth0 -j DROP

# Bloquer acces direct a Redis
iptables -A INPUT -p tcp --dport 6379 -i eth0 -j DROP
```

## Monitoring

### Verifier l'etat du tunnel
```bash
# Status WireGuard
docker exec massacorp_wireguard wg show

# Derniers handshakes
docker exec massacorp_wireguard wg show wg0 latest-handshakes

# Transfer stats
docker exec massacorp_wireguard wg show wg0 transfer
```

### Logs
```bash
# Logs WireGuard
docker logs massacorp_wireguard -f

# Logs synchronisation peers
docker logs massacorp_wg_sync -f
```

## Depannage

### Le client ne se connecte pas
1. Verifier que le port 51820/UDP est ouvert sur le firewall
2. Verifier la cle publique du serveur dans la config client
3. Verifier que l'IP assignee n'est pas deja utilisee

### Pas d'acces aux services internes
1. Verifier que le tunnel est actif: `wg show`
2. Tester la connectivite: `ping 10.10.0.1`
3. Verifier les AllowedIPs dans la config client

### Handshake echoue
1. Verifier que les cles sont correctes
2. Verifier l'endpoint (IP:port) du serveur
3. Verifier les regles firewall cote client

## Base de donnees

Les peers sont stockes dans la table `wg_peers`:

```sql
-- Voir tous les peers actifs
SELECT name, assigned_ip, last_handshake_at
FROM wg_peers
WHERE enabled = true AND revoked_at IS NULL;

-- IPs disponibles
SELECT COUNT(*) FROM wg_ip_pool
WHERE is_allocated = FALSE AND is_reserved = FALSE;
```

## Maintenance

### Rotation des cles serveur
```bash
# Generer nouvelles cles
wg genkey | tee server_private.key | wg pubkey > server_public.key

# Mettre a jour la config et redemarrer
docker-compose -f docker-compose.wireguard.yml restart wireguard

# ATTENTION: Tous les clients devront mettre a jour la cle publique serveur
```

### Backup
```bash
# Sauvegarder les cles et configs
tar -czvf wireguard-backup.tar.gz wireguard/config/

# Exporter les peers depuis la DB
pg_dump -t wg_peers -t wg_ip_pool MassaCorp > wg_peers_backup.sql
```
