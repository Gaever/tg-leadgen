import React, { useState, useEffect } from 'react'
import { API_URL } from '../App'
import { 
  X, User, AtSign, Phone, Calendar, 
  MessageSquare, ExternalLink, Loader2,
  Megaphone, Link2, Copy, Check
} from 'lucide-react'

function ContactModal({ userId, onClose }) {
  const [contact, setContact] = useState(null)
  const [messagesCount, setMessagesCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    loadContact()
  }, [userId])

  const loadContact = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_URL}/api/rag/contacts/${userId}`)
      const data = await res.json()
      
      if (data.error) {
        setError(data.error)
      } else {
        setContact(data.contact)
        setMessagesCount(data.messages_count || 0)
      }
    } catch (err) {
      setError('Ошибка загрузки контакта')
    } finally {
      setLoading(false)
    }
  }

  const getAvatarGradient = (id) => {
    const gradients = ['avatar-gradient-1', 'avatar-gradient-2', 'avatar-gradient-3', 
                       'avatar-gradient-4', 'avatar-gradient-5', 'avatar-gradient-6']
    return gradients[Math.abs(id) % gradients.length]
  }

  const getTelegramLink = () => {
    if (contact?.username) {
      return `https://t.me/${contact.username}`
    }
    return `tg://user?id=${userId}`
  }

  const copyToClipboard = async () => {
    const text = JSON.stringify(contact, null, 2)
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const getInitials = () => {
    if (!contact) return '?'
    const name = contact.full_name || contact.username || ''
    return name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase() || '?'
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-telegram-sidebar rounded-2xl w-full max-w-md mx-4 animate-fadeIn overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {loading ? (
          <div className="p-8 flex items-center justify-center">
            <Loader2 className="animate-spin text-telegram-accent" size={32} />
          </div>
        ) : error ? (
          <div className="p-8">
            <div className="text-center text-telegram-textSecondary">
              <User size={48} className="mx-auto mb-4 opacity-50" />
              <p>{error}</p>
              <p className="text-xs mt-2">ID: {userId}</p>
            </div>
            <button
              onClick={onClose}
              className="w-full mt-4 py-3 bg-telegram-hover rounded-xl font-medium"
            >
              Закрыть
            </button>
          </div>
        ) : contact ? (
          <>
            {/* Header with avatar */}
            <div className="relative">
              <div className="h-24 bg-gradient-to-r from-telegram-blue to-telegram-accent" />
              <button 
                onClick={onClose}
                className="absolute top-3 right-3 p-2 bg-black/30 hover:bg-black/50 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
              <div className={`absolute -bottom-12 left-1/2 -translate-x-1/2 w-24 h-24 rounded-full ${getAvatarGradient(userId)} flex items-center justify-center text-3xl font-semibold border-4 border-telegram-sidebar`}>
                {getInitials()}
              </div>
            </div>

            {/* Info */}
            <div className="pt-14 px-6 pb-6">
              {/* Name */}
              <div className="text-center mb-4">
                <h2 className="text-xl font-semibold">{contact.full_name || `User ${userId}`}</h2>
                {contact.username && (
                  <p className="text-telegram-accent">@{contact.username}</p>
                )}
                <p className="text-xs text-telegram-textSecondary mt-1">ID: {userId}</p>
              </div>

              {/* Bio */}
              {contact.bio && (
                <div className="mb-4 p-3 bg-telegram-bg rounded-xl">
                  <p className="text-sm whitespace-pre-wrap">{contact.bio}</p>
                </div>
              )}

              {/* Details */}
              <div className="space-y-3">
                {contact.phone && (
                  <div className="flex items-center gap-3 text-sm">
                    <Phone size={18} className="text-telegram-textSecondary" />
                    <span>{contact.phone}</span>
                  </div>
                )}

                {contact.birthday && (
                  <div className="flex items-center gap-3 text-sm">
                    <Calendar size={18} className="text-telegram-textSecondary" />
                    <span>{contact.birthday}</span>
                  </div>
                )}

                {contact.personal_channel_title && (
                  <div className="flex items-center gap-3 text-sm">
                    <Megaphone size={18} className="text-telegram-textSecondary" />
                    <span>{contact.personal_channel_title}</span>
                  </div>
                )}

                {messagesCount > 0 && (
                  <div className="flex items-center gap-3 text-sm">
                    <MessageSquare size={18} className="text-telegram-textSecondary" />
                    <span>{messagesCount} сообщений в базе</span>
                  </div>
                )}

                {contact.common_chats_count > 0 && (
                  <div className="flex items-center gap-3 text-sm">
                    <Link2 size={18} className="text-telegram-textSecondary" />
                    <span>{contact.common_chats_count} общих чатов</span>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3 mt-6">
                <a
                  href={getTelegramLink()}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 py-3 bg-telegram-blue rounded-xl font-medium hover:bg-opacity-90 transition-colors flex items-center justify-center gap-2"
                >
                  <ExternalLink size={18} />
                  Открыть в TG
                </a>
                <button
                  onClick={copyToClipboard}
                  className="px-4 py-3 bg-telegram-hover rounded-xl hover:bg-telegram-bg transition-colors flex items-center gap-2"
                >
                  {copied ? <Check size={18} /> : <Copy size={18} />}
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

export default ContactModal
