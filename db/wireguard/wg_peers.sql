-- ============================================
-- WireGuard Peers Management
-- Full isolation + Dynamic peer management
-- ============================================

-- 1) Table principale des peers WireGuard
CREATE TABLE wg_peers (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,
    user_id BIGINT,                          -- NULL si peer systeme (service)

    -- Identification
    name TEXT NOT NULL,                       -- Nom lisible (ex: "laptop-john", "n8n-prod")
    description TEXT,
    peer_type TEXT NOT NULL DEFAULT 'client', -- 'client' | 'service' | 'gateway'

    -- Cles WireGuard
    public_key TEXT NOT NULL,                 -- Cle publique du peer
    preshared_key_hash TEXT,                  -- Hash de la PSK (optionnel, securite++)

    -- Reseau
    allowed_ips TEXT[] NOT NULL,              -- IPs autorisees (ex: {'10.10.0.2/32'})
    assigned_ip INET NOT NULL,                -- IP assignee dans le tunnel
    dns_servers TEXT[],                       -- DNS optionnels

    -- Endpoint (pour peers avec IP publique)
    endpoint TEXT,                            -- host:port si le peer est joignable
    persistent_keepalive INT DEFAULT 25,      -- Keepalive en secondes

    -- Etat
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    revoked_at TIMESTAMPTZ,
    last_handshake_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by BIGINT,                        -- Admin qui a cree le peer

    -- Contraintes
    UNIQUE (public_key),
    UNIQUE (assigned_ip),
    UNIQUE (tenant_id, name)
);

-- 2) Table de configuration du serveur WireGuard
CREATE TABLE wg_server_config (
    id BIGSERIAL PRIMARY KEY,
    interface_name TEXT NOT NULL DEFAULT 'wg0',

    -- Cles (chiffrees en DB)
    private_key_encrypted TEXT NOT NULL,
    public_key TEXT NOT NULL,

    -- Reseau
    listen_port INT NOT NULL DEFAULT 51820,
    address INET NOT NULL,                    -- IP du serveur (ex: 10.10.0.1/24)
    network_cidr CIDR NOT NULL,               -- Reseau WireGuard (ex: 10.10.0.0/24)

    -- DNS et routage
    dns_servers TEXT[],
    post_up TEXT,                             -- Script post-up (iptables, etc.)
    post_down TEXT,                           -- Script post-down

    -- MTU
    mtu INT DEFAULT 1420,

    -- Etat
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (interface_name)
);

-- 3) Table d'audit des connexions WireGuard
CREATE TABLE wg_connection_log (
    id BIGSERIAL PRIMARY KEY,
    peer_id BIGINT NOT NULL,
    tenant_id BIGINT NOT NULL,

    -- Connexion
    event_type TEXT NOT NULL,                 -- 'handshake' | 'disconnect' | 'data_transfer'
    remote_endpoint TEXT,                     -- IP:port du peer

    -- Stats
    rx_bytes BIGINT,
    tx_bytes BIGINT,

    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT wg_connection_log_peer_fk
        FOREIGN KEY (peer_id)
        REFERENCES wg_peers (id)
        ON DELETE CASCADE
);

-- 4) Table d'allocation IP (pool management)
CREATE TABLE wg_ip_pool (
    id BIGSERIAL PRIMARY KEY,
    network_cidr CIDR NOT NULL,               -- Reseau (ex: 10.10.0.0/24)
    ip_address INET NOT NULL,                 -- IP specifique

    -- Allocation
    is_allocated BOOLEAN NOT NULL DEFAULT FALSE,
    peer_id BIGINT,
    allocated_at TIMESTAMPTZ,

    -- Reservation
    is_reserved BOOLEAN NOT NULL DEFAULT FALSE,  -- Pour le serveur, gateway, etc.
    reservation_note TEXT,

    UNIQUE (ip_address),

    CONSTRAINT wg_ip_pool_peer_fk
        FOREIGN KEY (peer_id)
        REFERENCES wg_peers (id)
        ON DELETE SET NULL
);

-- 5) Table des regles d'acces inter-peers
CREATE TABLE wg_access_rules (
    id BIGSERIAL PRIMARY KEY,

    -- Source
    source_peer_id BIGINT,                    -- NULL = tous les peers
    source_network CIDR,                      -- Alternative: par reseau

    -- Destination
    dest_peer_id BIGINT,
    dest_network CIDR,
    dest_port INT,
    dest_protocol TEXT DEFAULT 'any',         -- 'tcp' | 'udp' | 'icmp' | 'any'

    -- Action
    action TEXT NOT NULL DEFAULT 'allow',     -- 'allow' | 'deny'
    priority INT NOT NULL DEFAULT 100,        -- Plus bas = plus prioritaire

    -- Metadata
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT wg_access_rules_source_fk
        FOREIGN KEY (source_peer_id)
        REFERENCES wg_peers (id)
        ON DELETE CASCADE,

    CONSTRAINT wg_access_rules_dest_fk
        FOREIGN KEY (dest_peer_id)
        REFERENCES wg_peers (id)
        ON DELETE CASCADE
);

