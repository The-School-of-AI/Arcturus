import { useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { useAppStore } from '@/store';
import { LoginForm } from './LoginForm';
import { RegisterForm } from './RegisterForm';

interface AuthModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export const AuthModal = ({ isOpen, onClose }: AuthModalProps) => {
    const [activeTab, setActiveTab] = useState<'login' | 'register'>('login');
    const { authStatus, authUserEmail, authUserFirstName, logoutAuth } = useAppStore();

    if (authStatus === 'logged_in') {
        return (
            <Dialog open={isOpen} onOpenChange={onClose}>
                <DialogContent className="sm:max-w-[400px]">
                    <DialogHeader>
                        <DialogTitle>Account</DialogTitle>
                        <DialogDescription>
                            You are logged in as {authUserFirstName || authUserEmail || 'User'}.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="py-4">
                        <Button 
                            variant="destructive" 
                            className="w-full" 
                            onClick={() => {
                                logoutAuth();
                                onClose();
                            }}
                        >
                            Log Out
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        );
    }

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[400px]">
                <DialogHeader>
                    <DialogTitle>Sign In to Arcturus</DialogTitle>
                    <DialogDescription>
                        Sync your spaces, tasks, and agents across devices.
                    </DialogDescription>
                </DialogHeader>
                <Tabs value={activeTab} onValueChange={(v: string) => setActiveTab(v as 'login' | 'register')} className="w-full">
                    <TabsList className="grid w-full grid-cols-2 mb-4">
                        <TabsTrigger value="login">Login</TabsTrigger>
                        <TabsTrigger value="register">Register</TabsTrigger>
                    </TabsList>
                    <TabsContent value="login">
                        <LoginForm onSuccess={onClose} />
                    </TabsContent>
                    <TabsContent value="register">
                        <RegisterForm onSuccess={onClose} />
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    );
};
