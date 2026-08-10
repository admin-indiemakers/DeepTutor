import { motion } from 'framer-motion'
import { Award } from 'lucide-react'

export default function ResultPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-3"
      >
        <div className="w-10 h-10 rounded-2xl bg-violet-100 text-violet-600 flex items-center justify-center">
          <Award size={20} />
        </div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">Academic Results</h1>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="bg-white border border-slate-200/80 rounded-[20px] p-8 text-center shadow-sm"
      >
        <div className="w-16 h-16 rounded-3xl bg-violet-50 text-violet-600 flex items-center justify-center mx-auto mb-4 border border-violet-100">
          <Award size={28} />
        </div>
        <h2 className="text-lg font-bold text-slate-900 mb-2">Semester Grades & GPA</h2>
        <p className="text-slate-500 text-sm max-w-md mx-auto leading-relaxed">
          Check your final exam results, mid-term grades, credits earned, and download official GPA transcripts. 
          This page is currently a placeholder stub for the student portal demo.
        </p>
      </motion.div>
    </div>
  )
}
