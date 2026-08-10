import { Calendar, Flame, Zap, CheckCircle2 } from 'lucide-react'
import ContributionHeatmap from './ContributionHeatmap'

interface StudyActivityPanelProps {
  totalDaysStudied: number
  currentStreak: number
  bestStreak: number // NOTE: "best_streak_ever" not tracked by backend — using mock/estimated value
  thingsFinished: number
  calendarDays: Array<{ date: string; active: boolean; intensity: number }>
}

export default function StudyActivityPanel({
  totalDaysStudied,
  currentStreak,
  bestStreak,
  thingsFinished,
  calendarDays,
}: StudyActivityPanelProps) {
  return (
    <div className="glass-card border border-gray-200 p-6">
      {/* Header row */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Calendar size={18} className="text-gray-500" />
          <h3 className="text-lg font-bold text-gray-900">Your Study Activity</h3>
        </div>
        <span className="pill-badge pill-badge-green">
          {totalDaysStudied} days you studied
        </span>
      </div>

      {/* 4-column stat row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6 pb-5 border-b border-gray-100">
        <div>
          <p className="text-xs text-gray-400 mb-1">Going strong for</p>
          <div className="flex items-center gap-1.5">
            <Flame size={15} className="text-orange-500" />
            <span className="text-lg font-black text-orange-500">{currentStreak} Days</span>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">Best streak ever</p>
          <div className="flex items-center gap-1.5">
            <Zap size={15} className="text-yellow-500" />
            <span className="text-lg font-black text-gray-900">{bestStreak} Days</span>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">Total days studied</p>
          <div className="flex items-center gap-1.5">
            <Calendar size={15} className="text-emerald-500" />
            <span className="text-lg font-black text-emerald-600">{totalDaysStudied} Days</span>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-1">Things you finished</p>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 size={15} className="text-blue-500" />
            <span className="text-lg font-black text-blue-600">{thingsFinished}</span>
          </div>
        </div>
      </div>

      {/* GitHub-style contribution heatmap */}
      <ContributionHeatmap
        days={calendarDays}
        totalDaysStudied={totalDaysStudied}
      />
    </div>
  )
}
