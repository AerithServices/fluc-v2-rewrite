import { Link } from "react-router-dom";

export default function Rules() {
    return (
        <>
            <h1>Server Rules</h1>
            <br />
            <h2>Notice</h2>
            <ol>
                <li>The staff team reserves the right to add, alter, or remove any rules as required.</li>
                <li>This list cannot include every possible situation, so moderators may use their own judgment when taking action. Punishments may be issued for reasons not listed here.</li>
                <li>Do not deliberately attempt to circumvent these rules through loopholes or technicalities. Such behavior may be moderated as if the underlying rule had been violated.</li>
                <li>These rules do NOT apply to personal disputes or private matters between individuals. Take personal issues to DMs or block the person. Prohibited activities such as unsolicited advertising, spam, or malicious activity in DMs may still be moderated.</li>
            </ol>
            <h2>1. General</h2>
            <ol>
                <li>By using <Link to='/'>Fluc</Link> you agree to our <b><Link to='/tos'>Terms of Service</Link></b> and <b><Link to='/pp'>Privacy Policy</Link></b>.</li>
                <li>Follow <b><Link to='https://discord.com'>Discord</Link><Link to='https://discord.com/terms'>Terms of Service</Link></b> and <b><Link to='https://discord.com/guidelines'>Community Guidelines</Link></b> at all times.</li>
                <li>Respect staff and members.</li>
                <li>Staff decisions are final.</li>
                <li>If your account is compromised, it will be kicked.</li>
                <li>Impersonating a member or staff is strictly prohibited. </li>
                <li>Evading punishments using alternate accounts, VPNs, or other methods is prohibited.</li>
                <li>Respect the mental health of other users.</li>
                <li>No witch hunting.</li>
            </ol>
            <h2>2. Content</h2>
            <ol>
                <li>Do not post classified, confidential, restricted, or otherwise illegal content.</li>
                <li>No racism, sexism, harassment, generally toxic behavior, NSFW or other disturbing content.</li>
                <li>No spamming, flooding, or inciting raids.</li>
                <li>Excessive emojis, emotes, or special characters that disrupt chat are considered spam.</li>
                <li>Do not send off-topic or repetitive messages that disrupt conversations.</li>
                <li>No minimodding - notify a moderator instead.</li>
                <li>Threats of violence, serious harm, or other credible threats are prohibited.</li>
                <li>Do not distribute malware, phishing links, or other content intended to compromise or harm another user's device or account.</li>
                <li>No suspicious/shortened links allowed.</li>
            </ol>
            <h2>3. Advertising</h2>
            <ol>
                <li>Advertising third-party servers, channels, or websites is prohibited.</li>
                <li>Sending referral links, affiliate codes, or self-promotion, including unsolicited DMs, is prohibited.</li>
            </ol>
            <h2>Punishments</h2>
            <p>Punishments are determined at the discretion of the staff team based on the severity, context, and history of the violation. A verbal warning may be issued for minor or first time violations, while serious violations may result in an immediate mute, kick, or ban.</p>
            <p><b>Mass DMing members will result in an immediate and permanent ban.</b></p>
            <p>Severe violations of <Link to='https://discord.com/terms'>Discord's Terms of Service</Link> may result in an immediate ban and, where appropriate, a report to Discord <Link to='https://discord.com/safety'>Trust & Safety</Link>.</p>
        </>
    )
}