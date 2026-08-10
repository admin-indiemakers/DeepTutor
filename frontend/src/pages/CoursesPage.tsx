import { motion } from 'framer-motion'
import { GraduationCap } from 'lucide-react'

export default function CoursesPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="w-10 h-10 rounded-2xl bg-violet-100 text-violet-600 flex items-center justify-center">
          <GraduationCap size={20} />
        </div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Courses</h1>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white border border-slate-200/80 rounded-[20px] p-8 text-center shadow-sm"
      >
        <div className="w-16 h-16 rounded-3xl bg-violet-50 text-violet-600 flex items-center justify-center mx-auto mb-4 border border-violet-100">
          <GraduationCap size={28} />
        </div>
        <h2 className="text-lg font-bold text-slate-900 mb-2">My Enrolled Courses</h2>
        <p className="text-slate-500 text-sm max-w-md mx-auto leading-relaxed">
          Access your courses, syllabus, curriculum structure, and download reference files. 
          This page is currently a placeholder stub for the student portal demo.
        </p>
      </motion.div>
    </div>
  )
}
