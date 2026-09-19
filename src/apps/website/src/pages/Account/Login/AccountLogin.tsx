import axios from "axios";
import type { User } from "../../../types";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

interface Props {
    user: User | null;
}

export default function AccountLogin({ user }: Props) {
    if (user) {
        window.location.href = '/';
        return <></>
    }
    const [searchParams] = useSearchParams();
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [url, setUrl] = useState<string | null>(null);

    useEffect(() => {
        async function get_url() {
            try {
                setLoading(true);
                let redirect = searchParams.get('redirect');
                let url = 'https://api.fluc.lol/verify/get-url';
                if (redirect) {
                    url += `?redirect=${encodeURIComponent(redirect)}`
                } else {
                    url += `?redirect=${encodeURIComponent('/')}`
                }
                let response = await axios.get(url);
                setUrl(response.data.url);
            } catch (error) {
                if (axios.isAxiosError(error)) {
                    setError(error.message);
                } else {
                    setError('Unknown error occured.');
                }
            } finally {
                setLoading(false);
            }
        }
        get_url()
    }, []);

    if (loading)
        return <p>Loading...</p>

    if (error)
        return <p>{error}</p>

    if (url) {
        window.location.href = url;
    }
    return <></>
}