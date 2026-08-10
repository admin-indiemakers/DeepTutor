import PageHeader from '../components/PageHeader'

export default function MyStuffPage() {
  return (
    <div className="p-6 md:p-8 max-w-6xl mx-auto">
      <PageHeader title="My Stuff" emoji="📦" />
      <div className="glass-card p-12 text-center border border-gray-200">
        <p className="text-lg font-bold text-gray-700 mb-2">Coming Soon</p>
        <p className="text-sm text-gray-500">Your saved quizzes, flashcards, and study plans will live here.</p>
      </div>
    </div>
  )
}
