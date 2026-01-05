# WireGuard Module

## Vue d'ensemble
Module de gestion WireGuard pour une infrastructure zero-trust.
Gestion dynamique des peers via API avec full isolation du stack.

## Architecture

```
                          INTERNET
                              |
                              | (Port 51820/UDP)
                              v
                    +-------------------+
                    |   WireGuard VPN   |
                    |   (wg0 interface) |
                    | 10.10.0.1/24      |
                    +-------------------+
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
        +---------+     +---------+     +---------+
        |   API   |     |   DB    |     | Services|
        |10.10.0.2|     |10.10.0.3|     |10.10.0.x|
        +---------+     +---------+     +---------+
                              ^
                              |
                      (Accessible uniquement
                       via WireGuard tunnel)
```

## Tables

### `wg_peers`
Peers WireGuard (clients, services, gateways).

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | BIGSERIAL | Identifiant unique |
| `tenant_id` | BIGINT | Tenant proprietaire |
| `user_id` | BIGINT | Utilisateur lie (NULL si service) |
| `name` | TEXT | Nom lisible |
| `peer_type` | TEXT | `client`, `service`, `gateway` |
| `public_key` | TEXT | Cle publique WireGuard |
| `preshared_key_hash` | TEXT | Hash PSK (optionnel) |
| `allowed_ips` | TEXT[] | IPs autorisees |
| `assigned_ip` | INET | IP dans le tunnel |
| `endpoint` | TEXT | host:port si joignable |
| `enabled` | BOOLEAN | Peer actif |
| `revoked_at` | TIMESTAMPTZ | Date de revocation |
| `last_handshake_at` | TIMESTAMPTZ | Dernier handshake |

### `wg_server_config`
Configuration du serveur WireGuard.

| Colonne | Type | Description |
|---------|------|-------------|
| `private_key_encrypted` | TEXT | Cle privee chiffree |
| `public_key` | TEXT | Cle publique |
| `listen_port` | INT | Port d'ecoute (51820) |
| `address` | INET | IP serveur (10.10.0.1/24) |
| `network_cidr` | CIDR | Reseau VPN |
| `post_up` | TEXT | Script iptables |
| `post_down` | TEXT | Script cleanup |

### `wg_connection_log`
Audit des connexions.

| Colonne | Type | Description |
|---------|------|-------------|
| `peer_id` | BIGINT | Peer concerne |
| `event_type` | TEXT | `handshake`, `disconnect`, `data_transfer` |
| `remote_endpoint` | TEXT | IP:port du peer |
| `rx_bytes` | BIGINT | Octets recus |
| `tx_bytes` | BIGINT | Octets transmis |

### `wg_ip_pool`
Pool d'allocation IP.

| Colonne | Type | Description |
|---------|------|-------------|
| `network_cidr` | CIDR | Reseau |
| `ip_address` | INET | IP specifique |
| `is_allocated` | BOOLEAN | Allouee a un peer |
| `is_reserved` | BOOLEAN | Reservee (serveur, etc.) |

### `wg_access_rules`
Regles d'acces inter-peers (firewall interne).

| Colonne | Type | Description |
|---------|------|-------------|
| `source_peer_id` | BIGINT | Peer source (NULL = tous) |
| `dest_peer_id` | BIGINT | Peer destination |
| `dest_port` | INT | Port destination |
| `dest_protocol` | TEXT | `tcp`, `udp`, `any` |
| `action` | TEXT | `allow`, `deny` |
| `priority` | INT | Priorite (plus bas = prioritaire) |

## Types de peers

| Type | Description | Exemple |
|------|-------------|---------|
| `client` | Utilisateur final | Laptop, mobile |
| `service` | Service interne | n8n, monitoring |
| `gateway` | Routeur/bridge | Site-to-site VPN |

## Fonctions SQL

### Allocation IP automatique
```sql
-- Obtenir prochaine IP disponible
SELECT wg_get_next_available_ip('10.10.0.0/24');

-- Allouer une IP a un peer
SELECT wg_allocate_ip(peer_id, '10.10.0.0/24');

-- Liberer une IP
SELECT wg_release_ip('10.10.0.5');

-- Initialiser le pool (run once)
SELECT wg_init_ip_pool('10.10.0.0/24', '10.10.0.1');
```

## Flux de creation d'un peer

```
1. POST /wg/peers {name, public_key, peer_type}
   |
   v
2. Valider public_key (format base64, 44 chars)
   |
   v
3. wg_allocate_ip() -> Obtenir IP automatiquement
   |
   v
4. INSERT INTO wg_peers
   |
   v
5. Regenerer config WireGuard serveur
   |
   v
6. `wg syncconf wg0 <(wg-quick strip wg0)`
   |
   v
7. Retourner config client (QR code ou fichier .conf)
```

## Generation config client

```ini
[Interface]
PrivateKey = <CLIENT_PRIVATE_KEY>
Address = 10.10.0.5/32
DNS = 10.10.0.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
PresharedKey = <OPTIONAL_PSK>
Endpoint = vpn.massacorp.com:51820
AllowedIPs = 10.10.0.0/24
PersistentKeepalive = 25
```

## Regles iptables (post_up)

```bash
# NAT pour acces internet via VPN
iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE

# Autoriser forwarding
iptables -A FORWARD -i wg0 -o wg0 -j ACCEPT
iptables -A FORWARD -i wg0 -o eth0 -j ACCEPT
iptables -A FORWARD -i eth0 -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Bloquer acces direct aux services (uniquement via WireGuard)
iptables -A INPUT -p tcp --dport 5432 -i eth0 -j DROP
iptables -A INPUT -p tcp --dport 8000 -i eth0 -j DROP
```

## Monitoring

### Derniers handshakes
```sql
SELECT p.name, p.assigned_ip, p.last_handshake_at,
       NOW() - p.last_handshake_at as idle_time
FROM wg_peers p
WHERE p.enabled = true
ORDER BY p.last_handshake_at DESC NULLS LAST;
```

### Stats de traffic par peer
```sql
SELECT p.name,
       SUM(l.rx_bytes) as total_rx,
       SUM(l.tx_bytes) as total_tx
FROM wg_connection_log l
JOIN wg_peers p ON p.id = l.peer_id
WHERE l.created_at > NOW() - INTERVAL '24 hours'
GROUP BY p.name
ORDER BY total_rx + total_tx DESC;
```

### IPs disponibles
```sql
SELECT COUNT(*) as available
FROM wg_ip_pool
WHERE is_allocated = FALSE AND is_reserved = FALSE;
```

## Securite

1. **Cles privees chiffrees** : AES-256-GCM en DB
2. **PSK optionnel** : Couche de securite supplementaire
3. **Revocation instantanee** : `wg set wg0 peer <key> remove`
4. **Audit complet** : Tous les handshakes loges
5. **Access rules** : Firewall inter-peers

## Relations avec autres modules

- **auth/** : Utilisateurs lies aux peers
- **rbac/** : Permissions de gestion WireGuard
- **audit/** : Actions WireGuard dans audit_log
- **api_keys/** : API keys pour services automatises
