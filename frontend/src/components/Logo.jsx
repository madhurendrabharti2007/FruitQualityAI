export default function Logo({ size = 32 }) {
  return <svg className="logo-mark" width={size} height={size} viewBox="0 0 32 32" role="img" aria-label="Ripewise logo">
    <path d="M16 8.4c-5.3-3.8-11.2.4-10.8 7.1C5.6 23.6 10.1 28 16 28s10.4-4.4 10.8-12.5C27.2 8.8 21.3 4.6 16 8.4Z" fill="currentColor" />
    <path d="M16.2 7.9c.3-3.3 2.5-5.1 5.7-5.5-.3 3.2-2 5.5-5.7 5.5Z" fill="var(--orange)" />
    <path d="M7.5 17.2h17M7.9 21.1h16.2" stroke="var(--paper)" strokeWidth="1.7" strokeLinecap="round" opacity=".9" />
  </svg>;
}
