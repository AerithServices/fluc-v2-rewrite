INSERT INTO auths(
    user_id,
    username,
    avatar,
    access_token,
    token_type,
    scope,
    refresh_token,
    expires
) VALUES(%s, %s, %s, %s, %s, %s, %s, %s) AS new
ON DUPLICATE KEY UPDATE
    username = new.username,
    avatar = new.avatar,
    access_token = new.access_token,
    token_type = new.token_type,
    scope = new.scope,
    refresh_token = new.refresh_token,
    expires = new.expires;