export interface ChannelSettings {
    name: Array<string>;
    topic: Array<string>;
    nsfw: Array<boolean>;
    news: Array<boolean>;
    slowmode_delay: Array<number>;
    create_amount: Array<number>;
}

export interface GuildSettings {
    name: Array<string>;
    icon: Array<string>;
    banner: Array<string>;
    community: Array<string>;
    description: Array<string>;
    vanity: Array<string>;
    verification_level: Array<number>;
    content_filter: Array<number>;
    notification_level: Array<number>;
    system_channel_flags: Array<number>;
    server_widget: Array<boolean>;
    premium_progress_bar_enabled: Array<boolean>;
    dms_disabled_until: Array<number>;
    invites_disabled_until: Array<number>;
    invites_disabled: Array<boolean>;
}

export interface RoleSettings {
    name: Array<string>;
    icon: Array<string>;
    color: Array<number>;
    hoist: Array<boolean>;
    mentionable: Array<boolean>;
    permissions: Array<number>;
    create_amount: Array<number>;
}

export interface EmojiSettings {
    url: Array<string>;
    name: Array<string>;
}

export interface StickerSettings {
    url: Array<string>;
    name: Array<string>;
    description: Array<string>;
    emoji: Array<string>;
}

export interface SoundboardSettings {
    url: Array<string>;
    name: Array<string>;
    emoji: Array<string>;
}

export interface InviteSettings {
    create_amount: Array<number>;
}

export interface AutomodSettings {
    create_amount: Array<number>;
}

export interface TemplateSettings {
    name: Array<string>;
    description: Array<string>;
    create_amount: Array<number>;
}

export interface WebhookSettings {
    username: Array<string>;
    avatar_url: Array<string>;
    amount: Array<string>;
}

export interface MessageSettings {
    content: Array<string>;
    tts: Array<boolean>;
    embed: Array<any>;
}

export interface NoAdminSettings {
    username: Array<string>;
    avatar_url: Array<string>;
    content: Array<string>;
    tts: Array<boolean>;
    // TODO: Add embed interface
    embed: Array<any>;
}

export interface Preset {
    channel: Array<ChannelSettings>;
    guild: Array<GuildSettings>;
    role: Array<RoleSettings>;
    emoji: Array<EmojiSettings>;
    sticker: Array<StickerSettings>;
    soundboard: Array<SoundboardSettings>;
    invite: Array<InviteSettings>;
    automod: Array<AutomodSettings>;
    template: Array<TemplateSettings>;
    webhook: Array<WebhookSettings>;
    message: Array<MessageSettings>;
    no_admin: Array<NoAdminSettings>;
}

export interface CustomPreset {
    id: number;
    preset: Preset;
}

export interface Settings {
    presets: Array<CustomPreset>;
    selected_preset: number;
    command_prefix: Array<string>;
    auto_nuke: number;
    default_event: boolean;
    reason: Array<string>;
}

export interface Auth {
    user_id: bigint;
    username: string;
    avatar: string;
    access_token: string;
    token_type: string;
    scope: Array<string>;
    refresh_token: string;
    expires: BigInt;
}

export interface User {
    user_id: bigint;
    is_super: boolean;
    premium_expires_at: bigint;
    auth: Auth | null;
    is_blacklisted: boolean;
    is_owner: boolean;
}