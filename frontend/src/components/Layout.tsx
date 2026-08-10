import { useState } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  CreditCard,
  FileText,
  BookOpen,
  Archive,
  Award,
  Bell,
  Calendar,
  LogOut,
  Search,
  Menu,
  X,
  GraduationCap,
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

const NAV_ITEMS = [
  { to: '/app/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/app/payment-info', icon: CreditCard, label: 'Payment Info' },
  { to: '/app/registration', icon: FileText, label: 'Registration' },
  { to: '/app/courses', icon: BookOpen, label: 'Courses' },
  { to: '/app/drop-semester', icon: Archive, label: 'Drop Semester' },
  { to: '/app/result', icon: Award, label: 'Result' },
  { to: '/app/notice', icon: Bell, label: 'Notice' },
  { to: '/app/schedule', icon: Calendar, label: 'Schedule' },
]

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  // Fallback profile avatar initial
  const userInitial = user?.username?.[0]?.toUpperCase() ?? 'J'
  const userName = user?.username ?? 'John Doe'
  const userYear = '3rd year' // Custom fallback secondary line matching spec

  return (
    <div className="min-h-screen bg-portal-lavender flex items-center justify-center p-0 md:p-4 lg:p-6 overflow-x-hidden font-sans">
      {/* Centered Floating Large White Rounded Card */}
      <div className="w-full max-w-[1440px] min-h-screen md:min-h-[calc(100vh-2rem)] md:max-h-[calc(100vh-2rem)] bg-white md:rounded-[32px] shadow-2xl flex flex-col md:flex-row overflow-hidden border border-slate-100/50">
        
        {/* Mobile Sidebar backdrop */}
        {mobileOpen && (
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 md:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}

        {/* ─── LEFT SIDEBAR (Purple Gradient, Inset) ─── */}
        <aside
          className={`fixed md:static inset-y-0 left-0 z-50 w-[260px] bg-gradient-to-b from-[#7c3aed] to-[#4f46e5] text-white flex flex-col justify-between p-5 md:m-4 md:rounded-[24px] transition-transform duration-300 flex-shrink-0 ${
            mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
          }`}
        >
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Top Logo / Tile */}
            <div className="flex items-center justify-between mb-8">
              <div 
                className="flex items-center gap-3 cursor-pointer"
                onClick={() => { navigate('/app/dashboard'); setMobileOpen(false); }}
              >
                <div className="w-11 h-11 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-white border border-white/10 shadow-sm flex-shrink-0">
                  <GraduationCap size={22} className="stroke-[2.5]" />
                </div>
                <div>
                  <span className="font-black text-base text-white tracking-tight block">
                    Student Portal
                  </span>
                  <span className="text-[10px] text-white/60 block font-bold leading-none uppercase tracking-wider">
                    Adhyapikha
                  </span>
                </div>
              </div>

              {/* Mobile Close Button */}
              <button
                onClick={() => setMobileOpen(false)}
                className="md:hidden p-1 rounded-lg hover:bg-white/10 text-white/80"
              >
                <X size={18} />
              </button>
            </div>

            {/* Vertical Navigation Links */}
            <div className="flex-1 overflow-y-auto pr-1">
              <nav className="space-y-1.5">
                {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
                  const isActive = location.pathname.startsWith(to)
                  return (
                    <NavLink
                      key={to}
                      to={to}
                      onClick={() => setMobileOpen(false)}
                      className={`flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold transition-all ${
                        isActive
                          ? 'bg-portal-active-bg text-portal-active-text shadow-md shadow-purple-900/10'
                          : 'text-white/70 hover:text-white hover:bg-white/10'
                      }`}
                    >
                      <Icon
                        size={18}
                        className={`flex-shrink-0 ${isActive ? 'text-portal-primary' : 'text-white/60'}`}
                      />
                      <span>{label}</span>
                    </NavLink>
                  )
                })}
              </nav>
            </div>
          </div>

          {/* Bottom Section: Logout Separator */}
          <div className="pt-4 border-t border-white/10 mt-6">
            <button
              onClick={handleLogout}
              className="flex items-center gap-3.5 px-4 py-3 rounded-xl text-sm font-semibold text-white/75 hover:text-white hover:bg-white/10 transition-colors w-full"
            >
              <LogOut size={18} className="text-white/60 flex-shrink-0" />
              <span>Logout</span>
            </button>
          </div>
        </aside>

        {/* ─── MAIN CONTENT AREA ─── */}
        <div className="flex-1 flex flex-col min-h-0 bg-white">
          
          {/* Top Bar Navigation Toggle / Header for Mobile */}
          <div className="md:hidden px-5 py-4 bg-white border-b border-slate-100 flex items-center justify-between sticky top-0 z-30">
            <button
              onClick={() => setMobileOpen(true)}
              className="p-2.5 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              <Menu size={18} />
            </button>
            <div className="flex items-center gap-2" onClick={() => navigate('/app/dashboard')}>
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#7c3aed] to-[#4f46e5] flex items-center justify-center text-white">
                <GraduationCap size={16} />
              </div>
              <span className="font-black text-sm text-slate-900 tracking-tight">Portal</span>
            </div>
            <div className="w-9 h-9 rounded-full bg-violet-600 text-white flex items-center justify-center font-bold text-xs">
              {userInitial}
            </div>
          </div>

          {/* ─── TOP BAR (Desktop Viewport Header) ─── */}
          <header className="hidden md:flex items-center justify-between px-8 py-5 border-b border-slate-100 bg-white flex-shrink-0">
            
            {/* Pill-shaped Search Input */}
            <div className="relative w-72">
              <Search size={15} className="absolute left-3.5 top-3 text-slate-400" />
              <input
                type="text"
                placeholder="Search"
                className="w-full bg-[#f1f5f9] border-0 rounded-full pl-10 pr-4 py-2 text-xs font-semibold text-slate-950 placeholder-slate-400 outline-none focus:ring-2 focus:ring-violet-300 transition-all"
              />
            </div>

            {/* User Block & Notification Bell */}
            <div className="flex items-center gap-6">
              
              {/* Notification bell icon with red dot */}
              <button className="relative p-1 text-slate-500 hover:text-slate-700 transition-colors">
                <Bell size={20} />
                <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border-2 border-white" />
              </button>

              {/* User Identity Details */}
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="block text-xs font-black text-slate-900 leading-tight">
                    {userName}
                  </span>
                  <span className="block text-[10px] text-slate-400 font-extrabold leading-none mt-0.5">
                    {userYear}
                  </span>
                </div>
                <div className="w-10 h-10 rounded-full overflow-hidden bg-violet-100 flex items-center justify-center text-violet-700 font-black text-sm border-2 border-slate-100 shadow-sm flex-shrink-0">
                  {userInitial}
                </div>
              </div>

            </div>
          </header>

          {/* ─── OUTLET CONTENT BODY ─── */}
          <main className="flex-1 min-h-0 bg-white relative flex flex-col">
            <Outlet />
          </main>

        </div>

      </div>
    </div>
  )
}
