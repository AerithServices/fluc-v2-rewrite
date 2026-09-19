INSERT INTO users(
    user_id,
    flags,
    premium_key,
    restore_credits,
    blacklisted_until
) VALUES(%s, %s, %s, %s, %s) AS new
ON DUPLICATE KEY UPDATE
    flags = new.flags,
    premium_key = new.premium_key,
    restore_credits = new.restore_credits,
    blacklisted_until = new.blacklisted_until;