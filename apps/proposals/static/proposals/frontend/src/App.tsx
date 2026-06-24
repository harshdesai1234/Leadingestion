import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import DocumentList from './pages/DocumentList';
import WizardFlow from './pages/WizardFlow';
import Editor from './pages/Editor';

function App() {
  return (
    <BrowserRouter basename="/proposals">
      <Routes>
        <Route path="/" element={<DocumentList />} />
        <Route path="/create/*" element={<WizardFlow />} />
        <Route path="/:id/edit" element={<Editor />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
