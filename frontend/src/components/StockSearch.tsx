import { useState, useEffect, useRef, useCallback } from "react"
import { cn } from "@/lib/utils"
import { Input } from "@/components/ui/input"
import { Search, X, Check, Loader2, ChevronLeft, ChevronRight } from "lucide-react"
import { searchStocks, StockResult } from "@/lib/api"

interface StockSearchProps {
  onSelect: (stock: StockResult) => void
  disabled?: boolean
  selectedStock?: StockResult | null
  onClear?: () => void
  onSearchChange?: (isSearching: boolean) => void
}

export function StockSearch({
  onSelect,
  disabled = false,
  selectedStock,
  onClear,
  onSearchChange,
}: StockSearchProps) {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<StockResult[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const debounceRef = useRef<NodeJS.Timeout>()
  const nameScrollRef = useRef<HTMLDivElement>(null)

  const scrollName = (direction: 'left' | 'right') => {
    if (nameScrollRef.current) {
      const scrollAmount = direction === 'left' ? -80 : 80
      nameScrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' })
    }
  }

  // Debounced search
  const performSearch = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 1) {
      setResults([])
      setIsOpen(false)
      return
    }

    setIsLoading(true)
    try {
      const response = await searchStocks(searchQuery)
      setResults(response.results)
      setIsOpen(response.results.length > 0)
      setHighlightedIndex(0)
    } catch (error) {
      console.error("Stock search error:", error)
      setResults([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    debounceRef.current = setTimeout(() => {
      performSearch(query)
    }, 150) // 150ms debounce

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [query, performSearch])

  // Notify parent when search state changes
  useEffect(() => {
    onSearchChange?.(query.length > 0)
  }, [query, onSearchChange])

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isOpen) return

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault()
        setHighlightedIndex((prev) =>
          prev < results.length - 1 ? prev + 1 : prev
        )
        break
      case "ArrowUp":
        e.preventDefault()
        setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : 0))
        break
      case "Enter":
        e.preventDefault()
        if (results[highlightedIndex]) {
          handleSelect(results[highlightedIndex])
        }
        break
      case "Escape":
        e.preventDefault()
        setIsOpen(false)
        inputRef.current?.blur()
        break
    }
  }

  const handleSelect = (stock: StockResult) => {
    onSelect(stock)
    setQuery("")
    setIsOpen(false)
    setResults([])
  }

  const handleClear = () => {
    setQuery("")
    setResults([])
    setIsOpen(false)
    onClear?.()
    inputRef.current?.focus()
  }

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        listRef.current &&
        !listRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  // Show selected stock
  if (selectedStock) {
    return (
      <div className="relative">
        <div className="flex items-center gap-1 px-2 py-2 bg-card border border-border rounded-lg">
          <Check className="w-4 h-4 text-emerald-500 shrink-0" />
          <button
            onClick={() => scrollName('left')}
            className="shrink-0 p-0.5 hover:bg-muted rounded transition-colors"
          >
            <ChevronLeft className="w-3 h-3 text-muted-foreground" />
          </button>
          <div
            ref={nameScrollRef}
            className="flex-1 overflow-x-auto whitespace-nowrap scrollbar-hide"
            style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
          >
            <span className="font-medium text-foreground text-sm">
              {selectedStock.name}
            </span>
            <span className="text-muted-foreground text-sm ml-1">
              ({selectedStock.symbol})
            </span>
          </div>
          <button
            onClick={() => scrollName('right')}
            className="shrink-0 p-0.5 hover:bg-muted rounded transition-colors"
          >
            <ChevronRight className="w-3 h-3 text-muted-foreground" />
          </button>
          <span className="text-xs text-muted-foreground px-1.5 py-0.5 bg-muted rounded shrink-0">
            {selectedStock.exchange}
          </span>
          {!disabled && (
            <button
              onClick={handleClear}
              className="p-0.5 hover:bg-muted rounded transition-colors shrink-0"
            >
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query.length > 0 && results.length > 0 && setIsOpen(true)}
          placeholder="Search U.S. listed companies..."
          disabled={disabled}
          className="pl-10 pr-10 bg-background border-input text-foreground focus:border-primary"
        />
        {isLoading && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground animate-spin" />
        )}
        {!isLoading && query && (
          <button
            onClick={() => {
              setQuery("")
              setResults([])
              setIsOpen(false)
            }}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 hover:bg-muted rounded"
          >
            <X className="w-4 h-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && results.length > 0 && (
        <div
          ref={listRef}
          className="absolute z-50 w-full mt-1 bg-card border border-border rounded-lg shadow-xl overflow-hidden"
        >
          <div className="max-h-64 overflow-y-auto">
            {results.map((stock, index) => (
              <button
                key={stock.symbol}
                onClick={() => handleSelect(stock)}
                onMouseEnter={() => setHighlightedIndex(index)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 text-left transition-colors",
                  index === highlightedIndex
                    ? "bg-muted"
                    : "hover:bg-muted/50"
                )}
              >
                <span className="font-mono font-medium text-foreground min-w-[60px]">
                  {stock.symbol}
                </span>
                <span className="flex-1 text-sm text-muted-foreground truncate">
                  {stock.name}
                </span>
                <span className="text-xs text-muted-foreground px-2 py-0.5 bg-muted rounded">
                  {stock.exchange}
                </span>
              </button>
            ))}
          </div>
          <div className="px-3 py-2 border-t border-border text-xs text-muted-foreground">
            ↑↓ navigate · Enter select · Esc close
          </div>
        </div>
      )}
    </div>
  )
}

export default StockSearch
