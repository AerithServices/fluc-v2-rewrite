UPDATE users
SET blacklisted_until = NULL
WHERE user_id = %s;