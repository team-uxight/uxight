import { useState } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8080'

type Health = { status: string; service: string }
type RunCreated = { id: number; status: string }

export default function App() {
  const [health, setHealth] = useState<string>('—')
  const [run, setRun] = useState<string>('—')

  async function checkHealth() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/health`)
      const body = (await res.json()) as Health
      setHealth(`${body.service}: ${body.status}`)
    } catch (e) {
      setHealth(`error: ${(e as Error).message}`)
    }
  }

  async function createRun() {
    try {
      const res = await fetch(`${API_BASE_URL}/api/runs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ targetUrl: 'https://www.gachon.ac.kr', task: '장학금 신청 방법 찾기' }),
      })
      const body = (await res.json()) as RunCreated
      setRun(`run #${body.id} → ${body.status}`)
    } catch (e) {
      setRun(`error: ${(e as Error).message}`)
    }
  }

  return (
    <main>
      <h1>UXight</h1>
      <p>walking skeleton — web → api → agent → mysql → web</p>
      <section>
        <button onClick={checkHealth}>GET /api/health</button> <code>{health}</code>
      </section>
      <section>
        <button onClick={createRun}>POST /api/runs</button> <code>{run}</code>
      </section>
    </main>
  )
}
