import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Send, Sparkles, BookOpen, Brain,
  ArrowLeft, RefreshCw, Trophy, HelpCircle,
  Layers, CheckCircle2, ChevronRight, Plus, RotateCcw
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useSubjectStore } from '../stores/subjectStore'
import { useLanguageStore } from '../stores/languageStore'
import { useTranslation } from '../utils/translations'
import { chatApi, streamChatMessage } from '../services/api'
import ChatMessage from '../components/ChatMessage'
import type { Source } from '../components/SourceCard'

interface ExtendedMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  sources?: Source[]
  graph_context?: any
}

// Subject-specific theme and prompts
const SUBJECT_CONFIGS: Record<string, {
  color: string
  accentBg: string
  borderColor: string
  title: string
  icon: string
  starters: string[]
}> = {
  'sslc-math': {
    color: '#D97706',
    accentBg: '#FFF0B3',
    borderColor: '#FDE68A',
    title: 'Class 10 Mathematics AI Tutor',
    icon: '📐',
    starters: [
      'Give me 5 minute cheatcode for Arithmetic Sequences.',
      'How to solve second degree equations by completing the square?',
      'What are the angle properties of cyclic quadrilaterals in circles?',
      'How do I calculate probability using geometric area method?',
    ],
  },
  'sslc-physics': {
    color: '#0284C7',
    accentBg: '#F0F9FF',
    borderColor: '#BAE6FD',
    title: 'Class 10 Physics AI Tutor',
    icon: '⚡',
    starters: [
      'Give me 5 minute cheatcode for Wave Motion & Light Refraction.',
      'Explain how convex lenses form images at different object distances.',
      'Why does light disperse into a spectrum when passing through a glass prism?',
      'Explain the Right-Hand Thumb Rule for magnetic fields around a conductor.',
    ],
  },
  'sslc-chemistry': {
    color: '#059669',
    accentBg: '#ECFDF5',
    borderColor: '#A7F3D0',
    title: 'Class 10 Chemistry AI Tutor',
    icon: '🧪',
    starters: [
      'Give me 5 minute cheatcode for Nomenclature of Organic Compounds.',
      'How do I write IUPAC names for branched alkanes and alkenes?',
      'Explain the subshell electron configuration (s, p, d, f) with examples.',
      'What are Boyle’s Law and Charles’s Law? Explain with mole concept.',
    ],
  },
}

// In-memory cache for instant 0ms chapter switching
const subjectSessionCache = new Map<string, { sessionId: string; messages: ExtendedMessage[] }>()

