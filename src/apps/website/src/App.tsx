import './App.css';
import MainLayout from './layouts/MainLayout/MainLayout';
import Cookies from "universal-cookie";
import { Routes, Route, Navigate } from 'react-router-dom';
import { lazy, useEffect, useState, type ReactElement } from 'react';
import { getUser } from './utils';
import type { User } from './types';
import PrivacyPolicy from './pages/PrivacyPolicy/PrivacyPolicy';
import TermsOfService from './pages/TermsOfService/TermsOfService';
import DashboardLayout from './layouts/DashboardLayout/DashboardLayout';
import DiscordRedirect from './pages/DiscordRedirect/DiscordRedirect';
import Faq from './pages/Faq/Faq';
import Rules from './pages/Rules/Rules';

const cookies = new Cookies();
const Dashboard = lazy(() => import('./pages/Dashboard/Dashboard'));
const Home = lazy(() => import('./pages/Home/Home'));
const Error = lazy(() => import('./pages/Error/Error'));
const Account = lazy(() => import('./pages/Account/Account'));
const AccountLogin = lazy(() => import('./pages/Account/Login/AccountLogin'));
const ProfileSelector = lazy(() => import('./pages/ProfileSelector/ProfileSelector'));
const GetBot = lazy(() => import('./pages/GetBot/GetBot'));

function App() {
	const [user, setUser] = useState<User | null>(null);
	const [errorPage, setErrorPage] = useState<ReactElement | null>(null);

	useEffect(() => {
		const status = cookies.get('status');
		const error = cookies.get('error');
		const msg = cookies.get('msg');
		if (status || error || msg) {
			cookies.remove('error');
			cookies.remove('msg');
			cookies.remove('status');
			setErrorPage(<Error status={status} message={msg} error={error}></Error>);
		}
	}, []);

	useEffect(() => {
		getUser().then(({ user }) => {
			if (user)
				setUser({ ...user });
		});
	}, []);

	if (errorPage)
		return errorPage

	return (
		<div className='app'>
			<Routes>
				<Route element={<MainLayout user={user} />}>
					<Route index element={<Home user={user} />} />
					<Route path='/account' element={<Account user={user} />} />
					<Route path='/account/login' element={<AccountLogin user={user} />} />
					<Route path='/profile-selector' element={<ProfileSelector user={user} />} />
					<Route path='/terms-of-service' element={<TermsOfService />} />
					<Route path='/privacy-policy' element={<PrivacyPolicy />} />
					<Route path='/discord' element={<DiscordRedirect />} />
					<Route path='/get-bot' element={<GetBot />} />
					<Route path='/faq' element={<Faq />} />
					<Route path='/rules' element={<Rules />} />
					<Route path='/dash' element={<Navigate to='/dashboard' replace />} />
					<Route path='/tos' element={<Navigate to='/terms-of-service' replace />} />
					<Route path='/pp' element={<Navigate to='/privacy-policy' replace />} />
					<Route path='/dc' element={<Navigate to='/discord' replace />} />
				</Route>
				<Route element={<DashboardLayout user={user} />}>
					<Route path='/dashboard' element={<Dashboard user={user} />} />
				</Route>
				<Route path='*' element={<Error status={404} message='The requested page was not found.' />} />
			</Routes >
		</div>
	)
}

export default App
