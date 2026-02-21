import EcosystemCanvas from './components/EcosystemCanvas';
import FeedbackPanel from './components/FeedbackPanel';
import './App.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>The Lost World Plateau</h1>
        <p className="subtitle">A living ecosystem — observe, suggest, evolve</p>
      </header>
      <main className="app-main">
        <section className="canvas-section">
          <div className="canvas-frame">
            <EcosystemCanvas />
          </div>
          <div className="canvas-legend">
            <span className="legend-item">
              <span className="legend-dot plant" /> Plants
            </span>
            <span className="legend-item">
              <span className="legend-dot herbivore" /> Herbivores
            </span>
            <span className="legend-item">
              <span className="legend-tri predator" /> Predators
            </span>
          </div>
        </section>
        <aside className="feedback-section">
          <FeedbackPanel />
        </aside>
      </main>
    </div>
  );
}

export default App;
