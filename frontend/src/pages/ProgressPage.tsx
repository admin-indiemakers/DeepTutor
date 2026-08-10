import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Trophy, Flame, Star, Award } from 'lucide-react'
import { progressApi, leaderboardApi } from '../services/api'
import PageHeader from '../components/PageHeader'
import SegmentedControl from '../components/SegmentedControl'
import StatCard from '../components/StatCard'
import StudyActivityPanel from '../components/StudyActivityPanel'

export default function ProgressPage() {
  const [period, setPeriod] = useState('All Time')

  const { data: summary } = useQuery({
    queryKey: ['progress-summary'],
    queryFn: () => progressApi.summary().then((r) => r.data),
  })

  const { data: calendarDays = [] } = useQuery({
    queryKey: ['progress-calendar'],
    queryFn: () => progressApi.calendar().then((r) => r.data),
  })

  const { data: leaderboardData } = useQuery({
    queryKey: ['progress-leaderboard'],
    queryFn: () => leaderboardApi.getRankings().then((r) => r.data),
  })

  const currentUserRank = leaderboardData?.current_user_rank
  const totalStudents = leaderboardData?.rankings?.length ?? 0
  const userRank = currentUserRank?.rank ?? 0
  const percentile = totalStudents > 0
    ? Math.max(1, Math.round((userRank / totalStudents) * 100))
    : 1

  // Count total activities completed (sessions + quizzes + flashcards mastered)
  const thingsFinished =
    (summary?.total_sessions ?? 0) +
    (summary?.quizzes_taken ?? 0) +
    (summary?.flashcards_mastered ?? 0)

  // Count total days studied from calendar data
  const totalDaysStudied = calendarDays.filter((d: any) => d.active).length

  const bestStreak = summary?.best_streak_days ?? summary?.streak_days ?? 0

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
      {/* Header with Live Updates + Segmented Control */}
      <PageHeader title="My Progress" emoji="🏆">
        <div className="flex items-center gap-3">
          {/* Live Updates pill */}
          <span className="pill-badge pill-badge-green">
            <span className="pulse-dot" />
            Live Updates
          </span>
        </div>
      </PageHeader>

      {/* Subtitle + Segmented Control */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 -mt-4">
        <p className="text-sm text-gray-500">
          See how you are doing — your streaks, points, and where you stand.
        </p>
        <SegmentedControl
          options={['All Time', 'This Month', 'This Week']}
          value={period}
          onChange={setPeriod}
        />
      </div>

      {/* 4 Stat Cards Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          title="Your Rank"
          value={`#${userRank || '—'}`}
          subtitle={`Top ${percentile}% of ${totalStudents} students`}
          icon={Trophy}
          accentColor="#f97316"
        />
        <StatCard
          title="Daily Streak"
          value={`${summary?.streak_days ?? 0} Days`}
          subtitle="Keep going every day! 🔥"
          icon={Flame}
          accentColor="#f97316"
        />
        <StatCard
          title="Your Points"
          value={`${summary?.total_xp ?? 0}`}
          subtitle="Earned from quizzes and learning"
          icon={Star}
          accentColor="#eab308"
        />
        <StatCard
          title="Your Level"
          value={summary?.level_title ?? 'Scholar'}
          subtitle="Your best level so far ✨"
          icon={Award}
          accentColor="#3b82f6"
        />
      </div>

      {/* Study Activity Panel (stats row + heatmap) */}
      <StudyActivityPanel
        totalDaysStudied={totalDaysStudied}
        currentStreak={summary?.streak_days ?? 0}
        bestStreak={bestStreak}
        thingsFinished={thingsFinished}
        calendarDays={calendarDays}
      />
    </div>
  )
}
