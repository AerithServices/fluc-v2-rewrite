import type { User } from './types';
import axios from 'axios';

export function getUser(): Promise<{ user: User | null; response: any }> {
    return axios
        .get<User | null>('https://api.fluc.lol/db/user', { withCredentials: true })
        .then((response) => {
            let data = response.data;
            if (!data || response.status != 200) {
                console.log(data, 'error')
                return {
                    user: null,
                    response
                }
            }
            const user: User = {
                ...data,
                user_id: BigInt(data.user_id),
                auth: data?.auth
                    ? {
                        ...data.auth,
                        user_id: BigInt(data.auth.user_id),
                    }
                    : null,
            };

            return {
                user,
                response,
            };
        }
        )
        .catch((error) => {
            console.log(error)
            return {
                user: null,
                response: error
            };
        });
}

export function getAvatar(user: User): string {
    let avatar_ext = 'png';
    if (user && user.auth?.avatar) {
        avatar_ext = user.auth.avatar.startsWith('a_') ? 'gif' : 'png';
    }
    if (user.auth && user.auth.avatar) {
        return `https://cdn.discordapp.com/avatars/${user.user_id}/${user.auth.avatar}.${avatar_ext}`
    } else {
        const index = Number((user.user_id >> 22n) % 6n);
        return `https://cdn.discordapp.com/embed/avatars/${index}.${avatar_ext}`
    }
}