import { Sparkles } from 'lucide-react'

interface GenerationResultProps {
  category?: string
  userPrompt: string
  isLoading: boolean
  result?: string | null
}

export default function GenerationResult({
  category,
  userPrompt,
  isLoading,
  result,
}: GenerationResultProps) {
  return (
    <div className="space-y-4 mt-4">
      {/* Category pill tag — top right */}
      {category && (
        <div className="flex justify-end">
          <span className="text-xs text-gray-400 italic">{category}</span>
        </div>
      )}

      {/* User-turn bubble */}
      <div className="flex justify-end">
        <div className="bg-gray-100 rounded-2xl rounded-tr-md px-4 py-2.5 max-w-md">
          <p className="text-sm text-gray-800">{userPrompt}</p>
        </div>
      </div>

      {/* Loading / AI response row */}
      {isLoading && (
        <div className="flex items-center gap-3 py-3">
          <Sparkles size={18} className="text-gray-400 animate-spin" style={{ animationDuration: '2s' }} />
          <span className="text-sm text-gray-500 font-medium">
            Adhyapikha.ai Reasoning…
          </span>
        </div>
      )}

      {/* Result content (placeholder since no backend exists for visual generation) */}
      {result && !isLoading && (
        <div className="bg-white rounded-2xl border border-gray-200 p-5">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">{result}</p>
        </div>
      )}
    </div>
  )
}
