import './Header.css';
import fluc from '/src/assets/v2/fluc.png';
import moon from '/src/assets/icons/moon.png';
import sun from '/src/assets/icons/sun.png';
import { Link, useLocation } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import Cookies from 'universal-cookie';
import type { User } from '../../types';
import QuickActions from '../QuickActions/QuickActions';

const cookies = new Cookies();
interface Props {
    user: User | null;
}

export default function Header({ user }: Props) {
    const [theme, setTheme] = useState<boolean>(true);
    const [quickActionsOpen, setQuickActionsOpen] = useState<boolean>(false);
    const quickActionsRef = useRef<HTMLDivElement>(null);

    function switchTheme() {
        cookies.set('theme', !theme, { path: '/', maxAge: 60 * 60 * 24 * 360 })
        setTheme(!theme);
    }
    function toggleQuickActions() {
        setQuickActionsOpen(!quickActionsOpen)
    }
    const themeIcon = theme
        ? <img className='change-theme' src={moon} alt='Dark Mode'></img >
        : <img className='change-theme' src={sun} alt='Light Mode'></img>;

    useEffect(() => {
        document.documentElement.setAttribute('theme', theme ? 'light' : 'dark');
    }, [theme]);

    useEffect(() => {
        function onMousedown(event: MouseEvent) {
            if (quickActionsRef.current && !quickActionsRef.current.contains(event.target as Node)) {
                setQuickActionsOpen(false);
            }
        }
        setTheme(cookies.get('theme') ? true : false);
        document.addEventListener('mousedown', onMousedown);
        return () => {
            document.removeEventListener('mousedown', onMousedown);
        }
    }, []);
    const location = useLocation();
    return (
        <div className='header'>
            <div className='header-left'>
                <Link to='/'><img src={fluc} alt='Fluc icon' /></Link>
            </div>
            <div className='header-right'>
                {(!user || !user.auth) && (
                    <div className='login' style={{ backgroundColor: user ? 'transparent' : undefined }}>
                        <a href={`/account/login?redirect=${location.pathname}`}><p>Log in with Discord</p></a>
                    </div>
                )}
                {user && user.auth && (
                    <div className='profile' onClick={toggleQuickActions}>
                        <img src={user.auth.avatar} alt='User Avatar' />
                    </div>
                )}
                {quickActionsOpen && (
                    <div ref={quickActionsRef}>
                        <QuickActions />
                    </div>
                )}
                <div className='change-theme' onClick={switchTheme}>
                    {themeIcon}
                </div>
            </div>
        </div >
    );
}