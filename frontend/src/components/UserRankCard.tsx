import { Trophy, Flame } from 'lucide-react'

interface UserRankCardProps {
  rank: number
  streakDays: number
  levelTitle: string
  percentile: string
}

export default function UserRankCard({ rank, streakDays, levelTitle, percentile }: UserRankCardProps) {
  return (
    <div
      className="mx-3 p-3 rounded-2xl border border-orange-200/60"
      style={{ background: 'var(--color-rank-card-bg)' }}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <Trophy size={14} className="text-orange-500" />
          <span className="text-sm font-black text-orange-600">#{rank} Rank</span>
        </div>
        <div className="flex items-center gap-1">
          <Flame size={13} className="text-orange-400" />
          <span className="text-xs font-bold text-gray-600">{streakDays}d</span>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-gray-600">
          {levelTitle} 🏅
        </span>
        <span className="text-xs font-bold text-orange-500">{percentile}</span>
      </div>
    </div>
  )
}
