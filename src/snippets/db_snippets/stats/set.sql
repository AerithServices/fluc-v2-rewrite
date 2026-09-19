INSERT IGNORE INTO stats(
    user_id,
    server_id,
    member_id
) VALUES(%s, %s, %s)
ON DUPLICATE KEY UPDATE
    -- This doesn't do nothing but doesn't return warnings
    server_id = server_id;