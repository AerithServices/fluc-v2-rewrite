INSERT INTO backups(
    `key`,
    created_at,
    server_id,
    data
) VALUES (%s, %s, %s, %s) as new
ON DUPLICATE KEY UPDATE
    created_at = new.created_at,
    server_id = new.server_id,
    data = new.data;