INSERT INTO users (
    user_id,
    blacklisted_until
) VALUES (%s, %s) AS new
ON DUPLICATE KEY UPDATE
    blacklisted_until = new.blacklisted_until;