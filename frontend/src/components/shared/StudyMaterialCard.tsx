import { FileText, Upload, BookOpen, ClipboardPaste, ChevronDown } from 'lucide-react'

interface StudyMaterialCardProps {
  title?: string
  description?: string
  onUploadFile?: () => void
  onPickBook?: () => void
  onPasteText?: () => void
}

export default function StudyMaterialCard({
  title = 'Add Your Study Material',
  description = 'Upload your notes, textbook pages, or paste text — and the content will be based on what you added.',
  onUploadFile,
  onPickBook,
  onPasteText,
}: StudyMaterialCardProps) {
  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4">
      {/* Left: icon + text */}
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center flex-shrink-0">
          <FileText size={18} className="text-blue-500" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-bold text-gray-900">{title}</p>
          <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{description}</p>
        </div>
      </div>

      {/* Right: action buttons */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <button
          onClick={onUploadFile}
          className="btn-secondary"
        >
          <Upload size={14} />
          Upload a File
        </button>
        <button
          onClick={onPickBook}
          className="btn-secondary"
        >
          <BookOpen size={14} />
          Pick a Saved Book
          <ChevronDown size={12} className="text-gray-400 ml-0.5" />
        </button>
        <button
          onClick={onPasteText}
          className="btn-secondary"
        >
          <ClipboardPaste size={14} />
          Paste Text
        </button>
      </div>
    </div>
  )
}
