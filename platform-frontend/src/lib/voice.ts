export async function startVoice() {
    const res = await fetch("http://localhost:8000/api/voice/start", {
        method: "POST"
    })
    return res.json()
}

export async function stopVoice() {
    const res = await fetch("http://localhost:8000/api/voice/stop", {
        method: "POST"
    })
    return res.json()
}

export async function getVoiceSession() {
    const res = await fetch("http://localhost:8000/api/voice/session")
    return res.json()
}