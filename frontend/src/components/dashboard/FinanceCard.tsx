import React from 'react'

interface FinanceCardProps {
  title: string
  amount: string
  icon: React.ComponentType<any>
  colorClass: string
  isSelected?: boolean
  onClick?: () => void
}

export default function FinanceCard({
  title,
  amount,
  icon: Icon,
  colorClass,
  isSelected = false,
  onClick,
}: FinanceCardProps) {
  return (
    <div
      onClick={onClick}
      className={`p-6 bg-white rounded-[20px] transition-all duration-300 cursor-pointer flex flex-col justify-between ${
        isSelected
          ? 'border-2 border-portal-primary shadow-xl shadow-purple-900/5 -translate-y-1 scale-[1.01]'
          : 'border border-slate-200/80 hover:border-violet-300 hover:shadow-md shadow-sm'
      }`}
    >
      {/* Icon Frame */}
      <div className="flex items-start justify-between mb-4">
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center ${colorClass}`}>
          <Icon size={22} className="stroke-[2]" />
        </div>
      </div>

      {/* Details Stack */}
      <div>
        <span className="block text-2xl lg:text-3xl font-black text-slate-950 tracking-tight leading-none">
          {amount}
        </span>
        <span className="block text-[11px] font-extrabold text-slate-400 uppercase tracking-wider mt-1.5 leading-none">
          {title}
        </span>
      </div>
    </div>
  )
}
