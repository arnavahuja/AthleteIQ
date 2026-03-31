import ChatInterface from "./components/ChatInterface";
import "./styles/index.css";

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>AthleteIQ</h1>
        <p>RAG-powered athlete performance insights</p>
      </header>
      <main className="app-main">
        <ChatInterface />
      </main>
    </div>
  );
}

export default App;
