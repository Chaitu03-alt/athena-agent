import { useState, useEffect, useRef, useCallback } from 'react';
import { audio } from '../utils/audio';

// Type definitions for Web Speech API
interface IWindow extends Window {
  SpeechRecognition?: any;
  webkitSpeechRecognition?: any;
}

export type VoiceLanguage = 'en-IN' | 'hi-IN';

export interface VoiceControllerOptions {
  onTranscriptChange?: (text: string, isFinal: boolean) => void;
  onListeningStateChange?: (isListening: boolean) => void;
  onSpeakingStateChange?: (isSpeaking: boolean) => void;
  language?: VoiceLanguage;
}

export interface VoiceControllerReturn {
  isSupported: boolean;
  isListening: boolean;
  isSpeaking: boolean;
  language: VoiceLanguage;
  setLanguage: (lang: VoiceLanguage) => void;
  startListening: () => void;
  stopListening: () => void;
  toggleListening: () => void;
  speak: (text: string) => void;
  stopSpeaking: () => void;
}

export function useVoiceController(options: VoiceControllerOptions = {}): VoiceControllerReturn {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [language, setLanguage] = useState<VoiceLanguage>(options.language || 'en-IN');
  const [isSupported, setIsSupported] = useState(false);

  const recognitionRef = useRef<any>(null);
  const synthRef = useRef<SpeechSynthesis | null>(null);
  const activeUtteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  // Initialize Speech Recognition & Synthesis
  useEffect(() => {
    const customWindow = window as unknown as IWindow;
    const SpeechRecognitionConstructor =
      customWindow.SpeechRecognition || customWindow.webkitSpeechRecognition;

    const hasRecognition = typeof SpeechRecognitionConstructor !== 'undefined';
    const hasSynthesis = typeof window !== 'undefined' && 'speechSynthesis' in window;

    setIsSupported(hasRecognition || hasSynthesis);

    if (hasRecognition) {
      const recognition = new SpeechRecognitionConstructor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;
      recognition.lang = language;

      recognition.onstart = () => {
        setIsListening(true);
        options.onListeningStateChange?.(true);
        audio.play('keystroke');
      };

      recognition.onresult = (event: any) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const transcriptChunk = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            finalTranscript += transcriptChunk;
          } else {
            interimTranscript += transcriptChunk;
          }
        }

        const currentText = finalTranscript || interimTranscript;
        if (currentText) {
          options.onTranscriptChange?.(currentText, Boolean(finalTranscript));
        }
      };

      recognition.onerror = (err: any) => {
        if (err.error !== 'no-speech') {
          console.warn('[Athena Voice] Recognition error:', err.error);
        }
        setIsListening(false);
        options.onListeningStateChange?.(false);
      };

      recognition.onend = () => {
        setIsListening(false);
        options.onListeningStateChange?.(false);
      };

      recognitionRef.current = recognition;
    }

    if (hasSynthesis) {
      synthRef.current = window.speechSynthesis;
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
      if (synthRef.current) {
        synthRef.current.cancel();
      }
    };
  }, []);

  // Update recognition language when state changes
  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.lang = language;
    }
  }, [language]);

  const startListening = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.lang = language;
      recognitionRef.current.start();
    } catch {
      // If already running or starting
    }
  }, [language]);

  const stopListening = useCallback(() => {
    if (!recognitionRef.current) return;
    try {
      recognitionRef.current.stop();
    } catch {
      // ignore
    }
    setIsListening(false);
    options.onListeningStateChange?.(false);
  }, [options]);

  const toggleListening = useCallback(() => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }, [isListening, startListening, stopListening]);

  const stopSpeaking = useCallback(() => {
    if (synthRef.current) {
      synthRef.current.cancel();
    }
    setIsSpeaking(false);
    options.onSpeakingStateChange?.(false);
  }, [options]);

  const speak = useCallback(
    (rawText: string) => {
      if (!synthRef.current) return;

      // Stop any current utterance
      synthRef.current.cancel();

      // Clean markdown tags, code blocks, or raw ascii for natural reading
      const cleanText = rawText
        .replace(/```[\s\S]*?```/g, 'Code block omitted.')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/[#*_-]/g, ' ')
        .trim();

      if (!cleanText) return;

      // Truncate ultra-long responses to prevent endless monotone speech
      const speakableText = cleanText.length > 350 ? `${cleanText.slice(0, 350)}... and more.` : cleanText;

      const utterance = new SpeechSynthesisUtterance(speakableText);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;

      // Choose natural Indian English or Hindi voice if available
      const voices = synthRef.current.getVoices();
      const preferredVoice = voices.find(
        (v) =>
          (language === 'hi-IN' && (v.lang === 'hi-IN' || v.lang.startsWith('hi'))) ||
          (language === 'en-IN' && (v.lang === 'en-IN' || v.name.includes('India')))
      ) || voices.find((v) => v.lang.startsWith('en')) || null;

      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      utterance.onstart = () => {
        setIsSpeaking(true);
        options.onSpeakingStateChange?.(true);
      };

      utterance.onend = () => {
        setIsSpeaking(false);
        options.onSpeakingStateChange?.(false);
      };

      utterance.onerror = () => {
        setIsSpeaking(false);
        options.onSpeakingStateChange?.(false);
      };

      activeUtteranceRef.current = utterance;
      synthRef.current.speak(utterance);
    },
    [language, options]
  );

  return {
    isSupported,
    isListening,
    isSpeaking,
    language,
    setLanguage,
    startListening,
    stopListening,
    toggleListening,
    speak,
    stopSpeaking,
  };
}
