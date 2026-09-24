import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Detect from './pages/Detect';
import About from './pages/About';
import SignIn from './pages/SignIn';
import SignUp from './pages/SignUp';
import History from './pages/History';
import NotFound from './pages/NotFound';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Notebook from './pages/Notebook';
import NotebookDetail from './pages/NotebookDetail';
import ChatWidget from './components/ChatWidget';
import Dashboard from './pages/Dashboard';
import Logo from './components/Logo';
import BatchScan from './pages/BatchScan';
import Reports from './pages/Reports';
import Admin from './pages/Admin';

class ErrorBoundary extends React.Component { state = { failed: false }; static getDerivedStateFromError() { return { failed: true }; } render() { return this.state.failed ? <NotFound error /> : this.props.children; } }

export default function App() { return <ErrorBoundary><ThemeProvider><AuthProvider><BrowserRouter><Navbar /><Routes><Route path="/" element={<Home />} /><Route path="/dashboard" element={<Dashboard />} /><Route path="/detect" element={<Detect />} /><Route path="/batch-scan" element={<BatchScan />} /><Route path="/reports" element={<Reports />} /><Route path="/admin" element={<Admin />} /><Route path="/notebook" element={<Notebook />} /><Route path="/notebook/:fruitId" element={<NotebookDetail />} /><Route path="/about" element={<About />} /><Route path="/signin" element={<SignIn />} /><Route path="/signup" element={<SignUp />} /><Route path="/history" element={<History />} /><Route path="*" element={<NotFound />} /></Routes><ChatWidget /><footer><Logo size={34} /><strong>ripe<span className="brand-accent">wise</span></strong><span>Visual freshness guidance for everyday produce.</span><div><a href="#social">Instagram</a><a href="#social">Journal</a><a href="#social">Support</a></div></footer></BrowserRouter></AuthProvider></ThemeProvider></ErrorBoundary>; }
