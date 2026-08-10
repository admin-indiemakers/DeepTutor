import { Sparkles } from 'lucide-react'

interface QuizPromptPanelProps {
  topic: string
  onTopicChange: (value: string) => void
  onSubmit: () => void
  isGenerating?: boolean
}

export default function QuizPromptPanel({
  topic,
  onTopicChange,
  onSubmit,
  isGenerating = false,
}: QuizPromptPanelProps) {
  return (
    <div className="panel-card flex items-center gap-3">
      {/* Sparkle icon */}
      <div className="flex-shrink-0 text-gray-400">
        <Sparkles size={20} />
      </div>

      {/* Pill-shaped text input */}
      <input
        type="text"
        value={topic}
        onChange={(e) => onTopicChange(e.target.value)}
        placeholder='What do you want to be quizzed on? (e.g. "Photosynthesis", "Fractions", "Indian History")'
        className="flex-1 bg-white border border-gray-200 rounded-full px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-gray-300 transition-colors"
        onKeyDown={(e) => {
          if (e.key === 'Enter' && topic.trim()) onSubmit()
        }}
      />

      {/* Green primary button */}
      <button
        onClick={onSubmit}
        disabled={!topic.trim() || isGenerating}
        className="btn-action whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isGenerating ? (
          <>
            <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Generating…
          </>
        ) : (
          <>
            Make My Quiz
            <Sparkles size={14} />
          </>
        )}
      </button>
    </div>
  )
}