-- ============================================
-- INDEX
-- ============================================

-- Peers
CREATE INDEX wg_peers_tenant_idx ON wg_peers (tenant_id);
CREATE INDEX wg_peers_user_idx ON wg_peers (user_id);
CREATE INDEX wg_peers_public_key_idx ON wg_peers (public_key);
CREATE INDEX wg_peers_enabled_idx ON wg_peers (enabled) WHERE enabled = TRUE;
CREATE INDEX wg_peers_type_idx ON wg_peers (peer_type);

-- Connection log
CREATE INDEX wg_connection_log_peer_idx ON wg_connection_log (peer_id);
CREATE INDEX wg_connection_log_tenant_idx ON wg_connection_log (tenant_id);
CREATE INDEX wg_connection_log_created_idx ON wg_connection_log (created_at);

-- IP Pool
CREATE INDEX wg_ip_pool_available_idx ON wg_ip_pool (ip_address)
    WHERE is_allocated = FALSE AND is_reserved = FALSE;

-- Access rules
CREATE INDEX wg_access_rules_priority_idx ON wg_access_rules (priority);
CREATE INDEX wg_access_rules_enabled_idx ON wg_access_rules (enabled) WHERE enabled = TRUE;

-- ============================================
-- FONCTIONS UTILITAIRES
-- ============================================

-- Fonction pour obtenir la prochaine IP disponible
CREATE OR REPLACE FUNCTION wg_get_next_available_ip(p_network CIDR)
RETURNS INET AS $$
DECLARE
    next_ip INET;
BEGIN
    SELECT ip_address INTO next_ip
    FROM wg_ip_pool
    WHERE network_cidr = p_network
      AND is_allocated = FALSE
      AND is_reserved = FALSE
    ORDER BY ip_address
    LIMIT 1;

    RETURN next_ip;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour allouer une IP a un peer
CREATE OR REPLACE FUNCTION wg_allocate_ip(p_peer_id BIGINT, p_network CIDR)
RETURNS INET AS $$
DECLARE
    allocated_ip INET;
BEGIN
    -- Obtenir la prochaine IP disponible
    allocated_ip := wg_get_next_available_ip(p_network);

    IF allocated_ip IS NULL THEN
        RAISE EXCEPTION 'No available IP in network %', p_network;
    END IF;

    -- Marquer comme allouee
    UPDATE wg_ip_pool
    SET is_allocated = TRUE,
        peer_id = p_peer_id,
        allocated_at = NOW()
    WHERE ip_address = allocated_ip;

    -- Mettre a jour le peer
    UPDATE wg_peers
    SET assigned_ip = allocated_ip,
        allowed_ips = array_append(allowed_ips, allocated_ip::TEXT || '/32')
    WHERE id = p_peer_id;

    RETURN allocated_ip;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour liberer une IP
CREATE OR REPLACE FUNCTION wg_release_ip(p_ip INET)
RETURNS BOOLEAN AS $$
BEGIN
    UPDATE wg_ip_pool
    SET is_allocated = FALSE,
        peer_id = NULL,
        allocated_at = NULL
    WHERE ip_address = p_ip
      AND is_reserved = FALSE;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Fonction pour initialiser le pool d'IPs
CREATE OR REPLACE FUNCTION wg_init_ip_pool(p_network CIDR, p_server_ip INET)
RETURNS INT AS $$
DECLARE
    ip_count INT := 0;
    current_ip INET;
    network_start INET;
    network_end INET;
BEGIN
    -- Calculer le range
    network_start := host(p_network)::INET + 1;  -- Skip network address
    network_end := broadcast(p_network) - 1;      -- Skip broadcast

    current_ip := network_start;

    WHILE current_ip <= network_end LOOP
        INSERT INTO wg_ip_pool (network_cidr, ip_address, is_reserved, reservation_note)
        VALUES (
            p_network,
            current_ip,
            current_ip = p_server_ip,
            CASE WHEN current_ip = p_server_ip THEN 'WireGuard Server' ELSE NULL END
        )
        ON CONFLICT (ip_address) DO NOTHING;

        ip_count := ip_count + 1;
        current_ip := current_ip + 1;
    END LOOP;

    RETURN ip_count;
END;
$$ LANGUAGE plpgsql;
