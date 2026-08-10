import { Laptop, Database } from 'lucide-react'

interface CourseCardProps {
  title: string
  iconType: string
  isSelected?: boolean
  onClick?: () => void
}

export default function CourseCard({
  title,
  iconType,
  isSelected = false,
  onClick,
}: CourseCardProps) {
  // Select appropriate icon
  const Icon = iconType === 'laptop' ? Laptop : Database
  const iconColor = iconType === 'laptop' ? 'text-violet-600 bg-violet-50' : 'text-indigo-600 bg-indigo-50'

  return (
    <div
      onClick={onClick}
      className={`p-5 bg-white rounded-[20px] transition-all duration-300 cursor-pointer flex items-center justify-between gap-4 ${
        isSelected
          ? 'border-2 border-portal-primary shadow-lg shadow-purple-900/5'
          : 'border border-slate-200/80 hover:border-violet-300 shadow-sm'
      }`}
    >
      {/* Left side: Icon Tile + Title stack */}
      <div className="flex items-center gap-4">
        {/* Illustrative Icon Tile */}
        <div className={`w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0 ${iconColor}`}>
          <Icon size={22} className="stroke-[2]" />
        </div>
        
        {/* Course Title */}
        <span className="text-xs font-extrabold text-slate-900 leading-snug tracking-tight max-w-[150px] line-clamp-2">
          {title}
        </span>
      </div>

      {/* Right side: View Pill Button */}
      <button className="bg-portal-primary hover:bg-[#6d28d9] text-white text-[10px] font-extrabold px-4 py-2 rounded-full shadow-sm shadow-purple-900/10 transition-colors flex-shrink-0">
        View
      </button>
    </div>
  )
}
