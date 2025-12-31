'use client';

import { useState, useRef, useEffect } from 'react';
import { Mic, MicOff } from 'lucide-react';

interface VoiceInputProps {
  onTranscription: (text: string) => void;
}

// Define SpeechRecognition types for TypeScript
interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  }
}

export function VoiceInput({ onTranscription }: VoiceInputProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const [interimText, setInterimText] = useState('');
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    // Check for browser support
    const SpeechRecognitionAPI =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognitionAPI) {
      setIsSupported(false);
      return;
    }

    // Initialize speech recognition
    const recognition = new SpeechRecognitionAPI();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = '';
      let interimTranscript = '';

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      if (finalTranscript) {
        onTranscription(finalTranscript);
        setInterimText('');
      } else {
        setInterimText(interimTranscript);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      console.error('Speech recognition error:', event.error);
      setIsRecording(false);
      setInterimText('');
    };

    recognition.onend = () => {
      setIsRecording(false);
      setInterimText('');
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.abort();
    };
  }, [onTranscription]);

  const toggleRecording = () => {
    if (!recognitionRef.current) return;

    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      setIsRecording(true);
    }
  };

  if (!isSupported) {
    return (
      <button
        disabled
        className="p-3 md:p-4 text-content-tertiary rounded-xl md:rounded-2xl cursor-not-allowed 
                   bg-surface-tertiary border border-edge-subtle opacity-50 flex-shrink-0"
        title="Voice input not supported in this browser"
      >
        <MicOff className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="relative flex-shrink-0">
      <button
        onClick={toggleRecording}
        className={`p-3 md:p-4 rounded-xl md:rounded-2xl transition-all relative overflow-hidden
          ${isRecording
            ? 'bg-amber/20 text-amber border border-amber/50 shadow-[0_0_20px_-5px_rgba(255,184,0,0.5)]'
            : 'bg-surface-tertiary text-content-secondary border border-edge-subtle hover:border-edge-medium hover:text-content-primary hover:bg-surface-elevated'
          }`}
        title={isRecording ? 'Stop recording' : 'Start voice input'}
      >
        <Mic className={`w-5 h-5 relative z-10 ${isRecording ? 'animate-pulse' : ''}`} />
        
        {/* Recording pulse rings */}
        {isRecording && (
          <>
            <span className="absolute inset-0 rounded-xl md:rounded-2xl border-2 border-amber/50 pulse-ring" />
            <span className="absolute inset-0 rounded-xl md:rounded-2xl border-2 border-amber/30 pulse-ring" 
                  style={{ animationDelay: '0.5s' }} />
          </>
        )}
      </button>
      
      {/* Recording indicator dot */}
      {isRecording && (
        <span className="absolute -top-1 -right-1 w-3 h-3 bg-amber rounded-full 
                        shadow-[0_0_10px_2px_rgba(255,184,0,0.6)]">
          <span className="absolute inset-0 rounded-full bg-amber animate-ping opacity-75" />
        </span>
      )}
      
      {/* Interim text tooltip */}
      {interimText && (
        <div className="absolute bottom-full right-0 mb-3 p-3 rounded-xl max-w-[200px] md:max-w-xs
                       bg-surface-elevated border border-edge-medium shadow-glow-sm
                       animate-in z-10">
          <span className="text-content-tertiary text-xs font-medium">Hearing:</span>
          <p className="text-content-primary text-sm mt-1 break-words">{interimText}</p>
        </div>
      )}
    </div>
  );
}
