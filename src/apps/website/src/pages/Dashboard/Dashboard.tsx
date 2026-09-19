import { useState } from "react";
import type { User } from "../../types";
import Error from "../Error/Error";
import './Dashboard.css';
import { Link } from "react-router-dom";

interface Props {
    user: User | null;
}

export default function Dash({ user }: Props) {
    if (!user) {
        return <Error status={401} error='Unauthorized' message='Please log in to access this page.'></Error>
    }
    const [page, setPage] = useState(0);
    const pages = [
        (
            <div className="category">
                <p className="category-title">No-Admin Messages</p>
                <p>Username</p>
                <input className="no-admin-username" type="text" />
                <p>Avatar URL</p>
                <input className="no-admin-avatar" type="text" />
                <p>Content</p>
                <input className="no-admin-content" type="text" />
                <p>Embed</p>
                {/* Embed Builder */}
                <hr />
                <p>Text-To-Speech</p>
                <input className="no-admin-tts" type="checkbox" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">General Settings</p>
                <p>Reasons</p>
                <input className="reasons" type="text" />
                <hr />
                <p>Create Advertisement</p>
                <input className="premium create-event" type="checkbox" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Channel Settings</p>
                <p>Name</p>
                <input className="channel-name" type="text" />
                <p>Topic</p>
                <input className="channel-topic" type="text" />
                <hr />
                <p>Slowmode Delay</p>
                <input id="channel-slowmode-delay" type="number" min={0} max={60 * 60 * 8} />
                <p>Create Amount</p>
                <input id="channel-create-amount" type="number" min={0} max={500} />
                <hr />
                <p>Nsfw</p>
                <input id="channel-nsfw" type="checkbox" />
                <p>News</p>
                <input id="channel-news" type="checkbox" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Server Settings</p>
                <p>Name</p>
                <input id="server-name" type="text" />
                <p>Icon</p>
                <input id="server-icon" type="text" />
                <p>Banner</p>
                <input id="server-banner" type="text" />
                <p>Description</p>
                <input id="server-description" type="text" />
                <p>Vanity</p>
                <input id="server-vanity" type="text" />
                <hr />
                <p>Verification Level</p>
                <input id="server-verification-level" type="number" />
                <p>Notification Level</p>
                <input type="number" min={0} max={4} />
                <p>Content Filter</p>
                <input type="number" min={0} max={2} />
                <p>System Channel Flags</p>
                <input type="number" />
                <p>DMs Disabled For</p>
                <input type="number" max={60 * 60 * 24 * 7} min={0} /><p className="time">seconds</p>
                <p>Invites Disabled For</p>
                <input type="number" max={60 * 60 * 24 * 7} min={0} /><p className="time">seconds</p>
                <hr />
                <p>Community</p>
                <p className="alert">Enabling this might impact speed</p>
                <input type="checkbox" />
                <p>Server Widget</p>
                <input type="checkbox" />
                <p>Boost Progress Bar Enabled</p>
                <input type="checkbox" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Role Settings</p>
                <p>Name</p>
                <input type="text" />
                <p>Icon</p>
                <input type="text" />
                <hr />
                <p>Permissions</p>
                <input type="number" min={0} max={1829587348619263} />
                <p>Create Amount</p>
                <input type="number" min={0} max={100} />
                <hr />
                <p>Color</p>
                <input type="color" />
                <hr />
                <p>Mentionable</p>
                <input type="checkbox" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Emoji Settings</p>
                <p>Icon URL</p>
                <input type="text" />
                <p>Name</p>
                <input type="text" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Sticker Settings</p>
                <p>Icon URL</p>
                <input type="text" />
                <p>Name</p>
                <input type="text" />
                <p>Description</p>
                <input type="text" />
                <p>Emoji</p>
                <input type="text" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Soundboard Settings</p>
                <p>Sound URL</p>
                <input type="text" />
                <p>Name</p>
                <input type="text" />
                <p>Emoji</p>
                <input type="text" />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Invite Settings</p>
                <p>Create Amount</p>
                <input type="number" min={0} max={50} />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Automod Settings</p>
                <p>Create Amount</p>
                <input type="number" min={0} max={10} />
            </div>
        ),
        (
            <div className="category">
                <p className="category-title">Template Settings</p>
                <p>Name</p>
                <input type="text" />
                <p>Description</p>
                <input type="text" />
            </div>
        ),
        (
            <div className="category" >
                <p className="category-title">Webhook Settings</p>
                <p>Username</p>
                <input type="text" />
                <p>Avatar URL</p>
                <input type="text" />
            </div >
        ),
        (
            <div className="category">
                <p className="category-title">Message Settings</p>
                <p>Content</p>
                <input type="text" />
                <hr />
                <p>Embed</p>
                {/* Embed Builder */}
                <hr />
                <p>Text-To-Speech</p>
                <input type="checkbox" />
                <hr />
                <p>Amount</p>
                <input type="number" />
            </div>
        )
    ]

    function _setPage(num: number) {
        const newPage = page + num;
        if (newPage >= 0 && newPage < pages.length) {
            setPage(newPage);
        } else {
            if (num == -1) {
                setPage(pages.length - 1);
            } else {
                setPage(0);
            }
        }
    }

    // function save() {
    //     axios.patch('/api/user', {
    //         settings: user?.settings
    //     }).then((response) => {
    //         if (response.status == 200) {
    //             alert('Settings saved');
    //         }
    //     }).catch((response) => {
    //         if (response.status == 429) {
    //             alert('Settings not saved. You are being rate limited, please try again later.')
    //         } else {
    //             alert('Failed to save settings. Perhaps try logging in again?')
    //         }
    //     });
    // }

    if (1) {
        return (
            <>
                <p>Sorry, dashboard not available yet. Come back soon!</p>
                <p>Return <Link to='/'>home</Link></p>
            </>
        )
    }
    return (
        <>
            {page == 0 ? <h2>No-Admin Bot Settings</h2> : <h2>Nuke Bot Settings</h2>}
            <div className="controls">
                <button onClick={() => { _setPage(-1) }}>Previous</button>
                <button onClick={() => { _setPage(1) }}>Next</button>
            </div>
            <div className="quick-access">
                <p className={page == 0 ? 'selected' : ''} onClick={() => { setPage(0) }}>No-Admin Settings</p>
                <p className={page == 1 ? 'selected' : ''} onClick={() => { setPage(1) }}>General Settings</p>
                <p className={page == 2 ? 'selected' : ''} onClick={() => { setPage(2) }}>Channel Settings</p>
                <p className={page == 3 ? 'selected' : ''} onClick={() => { setPage(3) }}>Server Settings</p>
                <p className={page == 4 ? 'selected' : ''} onClick={() => { setPage(4) }}>Role Settings</p>
                <p className={page == 5 ? 'selected' : ''} onClick={() => { setPage(5) }}>Emoji Settings</p>
                <p className={page == 6 ? 'selected' : ''} onClick={() => { setPage(6) }}>Sticker Settings</p>
                <p className={page == 7 ? 'selected' : ''} onClick={() => { setPage(7) }}>Soundboard Settings</p>
                <p className={page == 8 ? 'selected' : ''} onClick={() => { setPage(8) }}>Invite Settings</p>
                <p className={page == 9 ? 'selected' : ''} onClick={() => { setPage(9) }}>Automod Settings</p>
                <p className={page == 10 ? 'selected' : ''} onClick={() => { setPage(10) }}>Template Settings</p>
                <p className={page == 11 ? 'selected' : ''} onClick={() => { setPage(11) }}>Webhook Settings</p>
                <p className={page == 12 ? 'selected' : ''} onClick={() => { setPage(12) }}>Message Settings</p>
            </div>
            <p>{`Page ${page + 1}/${pages.length}`}</p>
            {pages.at(page)}
        </>
    )
}