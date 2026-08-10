import { useMemo } from 'react'

interface HeatmapDay {
  date: string
  active: boolean
  intensity: number // 0-4
}

interface ContributionHeatmapProps {
  days: HeatmapDay[]
  totalDaysStudied?: number
}

const HEATMAP_COLORS = [
  'var(--color-heatmap-0)',
  'var(--color-heatmap-1)',
  'var(--color-heatmap-2)',
  'var(--color-heatmap-3)',
  'var(--color-heatmap-4)',
]

const ROW_LABELS = ['Mon', '', 'Wed', '', 'Fri', '', '']

export default function ContributionHeatmap({ days, totalDaysStudied }: ContributionHeatmapProps) {
  // Organize days into a week-grid: 7 rows (Mon-Sun) × N columns (weeks)
  const { weeks, monthLabels } = useMemo(() => {
    if (!days.length) return { weeks: [], monthLabels: [] }

    // Determine the first day's weekday (0 = Sun, adjust to Mon = 0)
    const firstDate = new Date(days[0].date)
    const firstDow = (firstDate.getDay() + 6) % 7 // Mon=0, Sun=6

    // Pad the beginning with empty days so the grid starts on Monday
    const padded: (HeatmapDay | null)[] = Array(firstDow).fill(null)
    padded.push(...days)

    // Build weeks
    const numWeeks = Math.ceil(padded.length / 7)
    const weekCols: (HeatmapDay | null)[][] = []
    for (let w = 0; w < numWeeks; w++) {
      const week: (HeatmapDay | null)[] = []
      for (let d = 0; d < 7; d++) {
        const idx = w * 7 + d
        week.push(idx < padded.length ? padded[idx] : null)
      }
      weekCols.push(week)
    }

    // Extract month labels from the first day of each month
    const labels: { label: string; col: number }[] = []
    let lastMonth = ''
    for (let w = 0; w < weekCols.length; w++) {
      const firstDayInWeek = weekCols[w].find((d) => d !== null)
      if (firstDayInWeek) {
        const date = new Date(firstDayInWeek.date)
        const month = date.toLocaleString('default', { month: 'short' })
        if (month !== lastMonth) {
          labels.push({ label: month, col: w })
          lastMonth = month
        }
      }
    }

    return { weeks: weekCols, monthLabels: labels }
  }, [days])

  return (
    <div
      className="rounded-2xl p-5 overflow-x-auto"
      style={{ background: 'var(--color-heatmap-bg)' }}
    >
      {/* Contribution count header */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-gray-300">
          {totalDaysStudied ?? days.filter((d) => d.active).length} contributions in the last year
        </p>
        <button className="text-xs text-gray-400 hover:text-gray-300 transition-colors">
          Contribution settings ▸
        </button>
      </div>

      {/* Month labels */}
      <div className="flex mb-1" style={{ paddingLeft: '32px' }}>
        {monthLabels.map(({ label, col }) => (
          <span
            key={`${label}-${col}`}
            className="text-[10px] text-gray-400 font-medium"
            style={{
              position: 'relative',
              left: `${col * 17}px`,
              marginRight: col === 0 ? '0' : '-8px',
            }}
          >
            {label}
          </span>
        ))}
      </div>

      {/* Grid: row labels + heatmap squares */}
      <div className="flex gap-0">
        {/* Row labels (Mon, Wed, Fri) */}
        <div className="flex flex-col justify-between pr-2 py-0.5" style={{ minWidth: '28px' }}>
          {ROW_LABELS.map((label, i) => (
            <span
              key={i}
              className="text-[10px] font-medium leading-none"
              style={{
                height: '14px',
                display: 'flex',
                alignItems: 'center',
                color: label === 'Mon' || label === 'Wed' || label === 'Fri' ? '#34d399' : 'transparent',
              }}
            >
              {label || '\u00A0'}
            </span>
          ))}
        </div>

        {/* Heatmap squares */}
        <div className="heatmap-grid">
          {weeks.map((week, wIdx) =>
            week.map((day, dIdx) => {
              if (!day) {
                return (
                  <div
                    key={`${wIdx}-${dIdx}`}
                    className="heatmap-square"
                    style={{ background: 'transparent' }}
                  />
                )
              }
              const intensity = day.active ? Math.min(4, Math.max(1, day.intensity)) : 0
              return (
                <div
                  key={`${wIdx}-${dIdx}`}
                  className="heatmap-square"
                  style={{ background: HEATMAP_COLORS[intensity] }}
                  title={`${day.date}: ${day.active ? `${day.intensity} activities` : 'No activity'}`}
                />
              )
            })
          )}
        </div>
      </div>

      {/* Legend + footer */}
      <div className="flex items-center justify-between mt-3">
        <a href="#" className="text-[11px] text-gray-400 hover:text-gray-300 transition-colors">
          Learn how we count contributions
        </a>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-gray-400">Less</span>
          {HEATMAP_COLORS.map((color, i) => (
            <div
              key={i}
              className="w-3 h-3 rounded-sm"
              style={{ background: color }}
            />
          ))}
          <span className="text-[11px] text-gray-400">More</span>
        </div>
      </div>
    </div>
  )
}
