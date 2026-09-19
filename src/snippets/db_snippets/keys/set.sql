INSERT INTO `keys` (
    `key`,
    issued_at,
    expires_at,
    `value`,
    `type`,
    redeemed_at
) VALUES (%s, %s, %s, %s, %s, %s) AS new
ON DUPLICATE KEY UPDATE
    issued_at = new.issued_at,
    expires_at = new.expires_at,
    `value` = new.value,
    `type` = new.type,
    redeemed_at = new.redeemed_at;