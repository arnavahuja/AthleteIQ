"""
Speech transcription is now handled client-side using the browser's
Web Speech API (SpeechRecognition). This module is kept as a placeholder
for any server-side audio processing if needed in the future.
"""


class TranscriptionError(Exception):
    pass


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """
    Server-side transcription placeholder.
    In the current architecture, transcription is done client-side via
    the browser's Web Speech API. This endpoint is kept for compatibility
    but should not be the primary transcription path.
    """
    raise TranscriptionError(
        "Server-side transcription is not available. "
        "Please use the browser's voice recognition feature instead."
    )
