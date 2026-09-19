import { Outlet } from "react-router-dom";
import Header from './../../components/Header/Header';
import type { User } from "../../types";
import Footer from "../../components/Footer/Footer";

interface Props {
    user: User | null;
}

export default function MainLayout({ user }: Props) {
    return (
        <>
            <Header user={user} />
            <main className='content'>
                <Outlet />
            </main>
            <Footer />
        </>
    );
}
