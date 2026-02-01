import React, { useState, useRef, useEffect } from 'react'
import { API_URL } from '../App'
import { 
  X, Download, Loader2, Check, AlertCircle,
  Settings, ChevronDown, ChevronUp
} from 'lucide-react'

function DownloadModal({ chat, topic, onClose }) {
  const [limit, setLimit] = useState(100)
  const [offsetId, setOffsetId] = useState(0)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [minId, setMinId] = useState(0)
  const [maxId, setMaxId] = useState(0)
  
  const [downloading, setDownloading] = useState(false)
  const [progress, setProgress] = useState([])
  const [status, setStatus] = useState(null) // null, 'downloading', 'complete', 'error'
  const [stats, setStats] = useState({ downloaded: 0, indexed: 0 })
  
  const progressRef = useRef(null)

  useEffect(() => {
    if (progressRef.current) {
      progressRef.current.scrollTop = progressRef.current.scrollHeight
    }
  }, [progress])

  const startDownload = async () => {
    setDownloading(true)
    setStatus('downloading')
    setProgress([])
    setStats({ downloaded: 0, indexed: 0 })

    try {
      const response = await fetch(`${API_URL}/api/messages/download`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: chat.id,
          topic_id: topic?.id || null,
          limit,
          offset_id: offsetId,
          min_id: minId,
          max_id: maxId
        })
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n').filter(Boolean)

        for (const line of lines) {
          try {
            const data = JSON.parse(line)
            
            if (data.type === 'progress') {
              setStats(prev => ({ ...prev, downloaded: data.downloaded }))
              setProgress(prev => [...prev, {
                type: 'download',
                text: `📥 [${data.downloaded}] ${data.message_preview}`
              }])
            } else if (data.type === 'indexed') {
              setStats(prev => ({ ...prev, indexed: prev.indexed + data.count }))
              setProgress(prev => [...prev, {
                type: 'index',
                text: `✅ Проиндексировано: ${data.count} сообщений`
              }])
            } else if (data.type === 'complete') {
              setStatus('complete')
              setProgress(prev => [...prev, {
                type: 'success',
                text: `🎉 Готово! Скачано ${data.total_downloaded} сообщений`
              }])
            } else if (data.type === 'error') {
              setStatus('error')
              setProgress(prev => [...prev, {
                type: 'error',
                text: `❌ Ошибка: ${data.error}`
              }])
            }
          } catch (e) {
            console.error('Parse error:', e)
          }
        }
      }
    } catch (err) {
      setStatus('error')
      setProgress(prev => [...prev, {
        type: 'error',
        text: `❌ Ошибка подключения: ${err.message}`
      }])
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-telegram-sidebar rounded-2xl w-full max-w-lg mx-4 animate-fadeIn overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div>
            <h2 className="text-lg font-semibold">{chat.title}</h2>
            {topic && (
              <p className="text-sm text-telegram-textSecondary">
                Топик: {topic.title}
              </p>
            )}
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-telegram-hover rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Settings */}
        <div className="p-4 space-y-4">
          {/* Limit */}
          <div>
            <label className="block text-sm text-telegram-textSecondary mb-2">
              Количество сообщений
            </label>
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(parseInt(e.target.value) || 100)}
              min={1}
              max={10000}
              disabled={downloading}
              className="w-full px-4 py-2 bg-telegram-bg rounded-xl focus:outline-none focus:ring-2 focus:ring-telegram-blue disabled:opacity-50"
            />
          </div>

          {/* Offset */}
          <div>
            <label className="block text-sm text-telegram-textSecondary mb-2">
              Начать с сообщения ID (0 = с последнего)
            </label>
            <input
              type="number"
              value={offsetId}
              onChange={(e) => setOffsetId(parseInt(e.target.value) || 0)}
              min={0}
              disabled={downloading}
              className="w-full px-4 py-2 bg-telegram-bg rounded-xl focus:outline-none focus:ring-2 focus:ring-telegram-blue disabled:opacity-50"
            />
          </div>

          {/* Advanced settings toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-telegram-accent hover:underline"
          >
            <Settings size={16} />
            Расширенные настройки
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {/* Advanced settings */}
          {showAdvanced && (
            <div className="space-y-4 p-4 bg-telegram-bg rounded-xl">
              <div>
                <label className="block text-sm text-telegram-textSecondary mb-2">
                  Минимальный ID сообщения
                </label>
                <input
                  type="number"
                  value={minId}
                  onChange={(e) => setMinId(parseInt(e.target.value) || 0)}
                  min={0}
                  disabled={downloading}
                  className="w-full px-4 py-2 bg-telegram-sidebar rounded-xl focus:outline-none focus:ring-2 focus:ring-telegram-blue disabled:opacity-50"
                />
              </div>
              <div>
                <label className="block text-sm text-telegram-textSecondary mb-2">
                  Максимальный ID сообщения
                </label>
                <input
                  type="number"
                  value={maxId}
                  onChange={(e) => setMaxId(parseInt(e.target.value) || 0)}
                  min={0}
                  disabled={downloading}
                  className="w-full px-4 py-2 bg-telegram-sidebar rounded-xl focus:outline-none focus:ring-2 focus:ring-telegram-blue disabled:opacity-50"
                />
              </div>
            </div>
          )}
        </div>

        {/* Progress */}
        {progress.length > 0 && (
          <div className="px-4 pb-4">
            <div className="flex items-center gap-4 mb-2 text-sm">
              <span className="text-telegram-textSecondary">
                Скачано: <span className="text-white">{stats.downloaded}</span>
              </span>
              <span className="text-telegram-textSecondary">
                Проиндексировано: <span className="text-telegram-green">{stats.indexed}</span>
              </span>
            </div>
            <div 
              ref={progressRef}
              className="h-48 overflow-y-auto bg-telegram-bg rounded-xl p-3 font-mono text-xs"
            >
              {progress.map((item, i) => (
                <div 
                  key={i} 
                  className={`mb-1 ${
                    item.type === 'error' ? 'text-red-400' :
                    item.type === 'success' ? 'text-telegram-green' :
                    item.type === 'index' ? 'text-telegram-accent' :
                    'text-telegram-textSecondary'
                  }`}
                >
                  {item.text}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="p-4 border-t border-gray-800 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-3 bg-telegram-hover rounded-xl font-medium hover:bg-telegram-bg transition-colors"
          >
            Закрыть
          </button>
          <button
            onClick={startDownload}
            disabled={downloading}
            className="flex-1 py-3 bg-telegram-blue rounded-xl font-medium hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {downloading ? (
              <>
                <Loader2 className="animate-spin" size={20} />
                Скачивание...
              </>
            ) : status === 'complete' ? (
              <>
                <Check size={20} />
                Готово
              </>
            ) : (
              <>
                <Download size={20} />
                Скачать
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default DownloadModal
