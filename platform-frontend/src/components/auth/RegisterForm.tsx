import { useState } from 'react';
import { useAppStore } from '@/store';
import { api, AUTH_API_BASE } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';

export const RegisterForm = ({ onSuccess }: { onSuccess: () => void }) => {
    const [email, setEmail] = useState('');
    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [password, setPassword] = useState('');
    const [mergeData, setMergeData] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const { setAuthUserId } = useAppStore();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        try {
            const currentGuestId = useAppStore.getState().authStatus === 'guest' ? useAppStore.getState().authUserId : null;
            const payload: any = { 
                email, 
                password,
                first_name: firstName,
                last_name: lastName
            };

            if (mergeData && currentGuestId) {
                payload.guest_id = currentGuestId;
            }

            const res = await api.post(`${AUTH_API_BASE}/auth/register`, payload);

            if (res.data.access_token) {
                setAuthUserId(res.data.user_id, 'logged_in', res.data.access_token, res.data.first_name, res.data.email);
                onSuccess();
            }
        } catch (err: any) {
            if (err.response?.status === 503) {
                setError('Auth not configured');
                return;
            }
            const detail = err.response?.data?.detail;
            if (Array.isArray(detail)) {
                setError(detail[0]?.msg || 'Registration failed');
            } else {
                setError(typeof detail === 'string' ? detail : 'Registration failed');
            }
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-4">
                <div className="space-y-2 flex-1">
                    <Label htmlFor="first-name">First Name</Label>
                    <Input
                        id="first-name"
                        placeholder="John"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                    />
                </div>
                <div className="space-y-2 flex-1">
                    <Label htmlFor="last-name">Last Name</Label>
                    <Input
                        id="last-name"
                        placeholder="Doe"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                    />
                </div>
            </div>
            <div className="space-y-2">
                <Label htmlFor="reg-email">Email</Label>
                <Input
                    id="reg-email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                />
            </div>
            <div className="space-y-2">
                <Label htmlFor="reg-password">Password</Label>
                <Input
                    id="reg-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />
            </div>
            
            <div className="flex items-center space-x-2 border p-3 rounded-md bg-muted/50">
                <Checkbox
                    id="merge-data"
                    checked={mergeData}
                    onCheckedChange={(checked) => setMergeData(checked as boolean)}
                />
                <div className="grid gap-1.5 leading-none">
                    <label
                        htmlFor="merge-data"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                    >
                        Merge local data
                    </label>
                    <p className="text-xs text-muted-foreground">
                        Keep your current unsigned session data in your new account.
                    </p>
                </div>
            </div>

            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading}>
                {loading ? 'Creating Account...' : 'Sign Up'}
            </Button>
        </form>
    );
};
