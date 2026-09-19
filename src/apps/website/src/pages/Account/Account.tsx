import type { User } from "../../types";
import Error from "../Error/Error";
import axios from "axios";
import './Account.css';

interface Props {
    user: User | null;
}

export default function Account({ user }: Props) {
    if (!user) {
        return <Error status={401} error='Unauthorized' message='Please log in to access this page.' ></Error>
    }
    function deleteAccount() {
        const confirmed = window.confirm(`Delete account associated with ${user?.auth?.username} (ID: ${user?.user_id})? This action is irreversible.`)
        if (confirmed) {
            axios.delete(`https://api.fluc.lol/db/user/${user?.user_id}`, { withCredentials: true });
            setTimeout(() => {
                window.location.href = '/';
            }, 1000);
        }
    }
    return (
        <>
            <h2>{`Welcome ${user.auth?.username}`}</h2>
            <button onClick={deleteAccount} id='btn-delete-account'>Delete Account</button>
        </>
    )
}