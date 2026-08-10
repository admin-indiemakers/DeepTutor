interface PageHeaderProps {
  title: string
  emoji: string
  children?: React.ReactNode
}

export default function PageHeader({ title, emoji, children }: PageHeaderProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl sm:text-3xl font-black text-gray-900 tracking-tight">
          {title}
        </h1>
        <span className="text-2xl sm:text-3xl" role="img" aria-label="page icon">
          {emoji}
        </span>
      </div>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </div>
  )
}
