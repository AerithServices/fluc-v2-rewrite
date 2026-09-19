import { Link } from 'react-router-dom';
import './QuickActions.css';

export default function QuickActions() {
    return (
        <div className='quick-actions'>
            <p>Actions</p>
            <hr />
            <Link to='/account'>Account</Link>
            <Link to='/dash'>Dashboard</Link>
            <a href={`https://api.fluc.lol/account/logout?redirect=${encodeURIComponent(location.pathname)}`}>Log out</a>
        </div>
    );
}