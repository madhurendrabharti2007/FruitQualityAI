import { motion } from 'framer-motion';
import { ScanLine } from 'lucide-react';
import Logo from './Logo';
export default function Loader() { return <div className="loader"><div className="scan-icon"><motion.div className="scan-line" animate={{ y: [0, 48, 0] }} transition={{ repeat: Infinity, duration: 1.5 }} /><Logo size={36} /></div><strong>Reading your fruit</strong><span>Comparing color, texture, and freshness signals...</span></div>; }
