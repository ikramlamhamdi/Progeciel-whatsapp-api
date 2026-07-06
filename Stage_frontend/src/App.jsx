import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import Templates from './pages/Templates'
import Clients from './pages/Clients'
import Campagnes from './pages/Campagnes'
import Dashboard from './pages/Dashboard'
import Messages from "./pages/Messages"

function App() {
  return (
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50">
          <Navbar />
          <main className="max-w-7xl mx-auto px-4 py-8">
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/templates" element={<Templates />} />
              <Route path="/clients" element={<Clients />} />
              <Route path="/campagnes" element={<Campagnes />} />
              <Route path="/messages" element={<Messages />} />

            </Routes>
          </main>
        </div>
      </BrowserRouter>
  )
}

export default App