import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { AlertTriangle, ArrowRight, CalendarClock, Check, ScanSearch, ShieldAlert, Sparkles } from 'lucide-react';
import { getNotebookEntry } from '../api/api';

function NutritionLabel({ facts }) {
  if (!facts || !facts.serving) return null;
  return (
    <section className="nutrition-label">
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
  );
}

export default function ResultCard({ result, onReset }) {
  const [entry, setEntry] = useState(null);
  const fresh = result.status === 'fresh';

  useEffect(() => {
    if (result.status === 'not_recognized') { setEntry(null); return; }
    getNotebookEntry(result.fruit).then(setEntry).catch(() => {});
  }, [result.status, result.fruit]);

  if (result.status === 'not_recognized') return (
    <motion.section className="result-card result-neutral" initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }}>
      <div className="neutral-icon"><ScanSearch size={27} /></div>
      <p className="eyebrow">No clear fruit found</p>
      <h2>Try a clearer photo.</h2>
      <p>{result.message}</p>
      <button className="primary-button" onClick={onReset}>Try another photo <ArrowRight size={16} /></button>
    </motion.section>
  );

  return (
    <motion.section className={`result-card ${fresh ? 'result-fresh' : 'result-rotten'}`} initial={{ opacity: 0, y: 22 }} animate={{ opacity: 1, y: 0 }}>
      <div className="result-top">
        <div>
          <p className="eyebrow">Looks like</p>
          <h2>{result.fruit}</h2>
        </div>
        <div className="status-badge">
          {fresh ? <Check size={19} /> : <AlertTriangle size={19} />}
          {fresh ? 'Fresh' : 'Rotten'}
        </div>
      </div>

      <div className="confidence">
        <div className="confidence-ring" style={{ '--confidence': `${result.confidence * 3.6}deg` }}>
          <div>
            <strong>{result.confidence}%</strong>
            <span>confidence</span>
          </div>
        </div>
        <div>
          <p className="eyebrow">Signal strength</p>
          <p className="confidence-copy">Our model is {result.confidence > 80 ? 'quite certain' : 'still getting a read'} about this result.</p>
        </div>
      </div>

      <div className="result-meta">
        <span>
          <small>Ripeness</small>
          <strong>{result.ripeness_stage || (fresh ? 'ripe' : 'spoiled')}</strong>
        </span>
        <span>
          <small>Shelf life estimate</small>
          <strong>{result.shelf_life_estimate || (fresh ? '2-4 days' : '0 days')}</strong>
        </span>
      </div>

      {entry?.nutrition_facts && <NutritionLabel facts={entry.nutrition_facts} />}

      {fresh && entry?.shelf_life_days && (
        <div className="shelf-life-estimate">
          <div className="shelf-icon"><CalendarClock size={19} /></div>
          <div style={{ flex: 1 }}>
            <small>Estimated time left to enjoy</small>
            <strong>{result.shelf_life_estimate || entry.shelf_life_days[result.ripeness_stage || 'ripe'] || '2-4 days'}</strong>
            <span>* Based on {result.ripeness_stage || (fresh ? 'ripe' : 'spoiled')} stage. Keep refrigerated for best results. This is an estimate only.</span>
          </div>
        </div>
      )}

      <div className="info-block">
        <div className="info-heading">
          {fresh ? <Sparkles size={18} /> : <ShieldAlert size={18} />}
          <h3>{fresh ? `Why ${result.fruit} is a good pick` : `A note about this ${result.fruit.toLowerCase()}`}</h3>
        </div>
        <ul>
          {result.info.points.map(point => (
            <li key={point}>
              <span>{fresh ? <Check size={13} /> : <AlertTriangle size={13} />}</span>
              {point}
            </li>
          ))}
        </ul>
        {!fresh && (
          <div className="disposal">
            <strong>Safe disposal</strong>
            <p>{result.info.disposal_tip}</p>
          </div>
        )}
      </div>

      {entry && (
        <div className={`result-notebook ${fresh ? '' : 'result-warning'}`}>
          <div className="info-heading">
            {fresh ? <Sparkles size={18} /> : <AlertTriangle size={18} />}
            <h3>{fresh ? 'From the fruit notebook' : 'If spoiled'}</h3>
          </div>

          {fresh && entry.benefits?.length > 0 && (
            <>
              <h4 style={{ fontFamily: 'Fraunces, serif', fontSize: 17, margin: '12px 0 4px' }}>Benefits</h4>
              <ul>
                {entry.benefits.map(b => (
                  <li key={'b-' + b.title}>
                    <b style={{ color: 'var(--ink)' }}>{b.title}.</b> {b.description}
                  </li>
                ))}
              </ul>
            </>
          )}

          {fresh && entry.good_combinations?.length > 0 && (
            <>
              <h4 style={{ fontFamily: 'Fraunces, serif', fontSize: 17, margin: '16px 0 4px' }}>Good food combinations</h4>
              <div className="combo-list">
                {entry.good_combinations.map((c, i) => (
                  <div key={'c-' + i} className="combo-item">
                    <div className="combo-bullet">{i + 1}</div>
                    <div>
                      <strong>Pair with {c.combo_with}</strong>
                      <p>{c.benefit}</p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {!fresh && entry.rotten_fruit_harms?.length > 0 && (
            <ul>
              {entry.rotten_fruit_harms.map(item => (
                <li key={item.risk_title}>
                  <b style={{ color: 'inherit' }}>{item.risk_title}.</b> {item.description}
                </li>
              ))}
            </ul>
          )}

          {!fresh && <p><strong>Safe disposal:</strong> {entry.safe_disposal_tip}</p>}

          <Link to={`/notebook/${encodeURIComponent(result.fruit)}`} className="text-button">
            View full notebook entry <ArrowRight size={16} />
          </Link>
        </div>
      )}

      {result.demo && <p className="demo-note">Demo mode is active. Add trained weights for production predictions.</p>}
      <button className="text-button" onClick={onReset}>Scan another fruit <ArrowRight size={16} /></button>
    </motion.section>
  );
}
