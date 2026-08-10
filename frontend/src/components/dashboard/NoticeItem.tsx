interface NoticeItemProps {
  title: string
  text: string
  onSeeMore?: () => void
}

export default function NoticeItem({ title, text, onSeeMore }: NoticeItemProps) {
  return (
    <div className="pb-4 border-b border-slate-200/60 last:border-b-0 last:pb-0 space-y-1">
      {/* Notice Title */}
      <h3 className="text-xs font-extrabold text-slate-900 leading-snug tracking-tight">
        {title}
      </h3>
      
      {/* Notice Body */}
      <p className="text-[11px] text-slate-400 font-medium leading-relaxed line-clamp-2">
        {text}
      </p>

      {/* Action Link */}
      <button 
        onClick={onSeeMore}
        className="text-[10px] text-violet-600 hover:text-violet-700 font-extrabold transition-colors pt-0.5 leading-none block"
      >
        See more
      </button>
    </div>
  )
}
