INSERT INTO fuck_ai(
    user_id
) VALUES(%s)
ON DUPLICATE KEY UPDATE
    user_id=user_id;