import { motion } from 'framer-motion'
import { GraduationCap, Award, BookOpen } from 'lucide-react'

interface HeroBannerProps {
  userName: string
}

export default function HeroBanner({ userName }: HeroBannerProps) {
  // Format current date matching the reference (e.g. September 4, 2023)
  const today = new Date()
  const formattedDate = today.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full bg-gradient-to-r from-[#7c3aed] to-[#4f46e5] rounded-[24px] text-white p-8 relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-6 shadow-lg shadow-purple-900/10"
    >
      {/* Decorative Glowing Background Gradients */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-white/10 rounded-full blur-3xl -mr-20 -mt-20 pointer-events-none" />
      <div className="absolute -bottom-10 left-1/3 w-60 h-60 bg-indigo-400/20 rounded-full blur-2xl pointer-events-none" />

      {/* Text Details Panel */}
      <div className="relative z-10 flex-1">
        <div className="inline-block bg-white/15 backdrop-blur-md px-3 py-1 rounded-full text-[10px] font-extrabold tracking-wider uppercase text-white/90">
          {formattedDate}
        </div>
        <h1 className="text-3xl lg:text-4xl font-black tracking-tight leading-tight mt-4">
          Welcome back, {userName}!
        </h1>
        <p className="text-white/85 text-xs font-medium mt-1.5 max-w-md">
          Always stay updated in your student portal. Check your syllabus, pending dues, and academic calendar notices.
        </p>
      </div>

      {/* Decorative Illustration Area (Student 3D-Like Graphic Setup) */}
      <div className="relative w-44 h-44 flex-shrink-0 flex items-center justify-center">
        {/* Floating background decorative dots/badges */}
        <motion.div
          animate={{ y: [0, -8, 0] }}
          transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
          className="absolute top-2 left-2 w-10 h-10 rounded-xl bg-amber-400 text-amber-950 flex items-center justify-center shadow-lg border border-amber-300"
        >
          <Award size={18} className="stroke-[2.5]" />
        </motion.div>
        
        <motion.div
          animate={{ y: [0, 8, 0] }}
          transition={{ repeat: Infinity, duration: 3.5, ease: 'easeInOut' }}
          className="absolute bottom-2 right-2 w-10 h-10 rounded-xl bg-teal-400 text-teal-950 flex items-center justify-center shadow-lg border border-teal-300"
        >
          <BookOpen size={18} className="stroke-[2.5]" />
        </motion.div>

        {/* Central Character/Graduation Tile Representation */}
        <div className="w-32 h-32 rounded-3xl bg-white/10 backdrop-blur-md border border-white/20 shadow-inner flex items-center justify-center relative">
          {/* Inner Circle Glow */}
          <div className="absolute inset-2 rounded-full bg-gradient-to-br from-violet-400/30 to-indigo-500/30 flex items-center justify-center">
            <GraduationCap size={56} className="text-white drop-shadow-md stroke-[1.5]" />
          </div>
          
          {/* Floating Orbit Rings (CSS decoration) */}
          <div className="absolute inset-0 rounded-3xl border border-white/5 rotate-12 scale-105 pointer-events-none" />
        </div>
      </div>
    </motion.div>
  )
}
