import React, { useState, useEffect, useRef, useCallback } from 'react'
import { API_URL } from '../App'
import { 
  Users, Hash, Megaphone, User, 
  ChevronRight, Download, X, Check,
  Loader2, AlertCircle, MessageSquare
} from 'lucide-react'
import AuthModal from './AuthModal'
import DownloadModal from './DownloadModal'

// Глобальный кэш чатов
let chatsCache = null
let chatsCacheTime = 0
const CACHE_TTL = 5 * 60 * 1000 // 5 минут

function ChatsPage() {
  const [authStatus, setAuthStatus] = useState(null)
  const [chats, setChats] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const [selectedChat, setSelectedChat] = useState(null)
  const [topics, setTopics] = useState([])
  const [selectedTopic, setSelectedTopic] = useState(null)
  const [showDownloadModal, setShowDownloadModal] = useState(false)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  
  // Infinite scroll
  const [displayCount, setDisplayCount] = useState(50)
  const listRef = useRef(null)

  useEffect(() => {
    checkAuth()
  }, [])

  // Infinite scroll handler
  const handleScroll = useCallback(() => {
    if (!listRef.current || loadingMore) return
    
    const { scrollTop, scrollHeight, clientHeight } = listRef.current
    if (scrollTop + clientHeight >= scrollHeight - 200) {
      setDisplayCount(prev => Math.min(prev + 30, filteredChats.length))
    }
  }, [loadingMore])

  const checkAuth = async () => {
    try {
      const res = await fetch(`${API_URL}/api/chats/auth/status`)
      const data = await res.json()
      setAuthStatus(data)
      
      if (data.is_authorized) {
        loadChats()
      } else {
        setLoading(false)
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
      setLoading(false)
    }
  }

  const loadChats = async (forceRefresh = false) => {
    // Проверяем кэш
    if (!forceRefresh && chatsCache && Date.now() - chatsCacheTime < CACHE_TTL) {
      setChats(chatsCache)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      const res = await fetch(`${API_URL}/api/chats/`)
      if (!res.ok) throw new Error('Ошибка загрузки чатов')
      const data = await res.json()
      
      // Сохраняем в кэш
      chatsCache = data
      chatsCacheTime = Date.now()
      
      setChats(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const loadTopics = async (chatId) => {
    try {
      const res = await fetch(`${API_URL}/api/chats/${chatId}/topics`)
      if (!res.ok) throw new Error('Ошибка загрузки топиков')
      const data = await res.json()
      setTopics(data)
    } catch (err) {
      console.error(err)
      setTopics([])
    }
  }

  const handleChatClick = async (chat) => {
    setSelectedChat(chat)
    setSelectedTopic(null)
    
    if (chat.is_forum) {
      await loadTopics(chat.id)
    } else {
      setTopics([])
      setShowDownloadModal(true)
    }
  }

  const handleTopicClick = (topic) => {
    setSelectedTopic(topic)
    setShowDownloadModal(true)
  }

  const handleBackToChats = () => {
    setSelectedChat(null)
    setTopics([])
    setSelectedTopic(null)
  }

  const getChatIcon = (type, isForum) => {
    if (isForum) return <Hash size={20} />
    switch (type) {
      case 'channel': return <Megaphone size={20} />
      case 'group':
      case 'supergroup': return <Users size={20} />
      default: return <User size={20} />
    }
  }

  const getAvatarGradient = (id) => {
    const gradients = ['avatar-gradient-1', 'avatar-gradient-2', 'avatar-gradient-3', 
                       'avatar-gradient-4', 'avatar-gradient-5', 'avatar-gradient-6']
    return gradients[Math.abs(id) % gradients.length]
  }

  const getInitials = (title) => {
    return title.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
  }

  const filteredChats = chats.filter(chat => 
    chat.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Reset display count when search changes
  useEffect(() => {
    setDisplayCount(50)
  }, [searchQuery])

  const displayedChats = filteredChats.slice(0, displayCount)

  if (!authStatus?.is_authorized) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8">
        <div className="text-center max-w-md">
          <div className="w-20 h-20 rounded-full bg-telegram-blue flex items-center justify-center mx-auto mb-6">
            <MessageSquare size={40} />
          </div>
          <h1 className="text-2xl font-semibold mb-2">Telegram LeadGen</h1>
          <p className="text-telegram-textSecondary mb-6">
            Войдите в свой Telegram аккаунт, чтобы начать скачивать сообщения
          </p>
          <button
            onClick={() => setShowAuthModal(true)}
            className="px-6 py-3 bg-telegram-blue rounded-xl font-medium hover:bg-opacity-90 transition-colors"
          >
            Войти в Telegram
          </button>
        </div>
        
        {showAuthModal && (
          <AuthModal 
            onClose={() => setShowAuthModal(false)}
            onSuccess={() => {
              setShowAuthModal(false)
              checkAuth()
            }}
          />
        )}
      </div>
    )
  }

  return (
    <div className="h-full flex">
      {/* Chat list */}
      <div className="w-96 bg-telegram-sidebar border-r border-gray-800 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-semibold">
              {selectedChat && topics.length > 0 ? (
                <button 
                  onClick={handleBackToChats}
                  className="flex items-center gap-2 hover:text-telegram-accent"
                >
                  <ChevronRight size={20} className="rotate-180" />
                  {selectedChat.title}
                </button>
              ) : (
                'Чаты'
              )}
            </h1>
            <span className="text-sm text-telegram-textSecondary">
              {authStatus?.username && `@${authStatus.username}`}
            </span>
          </div>
          
          {/* Search */}
          <input
            type="text"
            placeholder="Поиск..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-4 py-2 bg-telegram-bg rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-telegram-blue"
          />
          
          {!selectedChat && chats.length > 0 && (
            <p className="text-xs text-telegram-textSecondary mt-2">
              {filteredChats.length} чатов
              {displayCount < filteredChats.length && ` (показано ${displayCount})`}
            </p>
          )}
        </div>

        {/* List with infinite scroll */}
        <div 
          ref={listRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto"
        >
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="animate-spin text-telegram-accent" size={32} />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-32 text-telegram-textSecondary">
              <AlertCircle size={32} className="mb-2" />
              <p>{error}</p>
            </div>
          ) : selectedChat && topics.length > 0 ? (
            // Topics list
            topics.map(topic => (
              <div
                key={topic.id}
                onClick={() => handleTopicClick(topic)}
                className="flex items-center gap-3 px-4 py-3 hover:bg-telegram-hover cursor-pointer transition-colors"
              >
                <div className={`avatar w-12 h-12 ${getAvatarGradient(topic.id)}`}>
                  <Hash size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="font-medium truncate">{topic.title}</span>
                  </div>
                  <p className="text-sm text-telegram-textSecondary truncate">
                    Топик форума
                  </p>
                </div>
                <ChevronRight size={20} className="text-telegram-textSecondary" />
              </div>
            ))
          ) : (
            // Chats list with infinite scroll
            <>
              {displayedChats.map(chat => (
                <div
                  key={chat.id}
                  onClick={() => handleChatClick(chat)}
                  className={`flex items-center gap-3 px-4 py-3 hover:bg-telegram-hover cursor-pointer transition-colors ${
                    selectedChat?.id === chat.id ? 'bg-telegram-active' : ''
                  }`}
                >
                  <div className={`avatar ${getAvatarGradient(chat.id)}`}>
                    {getInitials(chat.title)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="font-medium truncate flex items-center gap-2">
                        {getChatIcon(chat.type, chat.is_forum)}
                        {chat.title}
                      </span>
                      {chat.is_forum && (
                        <span className="text-xs text-telegram-accent">Форум</span>
                      )}
                    </div>
                    <p className="text-sm text-telegram-textSecondary truncate">
                      {chat.username ? `@${chat.username}` : `ID: ${chat.id}`}
                      {chat.members_count && ` • ${chat.members_count.toLocaleString()} участников`}
                    </p>
                  </div>
                  {chat.is_forum ? (
                    <ChevronRight size={20} className="text-telegram-textSecondary" />
                  ) : (
                    <Download size={18} className="text-telegram-textSecondary" />
                  )}
                </div>
              ))}
              
              {/* Loading more indicator */}
              {displayCount < filteredChats.length && (
                <div className="py-4 text-center text-telegram-textSecondary text-sm">
                  <Loader2 className="animate-spin inline mr-2" size={16} />
                  Загрузка...
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Right panel - info or empty state */}
      <div className="flex-1 flex items-center justify-center bg-telegram-bg">
        {selectedChat && !showDownloadModal ? (
          <div className="text-center max-w-md p-8">
            <div className={`avatar w-24 h-24 mx-auto mb-4 text-3xl ${getAvatarGradient(selectedChat.id)}`}>
              {getInitials(selectedChat.title)}
            </div>
            <h2 className="text-2xl font-semibold mb-2">{selectedChat.title}</h2>
            <p className="text-telegram-textSecondary mb-4">
              {selectedChat.is_forum 
                ? 'Выберите топик для скачивания сообщений'
                : 'Нажмите на чат в списке, чтобы скачать сообщения'
              }
            </p>
            {selectedChat.members_count && (
              <p className="text-sm text-telegram-textSecondary">
                {selectedChat.members_count.toLocaleString()} участников
              </p>
            )}
          </div>
        ) : !selectedChat ? (
          <div className="text-center text-telegram-textSecondary">
            <MessageSquare size={64} className="mx-auto mb-4 opacity-50" />
            <p>Выберите чат для скачивания сообщений</p>
          </div>
        ) : null}
      </div>

      {/* Download modal */}
      {showDownloadModal && (
        <DownloadModal
          chat={selectedChat}
          topic={selectedTopic}
          onClose={() => {
            setShowDownloadModal(false)
            setSelectedTopic(null)
          }}
        />
      )}
    </div>
  )
}

export default ChatsPage
