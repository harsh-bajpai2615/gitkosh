"""Voice mock-interview support — native macOS TTS + speech-to-text.

TTS: macOS `say` (a reliable fallback; the web UI prefers the Web Speech API).
STT: record the mic with AVAudioRecorder, then transcribe on-device with the Speech
framework (SFSpeechRecognizer — free & private). If on-device recognition isn't
available/authorized and a Groq key is set, fall back to Groq's Whisper API.

All audio APIs are macOS-only and need the bundle's Info.plist usage strings
(NSMicrophoneUsageDescription, NSSpeechRecognitionUsageDescription). Every entry
point degrades gracefully so a failure surfaces a message instead of crashing the
JS bridge.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time

_recorder = None
_rec_path = None

# 'lpcm' fourcc — kAudioFormatLinearPCM (CoreAudio constant, stable).
_FMT_LINEAR_PCM = 1819304813


# ---------- text to speech ----------
def speak(text: str) -> dict:
    """Speak text via macOS `say` (non-blocking). Web UI normally uses Web Speech;
    this is the native fallback."""
    text = (text or "").strip()
    if not text:
        return {"ok": True}
    try:
        stop_speaking()
        subprocess.Popen(["/usr/bin/say", text[:2000]])
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def stop_speaking() -> dict:
    try:
        subprocess.run(["/usr/bin/killall", "say"], capture_output=True)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True}


# ---------- recording ----------
def start_recording() -> dict:
    """Begin recording the mic to a temp 16 kHz mono WAV (ideal for speech)."""
    global _recorder, _rec_path
    try:
        import AVFoundation
        import Foundation
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"audio frameworks unavailable: {e}"}
    try:
        if _recorder is not None:  # already recording — restart cleanly
            try:
                _recorder.stop()
            except Exception:  # noqa: BLE001
                pass
            _recorder = None
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        url = Foundation.NSURL.fileURLWithPath_(path)
        settings = {
            "AVFormatIDKey": _FMT_LINEAR_PCM,
            "AVSampleRateKey": 16000.0,
            "AVNumberOfChannelsKey": 1,
            "AVLinearPCMBitDepthKey": 16,
            "AVLinearPCMIsFloatKey": False,
            "AVLinearPCMIsBigEndianKey": False,
        }
        rec, err = AVFoundation.AVAudioRecorder.alloc().initWithURL_settings_error_(url, settings, None)
        if rec is None:
            return {"ok": False, "error": f"couldn't init recorder: {err}"}
        if not rec.record():
            return {"ok": False, "error": "microphone unavailable (check mic permission in System Settings → Privacy)"}
        _recorder, _rec_path = rec, path
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def stop_and_transcribe(groq_key: str = "") -> dict:
    """Stop recording and transcribe — on-device first, then Groq Whisper."""
    global _recorder, _rec_path
    if _recorder is None or not _rec_path:
        return {"ok": False, "error": "not recording"}
    try:
        _recorder.stop()
    except Exception:  # noqa: BLE001
        pass
    path, _recorder, _rec_path = _rec_path, None, None
    if not path or not os.path.exists(path) or os.path.getsize(path) < 1024:
        return {"ok": False, "error": "no audio captured — try again"}
    try:
        text, engine = None, ""
        try:
            text = _transcribe_ondevice(path)
            if text:
                engine = "on-device"
        except Exception as e:  # noqa: BLE001
            print(f"  ! on-device STT failed: {e}")
        if not text and groq_key:
            try:
                text = _transcribe_groq(path, groq_key)
                if text:
                    engine = "groq"
            except Exception as e:  # noqa: BLE001
                print(f"  ! groq STT failed: {e}")
        if not text:
            return {"ok": False, "error": "Couldn't transcribe. Turn on Dictation in "
                    "System Settings → Keyboard, or add a Groq API key for cloud transcription."}
        return {"ok": True, "text": text, "engine": engine}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------- transcription engines ----------
def _transcribe_ondevice(path: str, timeout: int = 45) -> str | None:
    """Transcribe on-device. The Speech framework (auth prompt + recognitionTask
    callbacks) must run on the main thread, but the JS bridge calls us on a worker
    thread — so we hop the work onto the main queue and block here on an Event until
    the main run loop (the live UI loop) delivers the result."""
    import Foundation
    import Speech

    box = {"text": None}
    done = threading.Event()

    def start_recognition():
        try:
            rec = Speech.SFSpeechRecognizer.alloc().initWithLocale_(
                Foundation.NSLocale.localeWithLocaleIdentifier_("en-US"))
            if rec is None or not rec.isAvailable():
                done.set()
                return
            url = Foundation.NSURL.fileURLWithPath_(path)
            req = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(url)
            try:
                if rec.supportsOnDeviceRecognition():
                    req.setRequiresOnDeviceRecognition_(True)
            except Exception:  # noqa: BLE001
                pass

            def handler(result, error):
                if error is not None:
                    done.set()
                    return
                if result is not None:
                    box["text"] = result.bestTranscription().formattedString()
                    if result.isFinal():
                        done.set()
            rec.recognitionTaskWithRequest_resultHandler_(req, handler)
        except Exception:  # noqa: BLE001
            done.set()

    def on_main():
        st = Speech.SFSpeechRecognizer.authorizationStatus()
        if st == 3:                      # authorized
            start_recognition()
        elif st in (1, 2):               # denied / restricted
            done.set()
        else:                            # not determined → prompt (on main), then proceed
            def authcb(status):
                start_recognition() if status == 3 else done.set()
            Speech.SFSpeechRecognizer.requestAuthorization_(authcb)

    Foundation.NSOperationQueue.mainQueue().addOperationWithBlock_(on_main)
    done.wait(timeout)
    return (box.get("text") or "").strip() or None


def _transcribe_groq(path: str, api_key: str) -> str | None:
    import requests
    with open(path, "rb") as f:
        r = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (os.path.basename(path), f, "audio/wav")},
            data={"model": "whisper-large-v3", "response_format": "json"},
            timeout=120)
    if r.status_code == 200:
        return (r.json().get("text") or "").strip() or None
    return None


def status() -> dict:
    """Report voice capabilities for the UI."""
    try:
        import Speech
        st = Speech.SFSpeechRecognizer.authorizationStatus()
        ondevice = st in (0, 3)  # not-yet-asked or authorized
    except Exception:  # noqa: BLE001
        ondevice = False
    return {"tts": True, "ondevice": ondevice}
