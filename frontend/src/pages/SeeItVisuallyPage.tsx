import { useState } from 'react'
import PageHeader from '../components/PageHeader'
import VisualPromptPanel from '../components/visual/VisualPromptPanel'
import StudyMaterialCard from '../components/shared/StudyMaterialCard'
import GenerationResult from '../components/shared/GenerationResult'

export default function SeeItVisuallyPage() {
  const [prompt, setPrompt] = useState('')
  const [displayMode, setDisplayMode] = useState('Let AI decide')
  const [isGenerating, setIsGenerating] = useState(false)
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  const handleSubmit = () => {
    if (!prompt.trim()) return
    setSubmittedPrompt(prompt)
    setIsGenerating(true)
    setResult(null)

    // NOTE: No backend endpoint exists for visual generation (see plan risk #9).
    // Simulating a mock loading state for UI demonstration.
    setTimeout(() => {
      setIsGenerating(false)
      setResult(
        `[MOCK RESULT — No backend visual generation endpoint exists yet]\n\n` +
        `Visual generation for "${prompt}" with mode "${displayMode}" would appear here.\n\n` +
        `To implement this, a POST /visual/generate endpoint needs to be added to the backend.`
      )
    }, 3000)
  }

  const handleStartOver = () => {
    setPrompt('')
    setDisplayMode('Let AI decide')
    setSubmittedPrompt(null)
    setResult(null)
    setIsGenerating(false)
  }

  const handleUploadFile = () => {
    console.log('Upload file clicked')
  }

  const handlePickBook = () => {
    console.log('Pick a saved book clicked')
  }

  const handlePasteText = () => {
    console.log('Paste text clicked')
  }

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-5">
      <PageHeader title="See It Visually" emoji="🎨" />

      {/* Visual Prompt Panel */}
      <VisualPromptPanel
        prompt={prompt}
        onPromptChange={setPrompt}
        displayMode={displayMode}
        onDisplayModeChange={setDisplayMode}
        onSubmit={handleSubmit}
        onStartOver={handleStartOver}
        isGenerating={isGenerating}
      />

      {/* Add Your Study Material Card (shared) */}
      <StudyMaterialCard
        title="Add Your Study Material"
        description="Upload your notes, textbook pages — and the picture or animation will be based on what you added."
        onUploadFile={handleUploadFile}
        onPickBook={handlePickBook}
        onPasteText={handlePasteText}
      />

      {/* Generation Result Area (shown after submit) */}
      {submittedPrompt && (
        <GenerationResult
          category="Quiz Generation"
          userPrompt={submittedPrompt}
          isLoading={isGenerating}
          result={result}
        />
      )}
    </div>
  )
}
