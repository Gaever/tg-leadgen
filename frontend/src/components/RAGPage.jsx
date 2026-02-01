import React, { useState, useEffect, useRef } from 'react'
import { API_URL } from '../App'
import { 
  Search, Send, Loader2, Database, 
  ChevronDown, ChevronUp, User, ExternalLink,
  Copy, Check, MessageSquare, Filter
} from 'lucide-react'

function RAGPage() {
  const [sources, setSources] = useState([])
  const [selectedSources, setSelectedSources] = useState([])
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [showSources, setShowSources] = useState(true)
  const [stats, setStats] = useState(null)
  const [topK, setTopK] = useState(10)
  
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    loadSources()
    loadStats()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadSources = async () => {
    try {
      const res = await fetch(`${API_URL}/api/rag/sources`)
      const data = await res.json()
      setSources(data)
      // Select all sources by default
      setSelectedSources(data.map(s => s.chat_id))
    } catch (err) {
      console.error('Error loading sources:', err)
    }
  }

  const loadStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/rag/stats`)
      const data = await res.json()
      setStats(data)
    } catch (err) {
      console.error('Error loading stats:', err)
    }
  }

  const toggleSource = (chatId) => {
    setSelectedSources(prev => 
      prev.includes(chatId) 
        ? prev.filter(id => id !== chatId)
        : [...prev, chatId]
    )
  }

  const selectAllSources = () => {
    setSelectedSources(sources.map(s => s.chat_id))
  }

  const deselectAllSources = () => {
    setSelectedSources([])
  }

  const handleSearch = async () => {
    if (!query.trim() || selectedSources.length === 0) return

    const userMessage = {
      type: 'user',
      text: query,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])
    setQuery('')
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/api/rag/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          sources: [...new Set(selectedSources)],
          top_k: topK
        })
      })
      
      const data = await res.json()
      
      const botMessage = {
        type: 'bot',
        results: data.results,
        totalFound: data.total_found,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, botMessage])
    } catch (err) {
      const errorMessage = {
        type: 'error',
        text: 'Ошибка поиска: ' + err.message,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSearch()
    }
  }

  const copyToClipboard = async (text) => {
    await navigator.clipboard.writeText(text)
  }

  const getAvatarGradient = (id) => {
    const gradients = ['avatar-gradient-1', 'avatar-gradient-2', 'avatar-gradient-3', 
                       'avatar-gradient-4', 'avatar-gradient-5', 'avatar-gradient-6']
    return gradients[Math.abs(id) % gradients.length]
  }

  return (
    <div className="h-full flex">
      {/* Sources sidebar */}
      <div className={`${showSources ? 'w-80' : 'w-0'} bg-telegram-sidebar border-r border-gray-800 flex flex-col transition-all overflow-hidden`}>
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold flex items-center gap-2">
              <Database size={18} />
              Источники
            </h2>
            {stats && (
              <span className="text-xs text-telegram-textSecondary">
                {stats.embeddings_count?.toLocaleString()} сообщений
              </span>
            )}
          </div>
          
          <div className="flex gap-2 text-xs">
            <button 
              onClick={selectAllSources}
              className="text-telegram-accent hover:underline"
            >
              Выбрать все
            </button>
            <span className="text-telegram-textSecondary">|</span>
            <button 
              onClick={deselectAllSources}
              className="text-telegram-accent hover:underline"
            >
              Снять все
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {sources.length === 0 ? (
            <div className="text-center text-telegram-textSecondary py-8">
              <Database size={32} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm">Нет скачанных чатов</p>
              <p className="text-xs mt-1">Скачайте сообщения в разделе "Чаты"</p>
            </div>
          ) : (
            sources.map(source => (
              <label
                key={`${source.chat_id}_${source.topic_id || ''}`}
                className="flex items-center gap-3 p-2 rounded-lg hover:bg-telegram-hover cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedSources.includes(source.chat_id)}
                  onChange={() => toggleSource(source.chat_id)}
                  className="checkbox-telegram"
                />
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{source.chat_title}</p>
                  {source.topic_title && (
                    <p className="text-xs text-telegram-textSecondary truncate">
                      {source.topic_title}
                    </p>
                  )}
                  <p className="text-xs text-telegram-textSecondary">
                    {source.messages_count.toLocaleString()} сообщений
                  </p>
                </div>
              </label>
            ))
          )}
        </div>

        {/* Top K setting */}
        <div className="p-4 border-t border-gray-800">
          <label className="block text-sm text-telegram-textSecondary mb-2">
            Количество результатов: {topK}
          </label>
          <input
            type="range"
            min={1}
            max={50}
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value))}
            className="w-full"
          />
        </div>
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col bg-telegram-bg">
        {/* Header */}
        <div className="p-4 border-b border-gray-800 flex items-center gap-4">
          <button
            onClick={() => setShowSources(!showSources)}
            className="p-2 hover:bg-telegram-hover rounded-lg transition-colors"
          >
            <Filter size={20} />
          </button>
          <div>
            <h1 className="font-semibold">RAG Поиск</h1>
            <p className="text-sm text-telegram-textSecondary">
              {selectedSources.length} источников выбрано
            </p>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <div className="text-center text-telegram-textSecondary max-w-md">
                <Search size={48} className="mx-auto mb-4 opacity-50" />
                <h2 className="text-xl font-semibold text-white mb-2">RAG Поиск по сообщениям</h2>
                <p className="text-sm mb-4">
                  Введите запрос для поиска релевантных сообщений в выбранных источниках.
                  Например: "найди посты про онлайн школы" или "авторы которые пишут про маркетинг"
                </p>
                <div className="text-xs bg-telegram-sidebar p-3 rounded-lg">
                  💡 Результаты показывают оригинальные сообщения из базы с id авторов
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className="animate-fadeIn">
                {msg.type === 'user' && (
                  <div className="flex justify-end">
                    <div className="message-bubble own max-w-2xl">
                      <p>{msg.text}</p>
                    </div>
                  </div>
                )}

                {msg.type === 'bot' && (
                  <div className="space-y-3">
                    <div className="text-sm text-telegram-textSecondary">
                      Найдено {msg.totalFound} результатов
                    </div>
                    
                    {msg.results.map((result, j) => (
                      <MessageResult key={j} result={result} copyToClipboard={copyToClipboard} />
                    ))}
                  </div>
                )}

                {msg.type === 'error' && (
                  <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
                    {msg.text}
                  </div>
                )}
              </div>
            ))
          )}
          
          {loading && (
            <div className="flex items-center gap-2 text-telegram-textSecondary">
              <Loader2 className="animate-spin" size={20} />
              Поиск...
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="p-4 border-t border-gray-800">
          <div className="flex gap-3">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Введите поисковый запрос..."
              disabled={loading || selectedSources.length === 0}
              className="flex-1 px-4 py-3 bg-telegram-sidebar rounded-xl focus:outline-none focus:ring-2 focus:ring-telegram-blue disabled:opacity-50"
            />
            <button
              onClick={handleSearch}
              disabled={loading || !query.trim() || selectedSources.length === 0}
              className="px-6 py-3 bg-telegram-blue rounded-xl hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <Send size={20} />
              )}
            </button>
          </div>
          {selectedSources.length === 0 && (
            <p className="text-xs text-red-400 mt-2">Выберите хотя бы один источник</p>
          )}
        </div>
      </div>
    </div>
  )
}

// Separate component for message result
function MessageResult({ result, copyToClipboard }) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const handleCopy = async () => {
    const data = {
      message_id: result.message.id,
      chat_id: result.message.chat_id,
      author_id: result.message.author.id,
      author_username: result.message.author.username,
      text: result.message.text,
      date: result.message.date
    }
    await copyToClipboard(JSON.stringify(data, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getAvatarGradient = (id) => {
    const gradients = ['avatar-gradient-1', 'avatar-gradient-2', 'avatar-gradient-3', 
                       'avatar-gradient-4', 'avatar-gradient-5', 'avatar-gradient-6']
    return gradients[Math.abs(id) % gradients.length]
  }

  const getAuthorName = () => {
    const { author } = result.message
    if (author.username) return `@${author.username}`
    if (author.first_name) return `${author.first_name} ${author.last_name || ''}`.trim()
    return `User ${author.id}`
  }

  return (
    <div className="message-bubble">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${getAvatarGradient(result.message.author.id)}`}>
          {getAuthorName()[0].toUpperCase()}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-telegram-accent">{getAuthorName()}</span>
            <span className="text-xs text-telegram-textSecondary">
              ID: {result.message.author.id}
            </span>
          </div>
          <div className="text-xs text-telegram-textSecondary flex items-center gap-2">
            <span>{result.message.chat_title}</span>
            {result.message.topic_title && (
              <>
                <span>•</span>
                <span>{result.message.topic_title}</span>
              </>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-telegram-textSecondary">
            {formatDate(result.message.date)}
          </div>
          <div className="text-xs text-telegram-green">
            Score: {(result.score * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Message text */}
      <div className="mb-2">
        <p className={`whitespace-pre-wrap ${!expanded && result.message.text.length > 300 ? 'line-clamp-4' : ''}`}>
          {result.message.text}
        </p>
        {result.message.text.length > 300 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-telegram-accent hover:underline mt-1"
          >
            {expanded ? 'Свернуть' : 'Показать полностью'}
          </button>
        )}
      </div>

      {/* Footer with IDs and actions */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-700 text-xs">
        <div className="flex items-center gap-3 text-telegram-textSecondary">
          <span>msg_id: {result.message.id}</span>
          <span>chat_id: {result.message.chat_id}</span>
          {result.message.views && (
            <span>👁 {result.message.views}</span>
          )}
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-telegram-accent hover:underline"
        >
          {copied ? (
            <>
              <Check size={14} />
              Скопировано
            </>
          ) : (
            <>
              <Copy size={14} />
              Копировать JSON
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default RAGPage
