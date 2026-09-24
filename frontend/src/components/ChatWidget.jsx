import { useEffect, useRef, useState } from 'react';
import { Bot, MessageCircle, Send, X } from 'lucide-react';
import { askFruitAssistant } from '../api/api';

const starters = ['How can I tell if a mango is ripe?', 'What are the benefits of bananas?', 'How should I store oranges?', 'Can I eat fruit with yogurt?'];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState([]);
  const scrollRef = useRef(null);
  const conversationId = useRef(sessionStorage.getItem('ripewise-conversation-id') || null);
  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy]);
  const send = async (value = message) => { const text = value.trim(); if (!text || busy) return; setMessage(''); setMessages(items => [...items, { role: 'user', content: text }]); setBusy(true); try { const result = await askFruitAssistant({ message: text, conversation_id: conversationId.current }); conversationId.current = result.conversation_id; sessionStorage.setItem('ripewise-conversation-id', result.conversation_id); setMessages(items => [...items, { role: 'model', content: result.reply }]); } catch { setMessages(items => [...items, { role: 'model', content: 'I could not reach the assistant. Please try again in a moment.' }]); } finally { setBusy(false); } };
  return <div className={`chat-widget ${open ? 'chat-open' : ''}`}><button className="chat-bubble" onClick={() => setOpen(value => !value)} aria-label={open ? 'Close fruit assistant' : 'Open fruit assistant'}>{open ? <X size={21} /> : <MessageCircle size={21} />}</button>{open && <section className="chat-panel"><header><div><span className="chat-avatar"><Bot size={17} /></span><div><strong>Fruit assistant</strong><small>Grounded in the notebook</small></div></div><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close chat"><X size={17} /></button></header><div className="chat-messages">{!messages.length && <div className="chat-welcome"><p>Ask me about freshness, nutrition, storage, or fruit pairings.</p><div>{starters.map(starter => <button key={starter} onClick={() => send(starter)}>{starter}</button>)}</div></div>}{messages.map((item, index) => <div className={`chat-message ${item.role}`} key={`${item.role}-${index}`}>{item.content}</div>)}{busy && <div className="chat-message model typing"><i /><i /><i /></div>}<span ref={scrollRef} /></div><form className="chat-form" onSubmit={event => { event.preventDefault(); send(); }}><input value={message} onChange={event => setMessage(event.target.value)} placeholder="Ask a fruit question" aria-label="Ask a fruit question" /><button className="primary-button" disabled={busy || !message.trim()} aria-label="Send message"><Send size={16} /></button></form></section>}</div>;
}
