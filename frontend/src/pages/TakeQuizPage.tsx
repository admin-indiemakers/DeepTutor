import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PageHeader from '../components/PageHeader'
import QuizPromptPanel from '../components/quiz/QuizPromptPanel'
import QuizSettingsBar from '../components/quiz/QuizSettingsBar'
import StudyMaterialCard from '../components/shared/StudyMaterialCard'
import { quizApi } from '../services/api'
import { useChatStore } from '../stores/chatStore'

export default function TakeQuizPage() {
  const navigate = useNavigate()
  const activeSession = useChatStore((s) => s.activeSession)

  const [topic, setTopic] = useState('')
  const [numQuestions, setNumQuestions] = useState(3)
  const [questionStyle, setQuestionStyle] = useState('Mix it up!')
  const [isGenerating, setIsGenerating] = useState(false)

  const handleMakeQuiz = async () => {
    if (!topic.trim()) return
    setIsGenerating(true)
    try {
      const difficultyMap: Record<string, string> = {
        'Mix it up!': 'medium',
        'Multiple Choice': 'medium',
        'True / False': 'easy',
        'Short Answer': 'hard',
        'Fill in the Blank': 'medium',
      }
      const result = await quizApi.generate({
        topic_id: activeSession?.topic_id || 'general',
        custom_topic: topic,
        difficulty: difficultyMap[questionStyle] || 'medium',
        num_questions: numQuestions,
        session_id: activeSession?.id,
      })
      // Navigate to the quiz-taking page if quiz was generated successfully
      if (result.data?.id) {
        navigate(`/app/quiz/${result.data.topic_id || 'general'}`)
      }
    } catch (err) {
      console.error('Quiz generation failed:', err)
    } finally {
      setIsGenerating(false)
    }
  }

  const handleStartOver = () => {
    setTopic('')
    setNumQuestions(3)
    setQuestionStyle('Mix it up!')
  }

  const handleClearAll = () => {
    setTopic('')
  }

  const handleUploadFile = () => {
    // TODO: Wire to documentsApi.upload() with file picker
    console.log('Upload file clicked')
  }

  const handlePickBook = () => {
    // TODO: Wire to documentsApi.list() dropdown
    console.log('Pick a saved book clicked')
  }

  const handlePasteText = () => {
    // TODO: Open paste text modal
    console.log('Paste text clicked')
  }

  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-5">
      <PageHeader title="Take a Quiz" emoji="📝" />

      {/* Quiz Prompt Panel */}
      <QuizPromptPanel
        topic={topic}
        onTopicChange={setTopic}
        onSubmit={handleMakeQuiz}
        isGenerating={isGenerating}
      />

      {/* Add Your Study Material Card */}
      <StudyMaterialCard
        title="Add Your Study Material"
        description="Upload your notes, textbook pages, or paste text — and the quiz will be made from what you added."
        onUploadFile={handleUploadFile}
        onPickBook={handlePickBook}
        onPasteText={handlePasteText}
      />

      {/* Quiz Settings Bar */}
      <QuizSettingsBar
        numQuestions={numQuestions}
        onNumQuestionsChange={setNumQuestions}
        questionStyle={questionStyle}
        onQuestionStyleChange={setQuestionStyle}
        onStartOver={handleStartOver}
        onClearAll={handleClearAll}
      />
    </div>
  )
}
