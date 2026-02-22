import EcosystemCanvas from "./components/EcosystemCanvas";
import FeedbackPanel from "./components/FeedbackPanel";
import "./App.css";

function App() {
  return (
    <div className="app">
      <header className="app__header">
        <h1 className="app__title">The Lost World Plateau</h1>
        <p className="app__subtitle">A living ecosystem, shaped by your suggestions</p>
      </header>
      <main className="app__main">
        <section className="app__canvas-area">
          <EcosystemCanvas />
        </section>
        <aside className="app__feedback-area">
          <FeedbackPanel />
        </aside>
      </main>
    </div>
  );
}

export default App;
