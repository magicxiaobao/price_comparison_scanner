import { HashRouter, Routes, Route } from "react-router-dom";
import HomePage from "./app/home-page";
import ProjectWorkbench from "./app/project-workbench";
import RuleManagement from "./app/rule-management";
import AppPreferences from "./app/app-preferences";

function App() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/project/:id" element={<ProjectWorkbench />} />
        <Route path="/rules" element={<RuleManagement />} />
        <Route path="/preferences" element={<AppPreferences />} />
      </Routes>
    </HashRouter>
  );
}

export default App;
