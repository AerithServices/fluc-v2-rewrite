import axios from "axios";
import { useEffect, useState } from "react";

export default function GetBot() {
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [url, setUrl] = useState<string | null>(null);

    useEffect(() => {
        async function get_url() {
            try {
                setLoading(true);
                let response = await axios.get('https://api.fluc.lol/verify/get-url?get_bot=True');
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