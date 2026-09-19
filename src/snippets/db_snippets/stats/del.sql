-- Purging all servers would require a custom query
DELETE FROM stats WHERE user_id=%s AND server_id=%s;