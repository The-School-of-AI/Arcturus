from voice.voice_wake_service import VoiceWakeService

def on_wake(event):
    print("🔥 WAKE EVENT:", event)

if __name__ == "__main__":
    service = VoiceWakeService(on_wake)
    service.start()

    input("Listening... Press Enter to stop\n")
    service.stop()
