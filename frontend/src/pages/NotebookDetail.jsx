import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowLeft, BookOpen, CalendarClock, Check, Leaf, Refrigerator } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { getNotebookEntry } from '../api/api';

const fruitEmoji = { Apple: '🍎', Banana: '🍌', Mango: '🥭', Orange: '🍊', Grapes: '🍇', Tomato: '🍅', Papaya: '🍈' };

function NutritionLabel({ facts }) {
  if (!facts || !facts.serving) return null;
  return (
    <section className="notebook-section">
      <div className="info-heading"><Leaf size={19} /><h2>Nutrition Facts</h2></div>
      <section className="nutrition-label" style={{ margin: '10px 0 0' }}>
        <h4>Nutrition Facts</h4>
        <div className="nut-serving">
          Serving size: <b>{facts.serving}</b>
        </div>
        <div className="nut-calories">
          <span>Calories</span>
          <strong>{facts.calories ?? '—'}</strong>
        </div>
        <div className="nut-section-head">Macronutrients</div>
        <div className="nut-row"><b>Total Fat</b><span className="nut-amount">{facts.fat_g ?? '—'} g</span></div>
        <div className="nut-row nut-indent"><span>Saturated</span><span className="nut-amount">—</span></div>
        <div className="nut-row nut-indent"><span>Trans</span><span className="nut-amount">0 g</span></div>
        <div className="nut-row"><b>Total Carbohydrate</b><span className="nut-amount">{facts.carbohydrates_g ?? '—'} g</span></div>
        <div className="nut-row nut-indent"><span>Dietary Fiber</span><span className="nut-amount">{facts.fiber_g ?? '—'} g</span></div>
        <div className="nut-row nut-indent"><span>Total Sugars</span><span className="nut-amount">{facts.sugar_g ?? '—'} g</span></div>
        <div className="nut-row"><b>Protein</b><span className="nut-amount">{facts.protein_g ?? '—'} g</span></div>
        {(facts.key_vitamins?.length || facts.key_minerals?.length) ? (
          <div className="nut-vitamins">
            {facts.key_vitamins?.map(v => (
              <div key={'v-' + v.name} className="nut-row">
                <span>{v.name} {v.amount}</span>
                <span className="nut-dv">{v.dv_percent ?? 0}% DV</span>
              </div>
            ))}
            {facts.key_minerals?.map(m => (
              <div key={'m-' + m.name} className="nut-row">
                <span>{m.name} {m.amount}</span>
                <span className="nut-dv">{m.dv_percent ?? 0}% DV</span>
              </div>
            ))}
          </div>
        ) : null}
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 9, borderTop: '1px solid var(--line)', paddingTop: 6 }}>
          * Percent Daily Values are based on a 2,000 calorie diet. Values are approximate.
        </div>
      </section>
    </section>
  );
}

function ShelfLifeCard({ shelf }) {
  if (!shelf || Object.keys(shelf).length === 0) return null;
  const stages = [
    { key: 'underripe', label: 'Underripe', emoji: '🟢' },
    { key: 'ripe', label: 'Ripe', emoji: '🟡' },
    { key: 'overripe', label: 'Overripe', emoji: '🟠' },
    { key: 'spoiled', label: 'Spoiled', emoji: '🔴' },
  ];
  return (
    <section className="notebook-section">
      <div className="info-heading"><CalendarClock size={19} /><h2>Shelf life guide</h2></div>
      <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
        {stages.map(s => (
          <div key={s.key} className="shelf-life-estimate" style={{ margin: 0 }}>
            <div className="shelf-icon" style={{ fontSize: 18 }}>{s.emoji}</div>
            <div style={{ flex: 1 }}>
              <small>{s.label}</small>
              <strong>{shelf[s.key] || '—'}</strong>
              <span>* Estimated assuming proper storage conditions.</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ListSection({ title, icon, items, fields = [] }) {
  return (
    <section className="notebook-section">
      <div className="info-heading">{icon}<h2>{title}</h2></div>
      <div className="notebook-items">
        {items.map((item, index) => (
          <article key={index}>
            <strong>{fields[0] ? item[fields[0]] : item.title}</strong>
            <p>{fields[1] ? item[fields[1]] : item.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function GoodCombinations({ items }) {
  if (!items?.length) return null;
  return (
    <section className="notebook-section">
      <div className="info-heading"><Check size={19} /><h2>Good food combinations</h2></div>
      <div className="combo-list" style={{ margin: '10px 0 0' }}>
        {items.map((c, i) => (
          <div key={i} className="combo-item">
            <div className="combo-bullet">{i + 1}</div>
            <div>
              <strong>Pair with {c.combo_with}</strong>
              <p>{c.benefit}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function NotebookDetail() {
  const { fruitId } = useParams();
  const [entry, setEntry] = useState(null);
  useEffect(() => { getNotebookEntry(fruitId).then(setEntry).catch(() => {}); }, [fruitId]);
  if (!entry) return <main className="empty-page"><BookOpen size={34} /><h1>Loading the entry.</h1><p>Gathering the useful bits about this fruit.</p></main>;
  return (
    <main className="page-shell notebook-detail">
      <Link to="/notebook" className="back-link"><ArrowLeft size={16} /> All notebook entries</Link>
      <header className="detail-hero">
        <div className="notebook-fruit-art">{entry.sample_image ? <img src={entry.sample_image} alt={entry.name} /> : fruitEmoji[entry.name] || '🍃'}</div>
        <div>
          <p className="eyebrow">Fruit notebook</p>
          <h1>{entry.name}</h1>
          <p>{entry.highlight}</p>
        </div>
      </header>
      <div className="disclaimer-banner">{entry.disclaimer}</div>
      <div className="notebook-sections">
        <NutritionLabel facts={entry.nutrition_facts} />
        <ShelfLifeCard shelf={entry.shelf_life_days} />
        <ListSection title="Benefits" icon={<Leaf size={19} />} items={entry.benefits} />
        <GoodCombinations items={entry.good_combinations} />
        <ListSection title="Combinations to avoid" icon={<AlertTriangle size={19} />} items={entry.bad_combinations} fields={['combo_with', 'risk']} />
        <section className="notebook-section">
          <div className="info-heading"><AlertTriangle size={19} /><h2>Overconsumption risks</h2></div>
          <p>{entry.overconsumption_risk}</p>
        </section>
        <section className="notebook-section spoiled-section">
          <div className="info-heading"><AlertTriangle size={19} /><h2>If spoiled</h2></div>
          <div className="notebook-items">
            {entry.rotten_fruit_harms.map(item => (
              <article key={item.risk_title}>
                <strong>{item.risk_title}</strong>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
          <div className="disposal">
            <strong>Safe disposal</strong>
            <p>{entry.safe_disposal_tip}</p>
          </div>
        </section>
        <section className="notebook-section storage-section">
          <div className="info-heading"><Refrigerator size={19} /><h2>Storage tip</h2></div>
          <p>{entry.storage_tip}</p>
        </section>
      </div>
    </main>
  );
}
