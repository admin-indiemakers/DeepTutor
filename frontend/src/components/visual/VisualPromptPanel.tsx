import { Sparkles, Plus } from 'lucide-react'

interface VisualPromptPanelProps {
  prompt: string
  onPromptChange: (value: string) => void
  displayMode: string
  onDisplayModeChange: (value: string) => void
  onSubmit: () => void
  onStartOver: () => void
  isGenerating?: boolean
}

const DISPLAY_MODES = [
  'Let AI decide',
  'Diagram',
  'Flowchart',
  'Mind Map',
  'Infographic',
  'Animation',
]

export default function VisualPromptPanel({
  prompt,
  onPromptChange,
  displayMode,
  onDisplayModeChange,
  onSubmit,
  onStartOver,
  isGenerating = false,
}: VisualPromptPanelProps) {
  return (
    <div className="panel-card space-y-3">
      {/* Top row: sparkle + input + button */}
      <div className="flex items-center gap-3">
        {/* Sparkle icon */}
        <div className="flex-shrink-0 text-gray-400">
          <Sparkles size={20} />
        </div>

        {/* Pill-shaped text input */}
        <input
          type="text"
          value={prompt}
          onChange={(e) => onPromptChange(e.target.value)}
          placeholder='What should I draw or explain? (e.g. "How the heart pumps blood", "Solar system")'
          className="flex-1 bg-white border border-gray-200 rounded-full px-4 py-2.5 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:border-gray-300 transition-colors"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && prompt.trim()) onSubmit()
          }}
        />

        {/* Green primary button */}
        <button
          onClick={onSubmit}
          disabled={!prompt.trim() || isGenerating}
          className="btn-action whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isGenerating ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Generating…
            </>
          ) : (
            <>
              Show Me
              <Sparkles size={14} />
            </>
          )}
        </button>
      </div>

      {/* Second row: display mode dropdown + start over */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 ml-8">
          <span className="text-xs font-medium text-gray-500">How to show it</span>
          <select
            value={displayMode}
            onChange={(e) => onDisplayModeChange(e.target.value)}
            className="bg-white border border-gray-200 rounded-lg px-3 py-1.5 text-sm text-gray-800 focus:outline-none focus:border-gray-300 cursor-pointer"
          >
            {DISPLAY_MODES.map((mode) => (
              <option key={mode} value={mode}>
                {mode}
              </option>
            ))}
          </select>
        </div>

        <button onClick={onStartOver} className="btn-secondary text-xs">
          <Plus size={14} />
          Start Over
        </button>
      </div>
    </div>
  )
}
