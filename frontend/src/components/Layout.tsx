import { useState, useEffect, useCallback } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'

import {
  Home,
  BookOpen,
  CalendarCheck,
  Layers,
  LogOut,
  Menu,
  X,
  WifiOff,
  GraduationCap,
  Award,
  Globe,
  ChevronLeft,
  ChevronRight
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { useChatStore } from '../stores/chatStore'
import { useLanguageStore } from '../stores/languageStore'
import { useTranslation } from '../utils/translations'
import { healthApi, chatApi } from '../services/api'
import ProfileModal from './ProfileModal'
import UpgradeModal from './UpgradeModal'
import ConfirmModal from './ConfirmModal'

export default function Layout() {
  const { user, isAuthenticated, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [isOnline, setIsOnline] = useState<boolean>(true)
  const [isProfileOpen, setIsProfileOpen] = useState(false)
  const [isUpgradeOpen, setIsUpgradeOpen] = useState(false)
  const [confirmDeleteSid, setConfirmDeleteSid] = useState<string | null>(null)

  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('indie-tutor-sidebar-collapsed') === 'true'
    } catch {
      return false
    }
  })

  const toggleSidebar = () => {
    setIsCollapsed((prev) => {
      const next = !prev
      try { localStorage.setItem('indie-tutor-sidebar-collapsed', String(next)) } catch {}
      return next
    })
  }

  const { uiLanguage, setUiLanguage } = useLanguageStore()
  const t = useTranslation(uiLanguage)

  const activeSession = useChatStore((s) => s.activeSession)
  const setActiveSession = useChatStore((s) => s.setActiveSession)
  const removeSession = useChatStore((s) => s.removeSession)

  const NAV_ITEMS = [
    { to: '/dashboard', icon: Home, label: t.nav.home, badge: null },
    { to: '/chat', icon: BookOpen, label: t.nav.learn, badge: t.nav.live },
    { to: '/subjects', icon: Layers, label: t.nav.mySubjects, badge: null },
    { to: '/records', icon: Award, label: t.nav.studentRecords, badge: t.nav.live },
    { to: '/study-plan', icon: CalendarCheck, label: t.nav.studyPlan, badge: t.nav.ai },
  ]

  useEffect(() => {
    let isMounted = true
    const checkBackend = () => {
      healthApi
        .check()
        .then(() => { if (isMounted) setIsOnline(true) })
        .catch(() => { if (isMounted) setIsOnline(false) })
    }
    checkBackend()
    const interval = setInterval(checkBackend, 60000)
    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  const executeDeleteSession = useCallback(async () => {
    const sid = confirmDeleteSid
    if (!sid) return
    setConfirmDeleteSid(null)
    try {
      await chatApi.deleteSession(sid)
      removeSession(sid)
      if (activeSession?.id === sid) {
        setActiveSession(null)
        navigate('/chat')
      }
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }, [confirmDeleteSid, activeSession?.id, removeSession, setActiveSession, navigate])

  useEffect(() => {
    document.documentElement.dir = uiLanguage === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = uiLanguage
  }, [uiLanguage])

  const toggleLanguage = () => {
    if (uiLanguage === 'en') setUiLanguage('sv')
    else if (uiLanguage === 'sv') setUiLanguage('ar')
    else setUiLanguage('en')
  }

  const getLangBadge = (lang: string) => {
    if (lang === 'ar') return '🇸🇦 AR'
    if (lang === 'sv') return '🇸🇪 SV'
    return '🇬🇧 EN'
  }

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden text-text-primary font-sans antialiased">
      {/* Modals */}
      <ProfileModal isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} />
      <UpgradeModal isOpen={isUpgradeOpen} onClose={() => setIsUpgradeOpen(false)} />
      <ConfirmModal
        isOpen={Boolean(confirmDeleteSid)}
        title="Delete Chat Session?"
        message="Are you sure you want to delete this chat session? All messages, documents, and data will be permanently removed from the database."
        confirmText="Delete Session"
        cancelText="Cancel"
        variant="danger"
        onConfirm={executeDeleteSession}
        onCancel={() => setConfirmDeleteSid(null)}
      />

      {/* ─── DESKTOP SIDE DRAWER SIDEBAR ─── */}
      <aside
        className={`hidden lg:flex flex-shrink-0 flex-col p-3 z-30 transition-all duration-300 ease-in-out select-none ${
          isCollapsed ? 'w-[84px]' : 'w-[250px]'
        }`}
      >
        <div className="flex-1 rounded-3xl bg-white/90 backdrop-blur-2xl border border-slate-200/80 shadow-xs flex flex-col justify-between p-3.5 relative overflow-hidden">
          
          {/* Top Logo & Drawer Toggle Button */}
          <div className="flex items-center justify-between mb-5 px-1 pt-1">
            <div
              className="flex items-center gap-3 cursor-pointer overflow-hidden group"
              onClick={() => navigate('/dashboard')}
            >
              <div className="w-10 h-10 rounded-2xl bg-indigo-600 text-white flex items-center justify-center shadow-md shadow-indigo-600/30 group-hover:scale-105 transition-transform shrink-0">
                <GraduationCap size={22} />
              </div>
              {!isCollapsed && (
                <div className="flex flex-col whitespace-nowrap transition-opacity duration-200">
                  <div className="flex items-center gap-1.5">
                    <span className="font-black text-slate-800 text-base tracking-tight">IndieTutor</span>
                    <span className="text-[9px] font-black uppercase tracking-wider bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded-md border border-indigo-200">
                      AI
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-semibold tracking-wide">Smart Exam Prep</span>
                </div>
              )}
            </div>

            {/* Collapse / Expand Toggle Button */}
            <button
              onClick={toggleSidebar}
              title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
              className="p-1.5 rounded-xl text-slate-400 hover:text-indigo-600 hover:bg-slate-100 transition-all shrink-0 cursor-pointer"
            >
              {isCollapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="flex-1 flex flex-col gap-2 overflow-y-auto no-scrollbar py-2">
            {NAV_ITEMS.map(({ to, icon: Icon, label, badge }) => {
              const isActive = location.pathname.startsWith(to)
              return (
                <NavLink
                  key={to}
                  to={to}
                  title={isCollapsed ? label : undefined}
                  className={`flex items-center gap-3.5 px-3 py-3 rounded-2xl font-bold text-xs transition-all group relative ${
                    isActive
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25'
                      : 'text-slate-600 hover:text-indigo-600 hover:bg-indigo-50/70'
                  }`}
                >
                  <Icon
                    size={20}
                    className={`shrink-0 transition-transform group-hover:scale-110 ${
                      isActive ? 'text-white' : 'text-slate-400 group-hover:text-indigo-600'
                    }`}
                  />
                  {!isCollapsed && (
                    <span className="truncate whitespace-nowrap tracking-tight">{label}</span>
                  )}
                  {!isCollapsed && badge && (
                    <span
                      className={`ml-auto text-[9px] font-black uppercase px-2 py-0.5 rounded-full ${
                        isActive
                          ? 'bg-white/20 text-white'
                          : 'bg-indigo-50 text-indigo-600 border border-indigo-200'
                      }`}
                    >
                      {badge}
                    </span>
                  )}
                </NavLink>
              )
            })}
          </nav>

          {/* Bottom Controls: Language Switcher & Profile / Auth */}
          <div className="pt-4 border-t border-slate-100 flex flex-col gap-3">
            
            {/* Website UI Language Switcher */}
            <button
              onClick={toggleLanguage}
              title={`${t.header.websiteLanguage}: ${
                uiLanguage === 'en' ? 'English (🇬🇧)' : uiLanguage === 'sv' ? 'Svenska (🇸🇪)' : 'العربية (🇸🇦)'
              }`}
              className={`flex items-center gap-2 px-3 py-2 rounded-2xl bg-slate-50 border border-slate-200/80 text-xs font-bold text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 transition-all cursor-pointer ${
                isCollapsed ? 'justify-center' : 'justify-between'
              }`}
            >
              <div className="flex items-center gap-2 truncate">
                <Globe size={15} className="text-indigo-600 shrink-0" />
                {!isCollapsed && <span className="truncate">{t.header.websiteLanguage}</span>}
              </div>
              <span className="font-black text-indigo-600 text-[11px] shrink-0">
                {getLangBadge(uiLanguage)}
              </span>
            </button>

            {/* Profile / Auth Section */}
            {isAuthenticated ? (
              <div className={`flex items-center gap-2 p-1.5 rounded-2xl bg-slate-50 border border-slate-200/80 ${
                isCollapsed ? 'flex-col justify-center' : 'justify-between'
              }`}>
                <div
                  onClick={() => setIsProfileOpen(true)}
                  className="flex items-center gap-2.5 min-w-0 cursor-pointer group flex-1"
                  title={t.header.profile}
                >
                  <div className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-black text-xs shrink-0 shadow-xs group-hover:scale-105 transition-transform">
                    {user?.username?.charAt(0).toUpperCase() || 'U'}
                  </div>
                  {!isCollapsed && (
                    <div className="flex flex-col min-w-0 text-left truncate">
                      <span className="text-xs font-bold text-slate-800 truncate leading-none">
                        {user?.username || 'Learner'}
                      </span>
                      <span className="text-[10px] text-slate-400 truncate mt-1 leading-none">
                        {user?.email || 'student@indietutor.ai'}
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => logout()}
                  className="p-1.5 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors shrink-0 cursor-pointer"
                  title={t.header.logout}
                >
                  <LogOut size={16} />
                </button>
              </div>
            ) : (
              <div className={`flex gap-2 ${isCollapsed ? 'flex-col' : 'flex-row'}`}>
                <button
                  onClick={() => navigate('/login')}
                  className="flex-1 py-2 px-2 text-xs font-bold text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-50 transition-all text-center cursor-pointer shadow-xs truncate"
                >
                  {isCollapsed ? 'Login' : (t.header.login || 'Login')}
                </button>
                <button
                  onClick={() => navigate('/register')}
                  className="flex-1 py-2 px-2 text-xs font-bold text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 transition-all text-center cursor-pointer shadow-xs truncate"
                >
                  {isCollapsed ? 'Sign Up' : (t.header.register || 'Sign Up')}
                </button>
              </div>
            )}

          </div>

        </div>
      </aside>

      {/* ─── MOBILE SIDEBAR (Drawer) ─── */}
      <div className={`fixed inset-0 bg-black/30 backdrop-blur-sm z-40 lg:hidden transition-opacity ${mobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} onClick={() => setMobileOpen(false)} />
      <aside className={`fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 transform transition-transform duration-300 lg:hidden flex flex-col ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-6 flex items-center justify-between border-b border-slate-200">
          <div className="flex items-center gap-3 text-indigo-600">
            <GraduationCap size={24} />
            <span className="font-black text-lg text-slate-800">IndieTutor</span>
          </div>
          <button onClick={() => setMobileOpen(false)} className="p-2 text-slate-400 hover:bg-slate-100 rounded-lg">
            <X size={20} />
          </button>
        </div>
        <nav className="flex-1 p-4 flex flex-col gap-2 overflow-y-auto">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
            const isActive = location.pathname.startsWith(to)
            return (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl font-bold transition-colors ${isActive ? 'bg-indigo-50 text-indigo-600' : 'text-slate-600 hover:bg-indigo-50/50 hover:text-indigo-600'
                  }`}
              >
                <Icon size={20} className={isActive ? 'text-indigo-600' : 'text-slate-400'} />
                {label}
              </NavLink>
            )
          })}
        </nav>
        {/* Mobile Language Switcher */}
        <div className="p-4 border-t border-slate-200">
          <button
            onClick={toggleLanguage}
            className="w-full flex items-center justify-between px-4 py-2.5 rounded-xl bg-slate-100 border border-slate-200 text-sm font-bold text-slate-700 hover:bg-indigo-50"
          >
            <div className="flex items-center gap-2">
              <Globe size={16} className="text-indigo-600" />
              <span>{t.header.websiteLanguage}</span>
            </div>
            <span className="font-black text-indigo-600">{getLangBadge(uiLanguage)}</span>
          </button>
        </div>
      </aside>

      {/* ─── MAIN CONTENT CONTAINER ─── */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden relative">
        {/* Mobile Top Navbar */}
        <div className="lg:hidden px-4 h-16 bg-white border-b border-slate-200 flex items-center justify-between sticky top-0 z-30 shadow-xs shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-50"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2 cursor-pointer font-black text-indigo-600 text-lg" onClick={() => navigate('/dashboard')}>
            IndieTutor
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={toggleLanguage}
              className="px-2 py-1 rounded-lg bg-slate-100 text-xs font-black text-slate-700"
            >
              {getLangBadge(uiLanguage)}
            </button>
            <span className={`w-2.5 h-2.5 rounded-full ${isOnline ? 'bg-emerald-500' : 'bg-rose-500 animate-ping'}`} title={isOnline ? t.header.online : t.header.offline} />
            {isAuthenticated ? (
              <button
                onClick={() => setIsProfileOpen(true)}
                className="w-8 h-8 rounded-full bg-indigo-600 text-white flex items-center justify-center font-bold text-sm shadow-xs"
              >
                {user?.username?.[0]?.toUpperCase() ?? 'U'}
              </button>
            ) : (
              <div className="flex items-center gap-1.5">
                <button
                  onClick={() => navigate('/login')}
                  className="px-2 py-1 text-xs font-bold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50"
                >
                  {t.header.login || 'Login'}
                </button>
                <button
                  onClick={() => navigate('/register')}
                  className="px-2 py-1 text-xs font-bold text-white bg-indigo-600 rounded-lg shadow-2xs hover:bg-indigo-700"
                >
                  {t.header.register || 'Sign Up'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Network Warning Banner */}
        {!isOnline && (
          <div className="bg-amber-50 text-amber-800 border-b border-amber-200 px-4 py-3 text-sm font-bold flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <WifiOff size={16} />
              <span>{t.header.offlineWarning}</span>
            </div>
            <button onClick={() => window.location.reload()} className="bg-amber-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold">
              {t.header.retry}
            </button>
          </div>
        )}

        {/* Page Outlet */}
        <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
          <Outlet />
        </main>

        {/* Mobile Bottom Navigation */}
        <nav className="lg:hidden absolute bottom-0 left-0 right-0 bg-white/95 backdrop-blur-md border-t border-slate-200 px-4 py-2 flex items-center justify-around z-40 shadow-lg pb-safe">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
            const isActive = location.pathname.startsWith(to)
            return (
              <NavLink
                key={to}
                to={to}
                className={`flex flex-col items-center gap-1 py-1 px-3 rounded-xl transition-all ${isActive ? 'text-indigo-600 scale-105' : 'text-slate-400 hover:text-slate-700'
                  }`}
              >
                <Icon size={20} strokeWidth={isActive ? 2.5 : 2} />
                <span className={`text-[10px] font-bold ${isActive ? 'text-indigo-600' : ''}`}>{label}</span>
              </NavLink>
            )
          })}
        </nav>
      </div>
    </div>
  )
}
