import { ResearchSettingsProvider } from "./context/ResearchSettingsProvider";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ConversationPage } from "./pages/ConversationPage";
import { LoginPage } from "./pages/LoginPage";

function AuthenticatedApp() {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#070b14] text-sm text-slate-400">
        Loading…
      </div>
    );
  }

  if (!session) {
    return <LoginPage />;
  }

  return (
    <ResearchSettingsProvider>
      <ConversationPage />
    </ResearchSettingsProvider>
  );
}

function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}

export default App;
