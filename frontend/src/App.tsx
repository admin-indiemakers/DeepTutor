import { useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from './stores/authStore'
import { useChatStore } from './stores/chatStore'
import { chatApi } from './services/api'
import Layout from './components/Layout'
import MouseSpotlight from './components/MouseSpotlight'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import StudyPlanPage from './pages/StudyPlanPage'
import ChatPage from './pages/ChatPage'
import QuizPage from './pages/QuizPage'
import QuizResultPage from './pages/QuizResultPage'
import ProgressPage from './pages/ProgressPage'
import FlashcardsPage from './pages/FlashcardsPage'
import LeaderboardPage from './pages/LeaderboardPage'
import TakeQuizPage from './pages/TakeQuizPage'
import SeeItVisuallyPage from './pages/SeeItVisuallyPage'
import WriteTogetherPage from './pages/WriteTogetherPage'
import MyBooksPage from './pages/MyBooksPage'
import MyStuffPage from './pages/MyStuffPage'
import SettingsPage from './pages/SettingsPage'
import PaymentInfoPage from './pages/PaymentInfoPage'
import RegistrationPage from './pages/RegistrationPage'
import CoursesPage from './pages/CoursesPage'
import DropSemesterPage from './pages/DropSemesterPage'
import ResultPage from './pages/ResultPage'
import NoticePage from './pages/NoticePage'
import SchedulePage from './pages/SchedulePage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
})

/** Pre-fetches sessions and ensures data is scoped to the current user only.
 * - On login/user-switch: clears old sessions immediately then fetches fresh ones
 * - On logout: wipes all cached session data
 */
function GlobalSessionLoader() {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const setSessions = useChatStore((s) => s.setSessions)
  const setActiveSession = useChatStore((s) => s.setActiveSession)
  const prevUserIdRef = useRef<string | null>(null)

  useEffect(() => {
    const currentUserId = user?.id ?? null

    // Logout: clear everything immediately
    if (!isAuthenticated) {
      setSessions([])
      setActiveSession(null)
      prevUserIdRef.current = null
      queryClient.clear() // wipe all React Query caches
      return
    }

    // User switched (different account): clear old data before loading new
    if (prevUserIdRef.current !== null && prevUserIdRef.current !== currentUserId) {
      setSessions([])
      setActiveSession(null)
      queryClient.clear()
    }
    prevUserIdRef.current = currentUserId

    // Fetch this user's sessions
    chatApi.sessions()
      .then((res) => setSessions(res.data))
      .catch(() => {/* page-level queries will retry */})
  }, [isAuthenticated, user?.id])

  return null
}

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return isAuthenticated ? <>{children}</> : <Navigate to="/" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  return !isAuthenticated ? <>{children}</> : <Navigate to="/app/dashboard" replace />
}

import { useParams } from 'react-router-dom'
function ChatRedirect() {
  const { sessionId } = useParams()
  return <Navigate to={sessionId ? `/app/chat/${sessionId}` : '/app/chat'} replace />
}


export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <GlobalSessionLoader />
        <Routes>
          {/* Public Hero Landing Page */}
          <Route path="/" element={<LandingPage />} />
          <Route path="/hero" element={<LandingPage />} />

          {/* Auth */}
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

          {/* Protected Application Routes — all nested under Layout shell */}
          <Route path="/app" element={<PrivateRoute><Layout /></PrivateRoute>}>
            <Route index element={<Navigate to="/app/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="study-plan" element={<StudyPlanPage />} />
            <Route path="chat/:sessionId?" element={<ChatPage />} />
            <Route path="leaderboard" element={<LeaderboardPage />} />
            <Route path="quiz/:topicId" element={<QuizPage />} />
            <Route path="quiz/:topicId/result" element={<QuizResultPage />} />
            <Route path="flashcards/:topicId?" element={<FlashcardsPage />} />
            <Route path="progress" element={<ProgressPage />} />

            {/* New Adhyapikha.ai routes */}
            <Route path="take-quiz" element={<TakeQuizPage />} />
            <Route path="see-visually" element={<SeeItVisuallyPage />} />
            <Route path="write-together" element={<WriteTogetherPage />} />
            <Route path="my-books" element={<MyBooksPage />} />
            <Route path="my-stuff" element={<MyStuffPage />} />
            <Route path="settings" element={<SettingsPage />} />

            {/* Portal pages */}
            <Route path="payment-info" element={<PaymentInfoPage />} />
            <Route path="registration" element={<RegistrationPage />} />
            <Route path="courses" element={<CoursesPage />} />
            <Route path="drop-semester" element={<DropSemesterPage />} />
            <Route path="result" element={<ResultPage />} />
            <Route path="notice" element={<NoticePage />} />
            <Route path="schedule" element={<SchedulePage />} />
          </Route>

          {/* Root-level redirects for convenience (keep backward compat) */}
          <Route path="/dashboard" element={<Navigate to="/app/dashboard" replace />} />
          <Route path="/study-plan" element={<Navigate to="/app/study-plan" replace />} />
          <Route path="/chat/:sessionId?" element={<ChatRedirect />} />
          <Route path="/chat" element={<ChatRedirect />} />
          <Route path="/leaderboard" element={<Navigate to="/app/leaderboard" replace />} />
          <Route path="/progress" element={<Navigate to="/app/progress" replace />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
