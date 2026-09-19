import { Link } from 'react-router-dom';
import './Footer.css';

export default function Footer() {
    return (
        <footer>
            <p>&copy; {new Date().getFullYear()} Fluc. All rights reserved.</p>
            <div className='consents'>
                <Link to='/tos'>Terms Of Service</Link>
                <Link to='/pp'>Privacy Policy</Link>
            </div>
        </footer>
    )
}