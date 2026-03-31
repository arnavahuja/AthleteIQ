import { useState, useRef } from "react";

export default function VoiceRecorder({ onTranscription, disabled }) {
  const [status, setStatus] = useState("idle"); // idle | listening | processing
  const recognitionRef = useRef(null);

  const startListening = () => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. Try Chrome.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      setStatus("idle");
      onTranscription(transcript);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      setStatus("idle");
      if (event.error === "not-allowed") {
        alert("Microphone access is required for voice input.");
      }
    };

    recognition.onend = () => {
      setStatus("idle");
    };

    recognitionRef.current = recognition;
    recognition.start();
    setStatus("listening");
  };

  const stopListening = () => {
    if (recognitionRef.current && status === "listening") {
      recognitionRef.current.stop();
    }
  };

  return (
    <button
      className={`voice-btn ${status}`}
      onClick={status === "listening" ? stopListening : startListening}
      disabled={disabled}
      title={
        status === "listening"
          ? "Click to stop listening"
          : "Click to start voice input"
      }
    >
      {status === "listening" ? (
        <span className="recording-indicator">&#9724; Stop</span>
      ) : (
        <span>&#127908; Speak</span>
      )}
    </button>
  );
}
