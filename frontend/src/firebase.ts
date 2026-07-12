import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'

// ค่าเหล่านี้มาจาก Firebase Console > Project settings > General > Your apps > Web app (SDK config)
// ต้องเปิดใช้งาน Sign-in method > Google ใน Firebase Authentication ก่อนใช้งานจริง
// ใส่ค่าจริงไว้ในไฟล์ .env (ดูตัวอย่างที่ .env.example) — ห้าม commit ไฟล์ .env ขึ้น git
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const firebaseApp = initializeApp(firebaseConfig)
export const auth = getAuth(firebaseApp)
