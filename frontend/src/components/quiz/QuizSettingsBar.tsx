import { Plus, X } from 'lucide-react'

interface QuizSettingsBarProps {
  numQuestions: number
  onNumQuestionsChange: (value: number) => void
  questionStyle: string
  onQuestionStyleChange: (value: string) => void
  onStartOver: () => void
  onClearAll: () => void
}

const STYLE_OPTIONS = [
  'Mix it up!',
  'Multiple Choice',
  'True / False',
  'Short Answer',
  'Fill in the Blank',
]

export default function QuizSettingsBar({
  numQuestions,
  onNumQuestionsChange,
  questionStyle,
  onQuestionStyleChange,
  onStartOver,
  onClearAll,
}: QuizSettingsBarProps) {
  return (
    <div className="panel-card flex flex-wrap items-center gap-4">
      {/* How many questions? */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-600">How many questions?</span>
        <input
          type="number"
          min={1}
          max={20}
          value={numQuestions}
          onChange={(e) => onNumQuestionsChange(Math.max(1, parseInt(e.target.value) || 1))}
          className="w-14 bg-white border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-center text-gray-800 focus:outline-none focus:border-gray-300"
        />
      </div>

      {/* Question style dropdown */}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-gray-600">Question style</span>
        <select
          value={questionStyle}
          onChange={(e) => onQuestionStyleChange(e.target.value)}
          className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-300 cursor-pointer"
        >
          {STYLE_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <button onClick={onStartOver} className="btn-secondary text-xs">
          <Plus size={14} />
          Start Over
        </button>
        <button
          onClick={onClearAll}
          className="text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors px-2 py-1"
        >
          Clear All
        </button>
      </div>
    </div>
  )
}
