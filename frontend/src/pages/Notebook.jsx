import { useEffect, useState } from 'react';
import { BookOpen, Search, ArrowUpRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getNotebook } from '../api/api';

const fruitEmoji = { Apple: '🍎', Banana: '🍌', Mango: '🥭', Orange: '🍊', Grapes: '🍇', Tomato: '🍅', Papaya: '🍈' };

export default function Notebook() {
  const [entries, setEntries] = useState([]); const [state, setState] = useState('loading');
  const [query, setQuery] = useState('');
  useEffect(() => { getNotebook().then(value => { setEntries(value); setState('ready'); }).catch(() => setState('error')); }, []);
  const filtered = entries.filter(item => item.name.toLowerCase().includes(query.toLowerCase()) || item.highlight.toLowerCase().includes(query.toLowerCase()));
  return <main className="page-shell notebook-page"><div className="page-intro notebook-intro"><p className="eyebrow"><BookOpen size={15} /> Fruit knowledge</p><h1>A better way to<br /><em>know your produce.</em></h1><p>A small, practical reference for nutrition, pairings, storage, and food safety.</p></div><div className="disclaimer-banner">{entries[0]?.disclaimer || 'This information is for general educational purposes and is not medical advice.'}</div><label className="notebook-search"><Search size={17} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search fruits or topics" aria-label="Search fruits or topics" /></label>{state === 'loading' ? <div className="notebook-grid-skeleton"><span /><span /><span /><span /></div> : state === 'error' ? <div className="inline-error">The notebook could not be loaded. Please try again shortly.</div> : <div className="notebook-grid">{filtered.map(item => <Link to={`/notebook/${encodeURIComponent(item.fruit_id)}`} className="notebook-card" key={item.fruit_id}><div className="notebook-fruit-art">{item.sample_image ? <img src={item.sample_image} alt="" /> : fruitEmoji[item.name] || '🍃'}</div><div><p className="eyebrow">{item.name}</p><h2>{item.highlight}</h2><span className="text-button">Read entry <ArrowUpRight size={15} /></span></div></Link>)}</div>}{state === 'ready' && !filtered.length && <div className="empty-page compact"><BookOpen size={30} /><h2>No fruit found</h2><p>Try a fruit name or a nutrition topic.</p></div>}</main>;
}