export default function SubjectChatPage() {
  const { subjectId, topicId: routeTopicId } = useParams<{ subjectId: string; topicId?: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAuthStore((s) => s.user)
  const subjects = useSubjectStore((s) => s.subjects)
  const getTopics = useSubjectStore((s) => s.getTopics)
  const recordActivity = useSubjectStore((s) => s.recordActivity)

  const { uiLanguage, aiLanguage, setAiLanguage } = useLanguageStore()
  const t = useTranslation(uiLanguage)

  const activeSubjectId = subjectId || 'sslc-math'
  const subject = subjects.find((s) => s.id === activeSubjectId) || subjects[0]
  const topics = getTopics(activeSubjectId)
  const config = SUBJECT_CONFIGS[activeSubjectId] || SUBJECT_CONFIGS['sslc-math']

  const [selectedTopicId, setSelectedTopicId] = useState<string>(routeTopicId || '')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ExtendedMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [loadingSession, setLoadingSession] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const pendingSessionPromiseRef = useRef<Promise<string> | null>(null)

  const selectedTopic = topics.find((t) => t.id === selectedTopicId)

  // Initialize or fetch stored session & messages for this subject with instant cache + single fast query
  useEffect(() => {
    let isMounted = true
    const targetTopic = selectedTopicId || activeSubjectId
    const sessionTitle = selectedTopic ? `${subject.name}: ${selectedTopic.title}` : `${subject.name} Chat`

    // 1. Check instant in-memory cache
    const cached = subjectSessionCache.get(targetTopic)
    if (cached) {
      setSessionId(cached.sessionId)
      setMessages(cached.messages)
      setLoadingSession(false)
    } else {
      setLoadingSession(true)
    }

    // 2. Fetch or create session in 1 single unified query
    const sessionPromise = (async () => {
      try {
        const res = await chatApi.getTopicSession(targetTopic, sessionTitle)
        const data = res.data
        const activeSid = data.id || data.session?.id || ''
        const rawMsgs = data.messages || []
        const loadedMsgs: ExtendedMessage[] = rawMsgs.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
          sources: m.metadata?.sources ?? m.sources ?? [],
          graph_context: m.metadata?.graph_context ?? m.graph_context ?? null,
        }))

        // Update in-memory cache
        subjectSessionCache.set(targetTopic, {
          sessionId: activeSid,
          messages: loadedMsgs,
        })

        if (isMounted) {
          setSessionId(activeSid)
          setMessages(loadedMsgs)
        }

        // Only send the inbuilt intro prompt on FIRST visit (when conversation history is empty)
        const state = location.state as any
        if (state?.initialPrompt && isMounted && loadedMsgs.length === 0) {
          sendMessage(state.initialPrompt, activeSid)
          navigate(location.pathname, { replace: true, state: {} })
        } else if (state?.initialPrompt && isMounted) {
          navigate(location.pathname, { replace: true, state: {} })
        }

        return activeSid
      } catch (err) {
        console.error('Failed to initialize subject chat session', err)
        return ''
      } finally {
        if (isMounted) setLoadingSession(false)
      }
    })()

    pendingSessionPromiseRef.current = sessionPromise

    return () => {
      isMounted = false
    }
  }, [activeSubjectId, selectedTopicId])

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  // Send message and persist to database
  const sendMessage = useCallback(async (contentToSend?: string, overrideSessionId?: string) => {
    const text = (contentToSend || input).trim()
    if (!text || isStreaming) return

    // Ensure we have an active session ID (awaiting initialization promise if still pending)
    let activeSid = overrideSessionId || sessionId
    if (!activeSid && pendingSessionPromiseRef.current) {
      activeSid = await pendingSessionPromiseRef.current
    }
    if (!activeSid) return

    if (!contentToSend) setInput('')

    const userMessage: ExtendedMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }

    const assistantMsgId = `asst_${Date.now()}`
    const placeholderAssistant: ExtendedMessage = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      sources: [],
    }

    setMessages((prev) => {
      const updated = [...prev, userMessage, placeholderAssistant]
      const targetTopic = selectedTopicId || activeSubjectId
      const cached = subjectSessionCache.get(targetTopic)
      if (cached) {
        subjectSessionCache.set(targetTopic, { ...cached, messages: updated })
      }
      return updated
    })
    setIsStreaming(true)

    if (selectedTopicId) {
      recordActivity(activeSubjectId, selectedTopicId)
    }

    const token = useAuthStore.getState().token || localStorage.getItem('access_token') || ''

    await streamChatMessage({
      sessionId: activeSid,
      content: text,
      token,
      language: aiLanguage,
      signal: abortControllerRef.current?.signal,
      onGraphContext: () => {},
      onSources: (sources) => {
        setMessages((prev) => {
          const updated = prev.map((m) => (m.id === assistantMsgId ? { ...m, sources } : m))
          const targetTopic = selectedTopicId || activeSubjectId
          const cached = subjectSessionCache.get(targetTopic)
          if (cached) {
            subjectSessionCache.set(targetTopic, { ...cached, messages: updated })
          }
          return updated
        })
      },
      onToken: (tokenChunk) => {
        setMessages((prev) => {
          const updated = prev.map((m) => (m.id === assistantMsgId ? { ...m, content: m.content + tokenChunk } : m))
          const targetTopic = selectedTopicId || activeSubjectId
          const cached = subjectSessionCache.get(targetTopic)
          if (cached) {
            subjectSessionCache.set(targetTopic, { ...cached, messages: updated })
          }
          return updated
        })
      },
      onDone: () => {
        setIsStreaming(false)
        abortControllerRef.current = null
      },
      onError: (err) => {
        setIsStreaming(false)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: m.content + `\n\n*(Error connecting to AI: ${err})*` }
              : m
          )
        )
      },
    })
  }, [input, sessionId, isStreaming, selectedTopicId, activeSubjectId, recordActivity, aiLanguage])

  // Reset/Clear conversation for this chapter in DB
  const handleResetChat = async () => {
    if (!sessionId || isStreaming) return
    const confirmed = window.confirm('Start a new conversation for this chapter? Previous messages will be cleared.')
    if (!confirmed) return

    try {
      await chatApi.deleteSession(sessionId)
      const targetTopic = selectedTopicId || activeSubjectId
      const sessionTitle = selectedTopic ? `${subject.name}: ${selectedTopic.title}` : `${subject.name} Chat`
      const newSess = await chatApi.createSession(targetTopic, sessionTitle)
      const newSid = newSess.data.id
      setSessionId(newSid)
      setMessages([])
      subjectSessionCache.set(targetTopic, { sessionId: newSid, messages: [] })
    } catch (err) {
      console.error('Failed to reset session:', err)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-68px)] bg-[#F7F7F7] text-[#3C3C3C] font-sans">
      {/* ─── Top Subject Navigation & Chapter Bar ─── */}
      <header className="bg-white border-b border-[#E2E8F0] px-4 sm:px-8 py-3.5 flex flex-col gap-3 elevation-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(`/subjects/${activeSubjectId}`)}
              className="p-2 rounded-[1.25rem] hover:bg-[#F2ECE4] text-[#777777] hover:text-[#3C3C3C] transition-colors cursor-pointer"
              title="Back to Subject Workspace"
            >
              <ArrowLeft size={18} />
            </button>

            <div className="flex items-center gap-2.5">
              <span className="text-2xl">{config.icon}</span>
              <div>
                <h1 className="text-base sm:text-lg font-bold text-[#3C3C3C] leading-tight">
                  {subject.name} AI Tutor
                </h1>
                <p className="text-xs text-[#777777]">
                  Connected to Official Kerala SCERT Class 10 Textbook (Pinecone Cloud)
                </p>
              </div>
            </div>
          </div>

          {/* Quick Actions & Language Control */}
          <div className="flex items-center gap-2">
            {/* AI Response Language Selector Pill */}
            <div className="flex items-center bg-slate-100 p-1 rounded-full border border-slate-200 text-xs font-bold mr-1">
              <button
                type="button"
                onClick={() => setAiLanguage('english')}
                className={`px-2.5 py-1 rounded-full transition-all cursor-pointer flex items-center gap-1.5 ${
                  aiLanguage === 'english'
                    ? 'bg-white text-indigo-700 shadow-2xs font-extrabold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
                title="Respond in English"
              >
                <span>🇬🇧</span>
                <span>English</span>
              </button>
              <button
                type="button"
                onClick={() => setAiLanguage('swedish')}
                className={`px-2.5 py-1 rounded-full transition-all cursor-pointer flex items-center gap-1.5 ${
                  aiLanguage === 'swedish'
                    ? 'bg-white text-indigo-700 shadow-2xs font-extrabold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
                title="Svara på svenska"
              >
                <span>🇸🇪</span>
                <span>Svenska</span>
              </button>
              <button
                type="button"
                onClick={() => setAiLanguage('arabic')}
                className={`px-2.5 py-1 rounded-full transition-all cursor-pointer flex items-center gap-1.5 ${
                  aiLanguage === 'arabic'
                    ? 'bg-white text-indigo-700 shadow-2xs font-extrabold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
                title="الرد باللغة العربية"
              >
                <span>🇸🇦</span>
                <span>العربية</span>
              </button>
            </div>

            {messages.length > 0 && (
              <button
                onClick={handleResetChat}
                disabled={isStreaming}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-[1.25rem] border border-[#E2E8F0] hover:border-[#4F46E5] text-xs font-bold text-[#777777] hover:text-[#4F46E5] transition-colors cursor-pointer bg-white"
                title="Start a new chat for this chapter"
              >
                <RotateCcw size={13} />
                <span className="hidden sm:inline">New Chat</span>
              </button>
            )}

            {selectedTopicId && (
              <>
                <button
                  onClick={() => navigate(`/quiz/${selectedTopicId}`)}
                  className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-[1.25rem] border border-[#E2E8F0] hover:border-[#4F46E5] text-xs font-bold text-[#777777] hover:text-[#4F46E5] transition-colors cursor-pointer bg-white"
                >
                  <Trophy size={14} /> Practice Quiz
                </button>
                <button
                  onClick={() => navigate(`/flashcards/${selectedTopicId}`)}
                  className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-[1.25rem] border border-[#E2E8F0] hover:border-[#4F46E5] text-xs font-bold text-[#777777] hover:text-[#4F46E5] transition-colors cursor-pointer bg-white"
                >
                  <Layers size={14} /> Flashcards
                </button>
              </>
            )}
          </div>
        </div>

        {/* ─── Chapter Selector Chips ─── */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
          <button
            onClick={() => setSelectedTopicId('')}
            className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-all cursor-pointer ${
              selectedTopicId === ''
                ? 'bg-[#3C3C3C] text-white elevation-2'
                : 'bg-[#F2ECE4] text-[#777777] hover:bg-[#E2E8F0]'
            }`}
          >
            📖 All Chapters
          </button>
          {topics.map((t) => {
            const isSelected = selectedTopicId === t.id
            return (
              <button
                key={t.id}
                onClick={() => setSelectedTopicId(t.id)}
                className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-all cursor-pointer flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-[#4F46E5] text-white elevation-2'
                    : 'bg-[#F2ECE4] text-[#777777] hover:bg-[#E2E8F0]'
                }`}
              >
                {t.title}
              </button>
            )
          })}
        </div>
      </header>

      {/* ─── Top Indeterminate Sync Bar (Non-blocking) ─── */}
      {loadingSession && (
        <div className="w-full h-0.5 bg-indigo-100 overflow-hidden relative z-10">
          <div className="h-full bg-gradient-to-r from-[#4F46E5] via-[#818CF8] to-[#4F46E5] w-full animate-pulse" />
        </div>
      )}

      {/* ─── Main Chat Area ─── */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 max-w-4xl w-full mx-auto">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: 'easeOut' }}
            className="h-full flex flex-col items-center justify-center text-center py-10 space-y-6"
          >
            {/* Animated Floating Emblem */}
            <motion.div
              animate={{ y: [0, -8, 0] }}
              transition={{ repeat: Infinity, duration: 3.5, ease: 'easeInOut' }}
              className="relative"
            >
              <div
                className="w-20 h-20 rounded-[2rem] flex items-center justify-center text-4xl elevation-4 border"
                style={{ backgroundColor: config.accentBg, borderColor: config.borderColor }}
              >
                {config.icon}
              </div>
              <div
                className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-white border flex items-center justify-center elevation-2 text-xs font-bold"
                style={{ borderColor: config.borderColor, color: config.color }}
              >
                10th
              </div>
            </motion.div>

            <div className="max-w-md space-y-2">
              <h2 className="text-2xl font-black text-[#3C3C3C] tracking-tight">
                {selectedTopic ? selectedTopic.title : `${subject.name} AI Tutor`}
              </h2>
              <p className="text-sm text-[#777777] leading-relaxed">
                {selectedTopic
                  ? selectedTopic.description
                  : 'Ask any question from official textbook chapters. I will explain concepts, provide step-by-step examples, solved calculations, and exam model answers.'}
              </p>
            </div>

            {/* Prompt Starters */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl text-left pt-2">
              {config.starters.map((starter, idx) => (
                <motion.button
                  key={idx}
                  whileHover={{ scale: 1.02, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => sendMessage(starter)}
                  className="p-4 rounded-[1.5rem] bg-white border border-[#E2E8F0] hover:border-[#4F46E5] hover:elevation-2 transition-all cursor-pointer flex items-start gap-3 group text-left"
                >
                  <div className="w-7 h-7 rounded-[1.25rem] bg-[#EEF2FF] flex items-center justify-center flex-shrink-0 mt-0.5 group-hover:scale-110 transition-transform">
                    <Sparkles size={14} className="text-[#4F46E5]" />
                  </div>
                  <span className="text-xs font-bold text-[#3C3C3C] group-hover:text-[#4F46E5] transition-colors leading-relaxed">
                    {starter}
                  </span>
                </motion.button>
              ))}
            </div>
          </motion.div>
        ) : (
          <div className="space-y-4 pb-4">
            <AnimatePresence initial={false}>
              {messages.map((m) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 10, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.25, ease: 'easeOut' }}
                >
                  <ChatMessage
                    role={m.role}
                    content={m.content}
                    sources={m.sources}
                    isStreaming={isStreaming && m.id === messages[messages.length - 1]?.id}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        )}
      </main>

      {/* ─── Bottom Chat Input (Clean & Aesthetic Floating Capsule) ─── */}
      <footer className="p-4 max-w-4xl w-full mx-auto">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            sendMessage()
          }}
          className="relative bg-white border border-[#E2E8F0] focus-within:border-[#4F46E5] focus-within:ring-3 focus-within:ring-[#4F46E5]/15 rounded-[2rem] p-2 pl-5 elevation-2 transition-all flex items-center gap-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask a question or topic from ${selectedTopic ? selectedTopic.title : subject.name}...`}
            className="flex-1 bg-transparent text-sm sm:text-base text-[#3C3C3C] font-medium placeholder-[#9E9B95] focus:outline-none"
            disabled={isStreaming}
          />

          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-3.5 bg-[#4F46E5] hover:bg-[#4338CA] disabled:opacity-30 disabled:cursor-not-allowed text-white rounded-[1.5rem] transition-all cursor-pointer flex-shrink-0 elevation-2 flex items-center justify-center"
            title="Send Message"
          >
            <Send size={16} />
          </motion.button>
        </form>
      </footer>
    </div>
  )
}
