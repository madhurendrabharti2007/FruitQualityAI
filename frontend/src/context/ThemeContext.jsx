import { createContext, useContext, useEffect, useState } from 'react';

const ThemeContext = createContext(null);
function readCookie() { return document.cookie.match(/(?:^|; )ripewise-theme=([^;]+)/)?.[1]; }
export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => readCookie() || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  useEffect(() => { document.documentElement.classList.toggle('dark', theme === 'dark'); document.cookie = `ripewise-theme=${theme}; max-age=31536000; path=/; SameSite=Lax`; }, [theme]);
  return <ThemeContext.Provider value={{ theme, toggleTheme: () => setTheme(value => value === 'dark' ? 'light' : 'dark') }}>{children}</ThemeContext.Provider>;
}
export function useTheme() { return useContext(ThemeContext); }
