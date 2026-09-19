-- Supress warnings
SET sql_notes = 0;

-- Create tables
CREATE TABLE IF NOT EXISTS users(
    user_id BIGINT UNSIGNED PRIMARY KEY,
    flags INTEGER UNSIGNED DEFAULT 0 NOT NULL,
    -- NULL = User is NOT premium
    -- DATE = Expiration date
    premium_key TEXT DEFAULT NULL,
    restore_credits INTEGER UNSIGNED NOT NULL DEFAULT 0,
    blacklisted_until DATE DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS auths(
    user_id BIGINT UNSIGNED PRIMARY KEY,
    username VARCHAR(32) NOT NULL,
    avatar VARCHAR(120),
    access_token VARCHAR(120) NOT NULL,
    token_type VARCHAR(10) NOT NULL,
    scope VARCHAR(120) NOT NULL,
    refresh_token VARCHAR(120) NOT NULL,
    expires TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS settings(
    user_id BIGINT UNSIGNED PRIMARY KEY,
    server_name VARCHAR(120),
    channel_name VARCHAR(32),
    message_content VARCHAR(1800),
    bot_nick VARCHAR(32),
    bot_bio VARCHAR(100),
    bot_avatar VARCHAR(120),
    bot_banner VARCHAR(120),
    rbot_message VARCHAR(1800),
    rbot_tts BOOLEAN
);

CREATE TABLE IF NOT EXISTS stats(
    user_id BIGINT UNSIGNED NOT NULL,
    server_id BIGINT UNSIGNED NOT NULL,
    member_id BIGINT UNSIGNED NOT NULL,
    -- Do not insert duplicate member from same server
    -- Do insert duplicate member from DIFFERENT server
    PRIMARY KEY (server_id, member_id)
);

CREATE TABLE IF NOT EXISTS punishments(
    punishment_id INTEGER UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    target_user_id BIGINT UNSIGNED NOT NULL,
    action_id SMALLINT NOT NULL,
    executed_action_id SMALLINT NOT NULL,
    done_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) AUTO_INCREMENT = 1000;

CREATE TABLE IF NOT EXISTS `keys`(
    `key` VARCHAR(120) PRIMARY KEY NOT NULL,
    issued_at DATE NOT NULL,
    expires_at DATE NOT NULL,
    `value` INTEGER NOT NULL,
    `type` SMALLINT NOT NULL,
    redeemed_at DATE DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS fuck_ai(
    user_id BIGINT UNSIGNED PRIMARY KEY NOT NULL
);

CREATE TABLE IF NOT EXISTS managed_keys(
    user_id BIGINT UNSIGNED PRIMARY KEY NOT NULL,
    `key` VARCHAR(120) NOT NULL
);

CREATE TABLE IF NOT EXISTS backups(
    `key` VARCHAR(120) PRIMARY KEY NOT NULL,
    created_at DATE NOT NULL,
    server_id BIGINT UNSIGNED NOT NULL,
    data JSON NOT NULL
);