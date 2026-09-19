import { Link } from "react-router-dom";
import type { User } from "../../types";
import flucTransperent from '/src/assets/v2/fluc_transperent.png';
import './Home.css';

interface Props {
    user: User | null;
}

export default function Home({ user }: Props) {
    return (
        <div className='home'>
            <h1>Welcome to Fluc</h1>
            <div className='description'>
                <img src={flucTransperent} alt='Fluc icon' />
                <div className='info'>
                    <h2>Why choose Fluc?</h2>
                    <hr />
                    <ul>
                        <li>Fluc is the most customizable (soon) and modern Discord nuke bot out there - <b>100% free</b>.</li>
                        <li>No sketchy authorizations / payments.</li>
                        <li>Clean & friendly community with no com kids and wannabe hackers.</li>
                        <li>No logs & data deletion available.</li>
                    </ul>
                    {!user && (
                        <>
                            <p><a href='/account/login'>Register</a>* and start nuking servers <b>today</b>! Or <a href='/discord'>join our Discord</a></p>
                            <p id='consent'>*By signing up or joining you agree to our <Link to='/tos'>Terms of Service</Link> and <Link to='/pp'>Privacy Policy</Link>.</p>
                        </>
                    )}
                </div>
            </div>
        </div>
    )
}