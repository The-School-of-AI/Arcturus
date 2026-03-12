import { useState } from 'react';
import { useAppStore } from '@/store';
import { api, AUTH_API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export const LoginForm = ({ onSuccess }: { onSuccess: () => void }) => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const { setAuthUserId } = useAppStore();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            // Include guest ID for optional migration
            const currentGuestId = useAppStore.getState().authStatus === 'guest' ? useAppStore.getState().authUserId : null;
            const payload: any = { username: email, password };
            if (currentGuestId && currentGuestId.startsWith('guest_')) {
                payload.guest_id = currentGuestId;
            }

            // Assume standard OAuth2 password request if FastAPI Form, but we will send JSON for now
            // Update: FastAPI typically uses form data for /token, but our custom /auth/login could use JSON
            const res = await api.post(`${AUTH_API_BASE}/auth/login`, payload);

            if (res.data.access_token) {
                setAuthUserId(res.data.user_id, 'logged_in', res.data.access_token);
                onSuccess();
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                    id="email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
            </div>
            <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
                {loading ? 'Logging in...' : 'Log In'}
            </Button>
        </form>
    );
};
