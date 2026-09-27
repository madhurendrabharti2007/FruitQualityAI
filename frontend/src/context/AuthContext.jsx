import { createContext, useContext, useEffect, useState } from 'react';
import { getMe, signOut as requestSignOut, signIn as signInApi, signUp as signUpApi } from '../api/api';

const TOKEN_KEY = 'fruit_ai_access_token';
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(() => { try { return localStorage.getItem(TOKEN_KEY) || null; } catch { return null; } });
  useEffect(() => { getMe().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false)); }, []);
  useEffect(() => { if (token) { try { localStorage.setItem(TOKEN_KEY, token); } catch {} } else { try { localStorage.removeItem(TOKEN_KEY); } catch {} } }, [token]);
  const signIn = async data => { const res = await signInApi(data); if (res.access_token) setToken(res.access_token); setUser(res); return res; };
  const signUp = async data => { const res = await signUpApi(data); if (res.access_token) setToken(res.access_token); setUser(res); return res; };
  const logout = async () => { try { await requestSignOut(); } finally { setToken(null); setUser(null); } };
  return <AuthContext.Provider value={{ user, setUser, loading, logout, signIn, signUp, token }}>{children}</AuthContext.Provider>;
}
export function useAuth() { return useContext(AuthContext); }
export { TOKEN_KEY };
