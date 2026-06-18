import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

interface TextGenerateProps {
  text: string
  className?: string
  speed?: number
  delay?: number
  onComplete?: () => void
}

export function TextGenerate({
  text,
  className,
  speed = 30,
  delay = 0,
  onComplete,
}: TextGenerateProps) {
  const [displayedText, setDisplayedText] = useState("")
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isStarted, setIsStarted] = useState(false)

  useEffect(() => {
    const startTimeout = setTimeout(() => {
      setIsStarted(true)
    }, delay)

    return () => clearTimeout(startTimeout)
  }, [delay])

  useEffect(() => {
    if (!isStarted) return

    if (currentIndex < text.length) {
      const timeout = setTimeout(() => {
        setDisplayedText((prev) => prev + text[currentIndex])
        setCurrentIndex((prev) => prev + 1)
      }, speed)

      return () => clearTimeout(timeout)
    } else if (onComplete) {
      onComplete()
    }
  }, [currentIndex, isStarted, text, speed, onComplete])

  return (
    <span className={cn("inline-block", className)}>
      {displayedText.split("").map((char, i) => (
        <motion.span
          key={i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.1 }}
        >
          {char}
        </motion.span>
      ))}
      {currentIndex < text.length && (
        <motion.span
          animate={{ opacity: [1, 0] }}
          transition={{ duration: 0.5, repeat: Infinity }}
          className="inline-block w-[2px] h-[1em] bg-primary ml-[1px] align-middle"
          style={{
            boxShadow: "0 0 5px rgba(59, 130, 246, 0.8)",
          }}
        />
      )}
    </span>
  )
}
