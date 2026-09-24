import { createContext, useContext, useEffect, useState } from 'react';
import { getMe, signOut as requestSignOut } from '../api/api';

const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { getMe().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)); }, []);
  const logout = async () => { try { await requestSignOut(); } finally { setUser(null); } };
  return <AuthContext.Provider value={{ user, setUser, loading, logout }}>{children}</AuthContext.Provider>;
}
export function useAuth() { return useContext(AuthContext); }
