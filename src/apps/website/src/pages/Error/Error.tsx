import { Link } from "react-router-dom";

interface Props {
    status?: number;
    message?: string;
    error?: string;
}

export default function Error({ status, message, error }: Props) {
    return (
        <div className='error'>
            <h1>
                {status ? status : ''}
                {status && error ? ' - ' : ''}
                {error ? `${error}` : ''}
                {!status && !error && 'Unknown Error'}
            </h1>
            <p>{message ? message : 'No message specified. Please refresh this page.'}</p>
            <p>Return <Link to='/'>home</Link></p>
        </div>
    )
}