SELECT *
FROM users
WHERE user_id = %s
    AND blacklisted_until IS NOT NULL
    AND blacklisted_until >= CURRENT_DATE; 