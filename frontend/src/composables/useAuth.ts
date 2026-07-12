import { ref } from 'vue'
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  GoogleAuthProvider,
  type User,
} from 'firebase/auth'
import axios from 'axios'
import { auth } from '../firebase'

const API_BASE = 'http://localhost:8000'

interface Profile {
  uid: string
  email?: string
  name?: string
  picture?: string
  role: 'admin' | 'teacher'
}

// State ระดับ module (shared) — ทุก component ที่เรียก useAuth() จะเห็นค่าเดียวกัน
const user = ref<User | null>(null)
const profile = ref<Profile | null>(null)
const loading = ref(true)
const errorMessage = ref('')

// จำกัดอายุ session ไว้ 8 ชั่วโมง — Firebase Auth ปกติจะต่ออายุ token ให้เองไม่มีวันหมด
// จึงต้องจับเวลาเองฝั่ง frontend แล้วบังคับออกจากระบบเมื่อครบกำหนด
const SESSION_DURATION_MS = 8 * 60 * 60 * 1000
const LOGIN_TIME_KEY = 'teachtabel_login_time'
let sessionCheckInterval: ReturnType<typeof setInterval> | null = null

function isSessionExpired(): boolean {
  const loginTime = localStorage.getItem(LOGIN_TIME_KEY)
  if (!loginTime) return false
  return Date.now() - Number(loginTime) > SESSION_DURATION_MS
}

onAuthStateChanged(auth, async (u) => {
  if (u && isSessionExpired()) {
    // เข้าสู่ระบบมาเกิน 8 ชั่วโมงแล้ว บังคับออกจากระบบ
    localStorage.removeItem(LOGIN_TIME_KEY)
    await signOut(auth)
    return
  }

  user.value = u
  if (u) {
    if (!localStorage.getItem(LOGIN_TIME_KEY)) {
      localStorage.setItem(LOGIN_TIME_KEY, Date.now().toString())
    }
    try {
      const token = await u.getIdToken()
      const res = await axios.get(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      profile.value = res.data
    } catch (e) {
      console.error('โหลดโปรไฟล์ผู้ใช้ไม่สำเร็จ', e)
    }

    // ตั้งตัวจับเวลาเช็คทุก 1 นาที เผื่อเปิดแท็บทิ้งไว้นานเกิน 8 ชม. โดยไม่ได้ปิด/เปิดใหม่
    if (!sessionCheckInterval) {
      sessionCheckInterval = setInterval(() => {
        if (isSessionExpired()) logout()
      }, 60 * 1000)
    }
  } else {
    profile.value = null
    localStorage.removeItem(LOGIN_TIME_KEY)
    if (sessionCheckInterval) {
      clearInterval(sessionCheckInterval)
      sessionCheckInterval = null
    }
  }
  loading.value = false
})

const provider = new GoogleAuthProvider()

async function signInWithGoogle() {
  errorMessage.value = ''
  try {
    await signInWithPopup(auth, provider)
  } catch (e: any) {
    errorMessage.value = e?.message || 'เข้าสู่ระบบไม่สำเร็จ กรุณาลองใหม่อีกครั้ง'
  }
}

async function logout() {
  await signOut(auth)
}

export function useAuth() {
  return { user, profile, loading, errorMessage, signInWithGoogle, logout }
}
