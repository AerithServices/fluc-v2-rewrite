import { Link } from "react-router-dom";

export default function PrivacyPolicy() {
    return (
        <>
            <h1>Privacy Policy</h1>

            <h2>General</h2>
            <ol>
                <li>We may temporarily collect certain information, including your IP address, for operational purposes.</li>
                <li>All data is securely stored within our database. Under no circumstances is any data sold or disclosed to third parties.</li>
                <li>Information provided on this site, including user settings, may be retained in our database for service functionality.</li>
                <li>Users may request the deletion of their data at any time. To do so, please press the "Delete Account" button and confirm the prompt within your <Link to='/account'>account settings</Link>.</li>
            </ol>

            <h2>Registration</h2>
            <ol>
                <li>
                    During registration, we may store information from your Discord account to ensure full platform functionality.
                    This information may include your user ID, username, and avatar.
                </li>
            </ol>
        </>
    );
}
