import "./App.css";
import { EcosystemCanvas } from "./components/EcosystemCanvas";
import { FeedbackPanel } from "./components/FeedbackPanel";

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">The Lost World Plateau</h1>
        <p className="app-subtitle">A living ecosystem, shaped by your observations</p>
      </header>

      <main className="app-main">
        <section className="ecosystem-section">
          <EcosystemCanvas />
          <div className="ecosystem-legend">
            <span className="legend-item">
              <span className="legend-dot legend-plant" /> Plants
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-herbivore" /> Herbivores
            </span>
            <span className="legend-item">
              <span className="legend-dot legend-predator" /> Predators
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
