import { ResearchSettingsProvider } from "./context/ResearchSettingsProvider";
import { ConversationPage } from "./pages/ConversationPage";

function App() {
  return (
    <ResearchSettingsProvider>
      <ConversationPage />
    </ResearchSettingsProvider>
  );
}

export default App;
