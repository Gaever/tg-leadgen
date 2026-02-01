import React, { useState, useEffect, useRef } from 'react'
import { API_URL } from '../App'
import { 
  Search, Send, Loader2, Users, 
  ExternalLink, Download, MessageSquare,
  Megaphone, AtSign, Calendar
} from 'lucide-react'
import ContactModal from './ContactModal'

function ContactsPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [topK, setTopK] = useState(20)
  const [selectedContactId, setSelectedContactId] = useState(null)
  const [hasSearched, setHasSearched] = useState(false)
  
  const inputRef = useRef(null)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/rag/stats`)
      const data = await res.json()
      setStats(data)
    } catch (err) {
      console.error('Error loading stats:', err)
    }
  }

  const handleSearch = async () => {
    if (!query.trim()) return

    setLoading(true)
    setHasSearched(true)

    try {
      const res = await fetch(`${API_URL}/api/rag/contacts/search?expand_query=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          top_k: topK
        })
      })
      
      const data = await res.json()
      setResults(data.results || [])
    } catch (err) {
      console.error('Search error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const exportContacts = () => {
    window.open(`${API_URL}/api/rag/contacts/export`, '_blank')
  }

  const getAvatarGradient = (id) => {
    const gradients = ['avatar-gradient-1', 'avatar-gradient-2', 'avatar-gradient-3', 
                       'avatar-gradient-4', 'avatar-gradient-5', 'avatar-gradient-6']
    return gradients[Math.abs(id) % gradients.length]
  }

  const getInitials = (contact) => {
    const name = contact.full_name || contact.username || ''
    return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() || '?'
  }

  const getTelegramLink = (contact) => {
    if (contact.username) {
      return `https://t.me/${contact.username}`
    }
    return `tg://user?id=${contact.id}`
  }

  return (
    <div className="h-full flex flex-col bg-telegram-bg">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <Users size={24} />
              Поиск по контактам
            </h1>
            {stats && (
              <p className="text-sm text-telegram-textSecondary">
                {stats.contacts_count || 0} контактов в базе
              </p>
            )}
          </div>
          <button
            onClick={exportContacts}
            className="px-4 py-2 bg-telegram-hover rounded-xl hover:bg-telegram-sidebar transition-colors flex items-center gap-2 text-sm"
          >
            <Download size={16} />
            Экспорт JSON
          </button>
        </div>

        {/* Search input */}
        <div className="flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Поиск по bio: онлайн школы, маркетинг, курсы..."
            disabled={loading}
            className="flex-1 px-4 py-3 bg-telegram-sidebar rounded-xl focus:outline-none focus:ring-2 focus:ring-telegram-blue disabled:opacity-50"
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-6 py-3 bg-telegram-blue rounded-xl hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {loading ? (
              <Loader2 className="animate-spin" size={20} />
            ) : (
              <Search size={20} />
            )}
          </button>
        </div>

        {/* Settings */}
        <div className="mt-3 flex items-center gap-4">
          <label className="text-sm text-telegram-textSecondary">
            Результатов: {topK}
          </label>
          <input
            type="range"
            min={5}
            max={50}
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
            className="w-32"
          />
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4">
        {!hasSearched ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-telegram-textSecondary max-w-md">
              <Users size={48} className="mx-auto mb-4 opacity-50" />
              <h2 className="text-xl font-semibold text-white mb-2">Семантический поиск по контактам</h2>
              <p className="text-sm mb-4">
                Ищите людей по содержимому их bio. Запрос автоматически расширяется синонимами.
              </p>
              <div className="text-xs bg-telegram-sidebar p-3 rounded-lg text-left space-y-1">
                <p>💡 <strong>Примеры запросов:</strong></p>
                <p>• "онлайн школы, инфобизнес, курсы"</p>
                <p>• "маркетолог, SMM, продвижение"</p>
                <p>• "разработчик, программист, IT"</p>
                <p>• "CEO, основатель, предприниматель"</p>
              </div>
            </div>
          </div>
        ) : results.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-telegram-textSecondary">
              <Users size={48} className="mx-auto mb-4 opacity-50" />
              <p>Контакты не найдены</p>
              <p className="text-xs mt-1">Попробуйте другой запрос</p>
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-sm text-telegram-textSecondary mb-4">
              Найдено {results.length} контактов
            </p>
            
            {results.map((item, i) => (
              <div
                key={item.contact.id}
                onClick={() => setSelectedContactId(item.contact.id)}
                className="flex items-center gap-4 p-4 bg-telegram-sidebar rounded-xl hover:bg-telegram-hover cursor-pointer transition-colors"
              >
                {/* Avatar */}
                <div className={`w-14 h-14 rounded-full flex items-center justify-center text-lg font-medium ${getAvatarGradient(item.contact.id)}`}>
                  {getInitials(item.contact)}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">
                      {item.contact.full_name || `User ${item.contact.id}`}
                    </span>
                    {item.contact.username && (
                      <span className="text-telegram-accent text-sm">@{item.contact.username}</span>
                    )}
                  </div>
                  
                  {item.contact.bio && (
                    <p className="text-sm text-telegram-textSecondary truncate mt-1">
                      {item.contact.bio}
                    </p>
                  )}

                  <div className="flex items-center gap-3 mt-1 text-xs text-telegram-textSecondary">
                    {item.messages_count > 0 && (
                      <span className="flex items-center gap-1">
                        <MessageSquare size={12} />
                        {item.messages_count}
                      </span>
                    )}
                    {item.contact.personal_channel_title && (
                      <span className="flex items-center gap-1">
                        <Megaphone size={12} />
                        Канал
                      </span>
                    )}
                    {item.contact.birthday && (
                      <span className="flex items-center gap-1">
                        <Calendar size={12} />
                        {item.contact.birthday}
                      </span>
                    )}
                  </div>
                </div>

                {/* Score */}
                <div className="text-right">
                  <div className="text-xs text-telegram-green">
                    {(item.score * 100).toFixed(1)}%
                  </div>
                  <a
                    href={getTelegramLink(item.contact)}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-telegram-accent hover:underline text-xs flex items-center gap-1 mt-1"
                  >
                    <ExternalLink size={12} />
                    TG
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Contact Modal */}
      {selectedContactId && (
        <ContactModal
          userId={selectedContactId}
          onClose={() => setSelectedContactId(null)}
        />
      )}
    </div>
  )
}

export default ContactsPage
