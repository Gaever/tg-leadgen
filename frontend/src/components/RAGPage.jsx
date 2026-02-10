import React, { useState, useEffect, useRef } from 'react'
import { API_URL } from '../App'
import { 
  Search, Send, Loader2, Database, 
  ExternalLink, Copy, Check, Filter, Download,
  Users, Trash2, X
} from 'lucide-react'
import ContactModal from './ContactModal'

function RAGPage() {
  const [sources, setSources] = useState([])
  const [selectedSources, setSelectedSources] = useState([])
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [showSources, setShowSources] = useState(true)
  const [stats, setStats] = useState(null)
  const [topK, setTopK] = useState(10)
  const [selectedContactId, setSelectedContactId] = useState(null)
  const [deletingSource, setDeletingSource] = useState(null)
  const [highlightedCid, setHighlightedCid] = useState(null)
  const [summaryCopied, setSummaryCopied] = useState(false)
  
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const highlightTimeoutRef = useRef(null)

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

  const exportMessages = () => {
    window.open(`${API_URL}/api/rag/messages/export`, '_blank')
  }

  const exportContacts = () => {
    window.open(`${API_URL}/api/rag/contacts/export`, '_blank')
  }

  const deleteSource = async (source) => {
    if (!confirm(`Удалить "${source.chat_title}"? Это удалит ${source.messages_count} сообщений из базы.`)) {
      return
    }
    
    setDeletingSource(source.chat_id)
    try {
      const url = source.topic_id 
        ? `${API_URL}/api/rag/sources/${source.chat_id}?topic_id=${source.topic_id}`
        : `${API_URL}/api/rag/sources/${source.chat_id}`
      
      const res = await fetch(url, { method: 'DELETE' })
      const data = await res.json()
      
      if (data.success) {
        loadSources()
        loadStats()
      } else {
        alert('Ошибка удаления: ' + data.error)
      }
    } catch (err) {
      alert('Ошибка: ' + err.message)
    } finally {
      setDeletingSource(null)
    }
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
      const selectedChatIds = [...new Set(selectedSources)]
      const [searchRes, answerRes] = await Promise.all([
        fetch(`${API_URL}/api/rag/search?min_text_length=50&expand_query=true`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: query,
            sources: selectedChatIds,
            top_k: topK
          })
        }),
        fetch(`${API_URL}/api/rag/answer`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: query,
            filters: { chatIds: selectedChatIds },
            topK: topK,
            answerStyle: 'standard'
          })
        })
      ])

      const data = await searchRes.json()
      const answerData = answerRes.ok ? await answerRes.json() : { error: 'answer_failed' }

      const botMessage = {
        type: 'bot',
        results: data.results,
        totalFound: data.total_found,
        answer: answerData.answer,
        citations: answerData.citations,
        retrieval: answerData.retrieval,
        answerError: answerData.error,
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

  const handleCitationClick = (cid) => {
    const element = document.getElementById(`citation-${cid}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
      setHighlightedCid(cid)
      if (highlightTimeoutRef.current) {
        clearTimeout(highlightTimeoutRef.current)
      }
      highlightTimeoutRef.current = setTimeout(() => {
        setHighlightedCid(null)
      }, 2500)
    }
  }

  const handleCopySummary = async (markdown) => {
    if (!markdown) return
    await copyToClipboard(markdown)
    setSummaryCopied(true)
    setTimeout(() => setSummaryCopied(false), 2000)
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
          
          <div className="flex flex-wrap gap-2 text-xs">
            <button 
              onClick={selectAllSources}
              className="text-telegram-accent hover:underline"
            >
              Все
            </button>
            <span className="text-telegram-textSecondary">|</span>
            <button 
              onClick={deselectAllSources}
              className="text-telegram-accent hover:underline"
            >
              Снять
            </button>
            <span className="text-telegram-textSecondary">|</span>
            <button
              onClick={exportMessages}
              className="text-telegram-accent hover:underline flex items-center gap-1"
            >
              <Download size={12} />
              JSON
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
              <div
                key={`${source.chat_id}_${source.topic_id || ''}`}
                className="flex items-center gap-2 p-2 rounded-lg hover:bg-telegram-hover transition-colors group"
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
                <button
                  onClick={() => deleteSource(source)}
                  disabled={deletingSource === source.chat_id}
                  className="p-1.5 text-telegram-textSecondary hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-50"
                  title="Удалить источник"
                >
                  {deletingSource === source.chat_id ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Trash2 size={14} />
                  )}
                </button>
              </div>
            ))
          )}
        </div>

        {/* Stats & Export */}
        <div className="p-4 border-t border-gray-800 space-y-3">
          {stats?.contacts_count > 0 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-telegram-textSecondary flex items-center gap-2">
                <Users size={14} />
                {stats.contacts_count} контактов
              </span>
              <button 
                onClick={exportContacts}
                className="text-telegram-accent hover:underline flex items-center gap-1 text-xs"
              >
                <Download size={12} />
                Экспорт
              </button>
            </div>
          )}
          
          <div>
            <label className="block text-sm text-telegram-textSecondary mb-2">
              Результатов: {topK}
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
                  Введите запрос для поиска релевантных сообщений. Запрос автоматически расширяется для лучших результатов.
                </p>
                <div className="text-xs bg-telegram-sidebar p-3 rounded-lg text-left space-y-1">
                  <p>💡 <strong>Примеры запросов:</strong></p>
                  <p>• "онлайн школы, курсы, обучение"</p>
                  <p>• "ищу подрядчика, нужен специалист"</p>
                  <p>• "маркетинг, продвижение, реклама"</p>
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

                    <AnswerSummary
                      answer={msg.answer}
                      citations={msg.citations}
                      answerError={msg.answerError}
                      retrieval={msg.retrieval}
                      onCitationClick={handleCitationClick}
                      onCopySummary={handleCopySummary}
                      summaryCopied={summaryCopied}
                    />
                    
                    {msg.results.map((result, j) => {
                      const citationMatch = msg.citations?.find(
                        (citation) =>
                          citation.message_id === result.message.id &&
                          citation.chat_id === result.message.chat_id
                      )
                      const cid = citationMatch?.cid
                      return (
                      <MessageResult 
                        key={j} 
                        result={result} 
                        copyToClipboard={copyToClipboard}
                        onContactClick={setSelectedContactId}
                        cid={cid}
                        highlighted={cid && cid === highlightedCid}
                      />
                      )
                    })}
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
              Поиск (с расширением запроса)...
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

// Компонент результата поиска
function AnswerSummary({ answer, citations, answerError, retrieval, onCitationClick, onCopySummary, summaryCopied }) {
  const citationLookup = new Map()
  citations?.forEach((citation) => {
    citationLookup.set(citation.cid, citation)
  })

  if (answerError) {
    return (
      <div className="message-bubble border border-yellow-500/40 bg-yellow-500/10 text-yellow-200 text-sm">
        Не удалось собрать сводку. Показываем только список источников.
      </div>
    )
  }

  if (!answer) {
    return null
  }

  const { summary, sections = [], rejected = [], markdown } = answer

  return (
    <div className="message-bubble border border-telegram-blue/30 bg-telegram-sidebar space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h3 className="text-base font-semibold">Сводка по запросу</h3>
          {retrieval && (
            <p className="text-xs text-telegram-textSecondary">
              Использовано источников: {retrieval.used} из {retrieval.topK} • {retrieval.latencyMs}мс
            </p>
          )}
        </div>
        <button
          onClick={() => onCopySummary(markdown)}
          className="text-xs text-telegram-accent hover:underline flex items-center gap-1"
        >
          {summaryCopied ? (
            <>
              <Check size={12} />
              Скопировано
            </>
          ) : (
            <>
              <Copy size={12} />
              Скопировать сводку
            </>
          )}
        </button>
      </div>

      {summary && <p className="text-sm text-telegram-textSecondary">{summary}</p>}

      <div className="space-y-4">
        {sections.map((section, idx) => (
          <div key={`${section.title}-${idx}`} className="space-y-2">
            <h4 className="font-semibold text-sm text-white">{section.title}</h4>
            <div className="space-y-3">
              {section.items?.map((item, itemIdx) => (
                <div key={`${section.title}-${itemIdx}`} className="border border-gray-700 rounded-lg p-3">
                  <div className="flex flex-col gap-1 text-sm">
                    <div className="font-medium text-telegram-accent">
                      {item.lead?.username || item.lead?.who || 'Кандидат'}
                    </div>
                    {item.lead?.need && (
                      <div className="text-white">{item.lead.need}</div>
                    )}
                    {item.lead?.intent && (
                      <div className="text-xs text-telegram-textSecondary">{item.lead.intent}</div>
                    )}
                    {item.why_fit?.length > 0 && (
                      <ul className="list-disc list-inside text-xs text-telegram-textSecondary space-y-1">
                        {item.why_fit.map((reason, reasonIdx) => (
                          <li key={reasonIdx}>{reason}</li>
                        ))}
                      </ul>
                    )}
                    {item.next_step && (
                      <div className="text-xs text-telegram-textSecondary">
                        Следующий шаг: {item.next_step}
                      </div>
                    )}
                  </div>
                  {item.citations?.length > 0 && (
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      {item.citations.map((cid) => {
                        const citation = citationLookup.get(cid)
                        return (
                          <div key={cid} className="flex items-center gap-1">
                            <button
                              onClick={() => onCitationClick(cid)}
                              className="text-xs px-2 py-1 rounded-full bg-telegram-blue/20 text-telegram-blue hover:bg-telegram-blue/30"
                            >
                              [{cid}]
                            </button>
                            {citation?.tg_link && (
                              <a
                                href={citation.tg_link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-telegram-accent hover:underline flex items-center gap-1"
                              >
                                <ExternalLink size={12} />
                              </a>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {rejected?.length > 0 && (
        <div className="space-y-2">
          <h4 className="font-semibold text-sm text-white">Не подошли</h4>
          <ul className="space-y-2 text-xs text-telegram-textSecondary">
            {rejected.map((item, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <span>{item.reason}</span>
                {item.citations?.map((cid) => (
                  <button
                    key={cid}
                    onClick={() => onCitationClick(cid)}
                    className="text-xs px-2 py-1 rounded-full bg-telegram-blue/20 text-telegram-blue hover:bg-telegram-blue/30"
                  >
                    [{cid}]
                  </button>
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function MessageResult({ result, copyToClipboard, onContactClick, cid, highlighted }) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const handleCopy = async () => {
    const data = {
      message_id: result.message.id,
      chat_id: result.message.chat_id,
      author_id: result.message.author.id,
      author_username: result.message.author.username,
      text: result.message.text,
      date: result.message.date,
      telegram_link: getTelegramLink()
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

  const getTelegramLink = () => {
    const { chat_id, chat_username, id } = result.message
    if (chat_username) {
      return `https://t.me/${chat_username}/${id}`
    }
    let cleanId = String(chat_id)
    if (cleanId.startsWith('-100')) {
      cleanId = cleanId.slice(4)
    }
    return `https://t.me/c/${cleanId}/${id}`
  }

  return (
    <div
      id={cid ? `citation-${cid}` : undefined}
      className={`message-bubble ${highlighted ? 'message-highlight' : ''}`}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <button 
          onClick={() => onContactClick(result.message.author.id)}
          className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${getAvatarGradient(result.message.author.id)} hover:opacity-80 transition-opacity`}
        >
          {getAuthorName()[0].toUpperCase()}
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <button 
              onClick={() => onContactClick(result.message.author.id)}
              className="font-medium text-telegram-accent hover:underline"
            >
              {getAuthorName()}
            </button>
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
        <div className="text-right flex flex-col items-end gap-1">
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

      {/* Footer with links and actions */}
      <div className="flex items-center justify-between pt-2 border-t border-gray-700 text-xs flex-wrap gap-2">
        <div className="flex items-center gap-3 text-telegram-textSecondary">
          <span>msg: {result.message.id}</span>
          {cid && <span>[{cid}]</span>}
          {result.message.views && (
            <span>👁 {result.message.views}</span>
          )}
          <a
            href={getTelegramLink()}
            target="_blank"
            rel="noopener noreferrer"
            className="text-telegram-accent hover:underline flex items-center gap-1"
          >
            <ExternalLink size={12} />
            Открыть в TG
          </a>
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
              JSON
            </>
          )}
        </button>
      </div>
    </div>
  )
}

export default RAGPage
