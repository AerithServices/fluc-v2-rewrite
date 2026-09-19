INSERT INTO settings (
    user_id,
    server_name,
    channel_name,
    message_content,
    bot_nick,
    bot_bio,
    bot_avatar,
    bot_banner,
    rbot_message,
    rbot_tts
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) AS new
ON DUPLICATE KEY UPDATE 
    server_name = new.server_name,
    channel_name = new.channel_name,
    message_content = new.message_content,
    bot_nick = new.bot_nick,
    bot_bio = new.bot_bio,
    bot_avatar = new.bot_avatar,
    bot_banner = new.bot_banner,
    rbot_message = new.rbot_message,
    rbot_tts = new.rbot_tts;