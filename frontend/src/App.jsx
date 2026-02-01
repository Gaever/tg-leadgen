import React, { useState } from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import { MessageSquare, Search, Users } from 'lucide-react'
import ChatsPage from './components/ChatsPage'
import RAGPage from './components/RAGPage'
import ContactsPage from './components/ContactsPage'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export { API_URL }

function App() {
  return (
    <div className="flex h-screen bg-telegram-bg">
      {/* Sidebar navigation */}
      <nav className="w-16 bg-telegram-sidebar flex flex-col items-center py-4 border-r border-gray-800">
        <NavLink 
          to="/" 
          className={({ isActive }) => 
            `w-12 h-12 rounded-xl flex items-center justify-center mb-2 transition-colors ${
              isActive ? 'bg-telegram-blue text-white' : 'text-telegram-textSecondary hover:bg-telegram-hover'
            }`
          }
        >
          <MessageSquare size={24} />
        </NavLink>
        
        <NavLink 
          to="/rag" 
          className={({ isActive }) => 
            `w-12 h-12 rounded-xl flex items-center justify-center mb-2 transition-colors ${
              isActive ? 'bg-telegram-blue text-white' : 'text-telegram-textSecondary hover:bg-telegram-hover'
            }`
          }
        >
          <Search size={24} />
        </NavLink>

        <NavLink 
          to="/contacts" 
          className={({ isActive }) => 
            `w-12 h-12 rounded-xl flex items-center justify-center mb-2 transition-colors ${
              isActive ? 'bg-telegram-blue text-white' : 'text-telegram-textSecondary hover:bg-telegram-hover'
            }`
          }
        >
          <Users size={24} />
        </NavLink>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<ChatsPage />} />
          <Route path="/rag" element={<RAGPage />} />
          <Route path="/contacts" element={<ContactsPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
