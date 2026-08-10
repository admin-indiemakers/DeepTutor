import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Coins, Wallet, BarChart3, ArrowRight } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import { progressApi } from '../services/api'
import HeroBanner from '../components/dashboard/HeroBanner'
import FinanceCard from '../components/dashboard/FinanceCard'
import CourseCard from '../components/dashboard/CourseCard'
import NoticeItem from '../components/dashboard/NoticeItem'

// Custom list of mockup instructors
const MOCK_INSTRUCTORS = [
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150',
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150',
  'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150',
]

// Mock courses data
const MOCK_COURSES = [
  { id: 'cs101', title: 'Object oriented programming', iconType: 'laptop', isSelected: true },
  { id: 'cs202', title: 'Fundamentals of database systems', iconType: 'database', isSelected: false },
]

// Mock notices data
const MOCK_NOTICES = [
  { id: 'n1', title: 'Prelim payment due', text: 'Please ensure that your prelim examination dues are settled before September 15. Drop by the accounts division for manual clearances.' },
  { id: 'n2', title: 'Exam schedule', text: 'The official mid-term examination calendar is now uploaded. View your class syllabus index to confirm individual timelines.' },
]

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [selectedFinance, setSelectedFinance] = useState<'payable' | 'paid' | 'others'>('paid')
  const [selectedNotice, setSelectedNotice] = useState<any | null>(null)

  // Pull progress data from backend if available
  const { data: progress } = useQuery({
    queryKey: ['dashboard-progress-summary'],
    queryFn: () => progressApi.summary().then((r) => r.data),
  })

  const userName = user?.username ?? 'John'

  // Detailed billing and payment receipts breakdown
  const financeBreakdown = {
    payable: [
      { item: 'Tuition Fee (Autumn 2026)', amount: '$8,000' },
      { item: 'Laboratory & Material Fees', amount: '$1,500' },
      { item: 'Student Activity & Library Fees', amount: '$500' },
    ],
    paid: [
      { item: 'First Installment (Bank Wire)', amount: '$3,000', date: 'Aug 1, 2026' },
      { item: 'Second Installment (Credit Card)', amount: '$2,000', date: 'Aug 18, 2026' },
    ],
    others: [
      { item: 'Athletics & Gym Access Fee', amount: '$150' },
      { item: 'Portal Administration Access Fee', amount: '$150' },
    ],
  }

  return (
    <div className="p-6 lg:p-8 overflow-y-auto w-full h-full space-y-8 max-w-7xl mx-auto relative">
      
      {/* Hero Banner Component */}
      <HeroBanner userName={userName} />

      {/* Main Two-Column Layout Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column (Span 2): Finance Section & Enrolled Courses */}
        <div className="lg:col-span-2 space-y-8">
          
          {/* Finance Section */}
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-slate-900 leading-none">Finanace</h2>
            
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <FinanceCard
                title="Total Payable"
                amount="$10,000"
                icon={Coins}
                colorClass="bg-amber-50 text-amber-600"
                isSelected={selectedFinance === 'payable'}
                onClick={() => setSelectedFinance('payable')}
              />
              <FinanceCard
                title="Total Paid"
                amount="$5,000"
                icon={Wallet}
                colorClass="bg-violet-50 text-violet-600"
                isSelected={selectedFinance === 'paid'}
                onClick={() => setSelectedFinance('paid')}
              />
              <FinanceCard
                title="Others"
                amount="$300"
                icon={BarChart3}
                colorClass="bg-emerald-50 text-emerald-600"
                isSelected={selectedFinance === 'others'}
                onClick={() => setSelectedFinance('others')}
              />
            </div>

            {/* Interactive Billing Breakdown Box */}
            <div className="bg-slate-50 border border-slate-200/80 p-5 rounded-[20px] space-y-3 shadow-sm transition-all">
              <div className="flex items-center justify-between border-b border-slate-200/60 pb-2">
                <span className="text-[11px] font-black text-slate-800 uppercase tracking-wider">
                  Breakdown: {selectedFinance === 'payable' ? 'Total Payable' : selectedFinance === 'paid' ? 'Total Paid' : 'Others'}
                </span>
                <span className="text-[10px] font-extrabold text-slate-400 uppercase tracking-widest bg-white border border-slate-200 px-2 py-0.5 rounded">
                  {financeBreakdown[selectedFinance].length} items
                </span>
              </div>
              <div className="space-y-2">
                {financeBreakdown[selectedFinance].map((row: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex flex-col">
                      <span className="font-semibold text-slate-700">{row.item}</span>
                      {row.date && <span className="text-[10px] text-slate-400 font-medium">Receipt Date: {row.date}</span>}
                    </div>
                    <span className="font-extrabold text-slate-950">{row.amount}</span>
                  </div>
                ))}
              </div>
              
              {/* Dynamic Warning Indicator / Payment Portal Action */}
              {selectedFinance === 'payable' && (
                <div className="mt-4 p-3.5 bg-amber-50 rounded-2xl border border-amber-200/80 flex items-center justify-between gap-3">
                  <div className="flex flex-col">
                    <span className="text-xs font-black text-amber-900 leading-snug">Pending Tuition Clearance</span>
                    <span className="text-[10px] text-amber-700 font-semibold leading-relaxed">
                      You have an outstanding balance of <span className="font-extrabold">$5,000</span> due for registration checks.
                    </span>
                  </div>
                  <button 
                    onClick={() => navigate('/app/payment-info')}
                    className="text-[10px] font-black bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-xl shadow-sm transition-colors flex-shrink-0"
                  >
                    Pay Bill
                  </button>
                </div>
              )}
            </div>

          </div>

          {/* Enrolled Courses Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900 leading-none">Enrolled Courses</h2>
              <button 
                onClick={() => navigate('/app/courses')}
                className="text-xs text-violet-600 hover:text-violet-700 font-extrabold flex items-center gap-1 transition-colors"
              >
                See all
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {MOCK_COURSES.map((course) => (
                <CourseCard
                  key={course.id}
                  title={course.title}
                  iconType={course.iconType}
                  isSelected={course.isSelected}
                  onClick={() => navigate(`/app/courses`)}
                />
              ))}
            </div>
          </div>

        </div>

        {/* Right Column (Span 1): Instructors & Notices */}
        <div className="space-y-8">
          
          {/* Course Instructors Column Card */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900 leading-none">Course intructors</h2>
              <button 
                onClick={() => navigate('/app/courses')}
                className="text-xs text-violet-600 hover:text-violet-700 font-extrabold transition-colors"
              >
                See all
              </button>
            </div>

            {/* Avatars Row */}
            <div className="flex items-center gap-3">
              {MOCK_INSTRUCTORS.map((src, i) => (
                <div 
                  key={i} 
                  className="w-12 h-12 rounded-full overflow-hidden border-2 border-slate-100 shadow-sm flex-shrink-0"
                >
                  <img src={src} alt="Instructor avatar" className="w-full h-full object-cover" />
                </div>
              ))}
            </div>
          </div>

          {/* Daily Notice Column Card */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-900 leading-none">Daily notice</h2>
              <button 
                onClick={() => navigate('/app/notice')}
                className="text-xs text-violet-600 hover:text-violet-700 font-extrabold transition-colors"
              >
                See all
              </button>
            </div>

            {/* Notice Stack */}
            <div className="space-y-4 bg-[#f8fafc] border border-slate-100 p-5 rounded-[24px]">
              {MOCK_NOTICES.map((notice) => (
                <NoticeItem
                  key={notice.id}
                  title={notice.title}
                  text={notice.text}
                  onSeeMore={() => setSelectedNotice(notice)}
                />
              ))}
            </div>
          </div>

        </div>

      </div>

      {/* Notice Details Modal Overlay */}
      {selectedNotice && (
        <div className="fixed inset-0 z-50 bg-slate-950/40 backdrop-blur-sm flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="w-full max-w-md bg-white rounded-3xl p-6 shadow-2xl border border-slate-100 relative"
          >
            <button
              onClick={() => setSelectedNotice(null)}
              className="absolute top-5 right-5 text-slate-400 hover:text-slate-600 font-extrabold p-1 rounded-full hover:bg-slate-50 transition-colors"
            >
              ✕
            </button>
            
            <div className="space-y-4 mt-2">
              <div className="inline-block bg-violet-50 text-violet-600 text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider">
                Official Notice
              </div>
              <h3 className="text-lg font-black text-slate-950 tracking-tight leading-snug">
                {selectedNotice.title}
              </h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                {selectedNotice.text}
              </p>
              
              <button
                onClick={() => setSelectedNotice(null)}
                className="w-full bg-[#111] hover:bg-zinc-800 text-white font-extrabold text-xs py-3 px-4 rounded-xl transition-all shadow-sm"
              >
                Understood
              </button>
            </div>
          </motion.div>
        </div>
      )}

    </div>
  )
}
