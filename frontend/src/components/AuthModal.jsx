import React, { useState } from 'react'
import { API_URL } from '../App'
import { X, Loader2, Phone, Key, Lock } from 'lucide-react'

function AuthModal({ onClose, onSuccess }) {
  const [step, setStep] = useState('initial') // initial, code_sent, 2fa_required
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendCode = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const res = await fetch(`${API_URL}/api/chats/auth/send-code`, {
        method: 'POST'
      })
      const data = await res.json()
      
      if (data.status === 'code_sent') {
        setStep('code_sent')
      } else if (data.status === 'error') {
        setError(data.error)
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  const verifyCode = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const res = await fetch(`${API_URL}/api/chats/auth/verify-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      })
      const data = await res.json()
      
      if (data.status === 'authorized') {
        onSuccess()
      } else if (data.status === '2fa_required') {
        setStep('2fa_required')
      } else if (data.status === 'error') {
        setError(data.error)
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  const verify2FA = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const res = await fetch(`${API_URL}/api/chats/auth/verify-2fa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password })
      })
      const data = await res.json()
      
      if (data.status === 'authorized') {
        onSuccess()
      } else if (data.status === 'error') {
        setError(data.error)
      }
    } catch (err) {
      setError('Ошибка подключения к серверу')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-telegram-sidebar rounded-2xl p-6 w-full max-w-md mx-4 animate-fadeIn">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold">Авторизация в Telegram</h2>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-telegram-hover rounded-lg transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {step === 'initial' && (
          <div className="text-center">
            <div className="w-16 h-16 bg-telegram-blue rounded-full flex items-center justify-center mx-auto mb-4">
              <Phone size={32} />
            </div>
            <p className="text-telegram-textSecondary mb-6">
              Код авторизации будет отправлен на номер телефона, указанный в настройках
            </p>
            <button
              onClick={sendCode}
              disabled={loading}
              className="w-full py-3 bg-telegram-blue rounded-xl font-medium hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  Отправка...
                </>
              ) : (
                'Отправить код'
              )}
            </button>
          </div>
        )}

        {step === 'code_sent' && (
          <div>
            <div className="w-16 h-16 bg-telegram-accent rounded-full flex items-center justify-center mx-auto mb-4">
              <Key size={32} />
            </div>
            <p className="text-center text-telegram-textSecondary mb-4">
              Введите код, отправленный в Telegram
            </p>
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Код из Telegram"
              className="w-full px-4 py-3 bg-telegram-bg rounded-xl text-center text-2xl tracking-widest mb-4 focus:outline-none focus:ring-2 focus:ring-telegram-blue"
              maxLength={5}
            />
            <button
              onClick={verifyCode}
              disabled={loading || code.length < 5}
              className="w-full py-3 bg-telegram-blue rounded-xl font-medium hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  Проверка...
                </>
              ) : (
                'Подтвердить'
              )}
            </button>
          </div>
        )}

        {step === '2fa_required' && (
          <div>
            <div className="w-16 h-16 bg-telegram-accent rounded-full flex items-center justify-center mx-auto mb-4">
              <Lock size={32} />
            </div>
            <p className="text-center text-telegram-textSecondary mb-4">
              Введите пароль двухфакторной аутентификации
            </p>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Пароль 2FA"
              className="w-full px-4 py-3 bg-telegram-bg rounded-xl mb-4 focus:outline-none focus:ring-2 focus:ring-telegram-blue"
            />
            <button
              onClick={verify2FA}
              disabled={loading || !password}
              className="w-full py-3 bg-telegram-blue rounded-xl font-medium hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="animate-spin" size={20} />
                  Проверка...
                </>
              ) : (
                'Войти'
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default AuthModal
