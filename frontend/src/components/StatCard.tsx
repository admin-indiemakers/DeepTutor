import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  subtitle: string
  icon: LucideIcon
  accentColor: string // CSS color value e.g. '#f97316'
}

export default function StatCard({ title, value, subtitle, icon: Icon, accentColor }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5 relative overflow-hidden border border-gray-200"
    >
      {/* Icon badge top-right */}
      <div className="absolute top-4 right-4">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center"
          style={{ backgroundColor: `${accentColor}15` }}
        >
          <Icon size={16} style={{ color: accentColor }} />
        </div>
      </div>

      {/* Decorative soft circle bottom-right */}
      <div
        className="absolute -bottom-6 -right-6 w-24 h-24 rounded-full opacity-10"
        style={{ backgroundColor: accentColor }}
      />

      {/* Content */}
      <div className="relative z-10">
        <p className="text-sm font-medium text-gray-500 mb-2">{title}</p>
        <p className="text-3xl font-black text-gray-900 mb-1">{value}</p>
        <p className="text-xs text-gray-400">{subtitle}</p>
      </div>
    </motion.div>
  )
}
