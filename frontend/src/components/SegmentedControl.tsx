interface SegmentedControlProps {
  options: string[]
  value: string
  onChange: (value: string) => void
}

export default function SegmentedControl({ options, value, onChange }: SegmentedControlProps) {
  return (
    <div className="flex items-center bg-gray-100 p-1 rounded-xl">
      {options.map((option) => {
        const isActive = option === value
        return (
          <button
            key={option}
            onClick={() => onChange(option)}
            className={`px-4 py-1.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
              isActive
                ? 'bg-[#0d9488] text-white shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {option}
          </button>
        )
      })}
    </div>
  )
}
