import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import axios from 'axios'
import { auth } from './firebase'
import { useAcademicYear } from './composables/useAcademicYear'
import { usePlan } from './composables/usePlan'

// แนบ Firebase ID token ให้ทุก request ที่ยิงผ่าน axios โดยอัตโนมัติ
// เพื่อให้ backend (FastAPI) ตรวจสอบสิทธิ์การแก้ไขข้อมูลได้ (ดู get_current_user ใน backend/main.py)
axios.interceptors.request.use(async (config) => {
  const currentUser = auth.currentUser
  if (currentUser) {
    const token = await currentUser.getIdToken()
    config.headers = config.headers ?? {}
    ;(config.headers as any).Authorization = `Bearer ${token}`
  }

  // แนบ year_key (ปีการศึกษา+เทอมที่กำลังใช้งานอยู่) ไปกับทุก request โดยอัตโนมัติ
  // เพื่อให้ backend กรอง/บันทึกข้อมูลแยกตามปี/เทอมได้ (ดู main.py — endpoint ที่ไม่มีพารามิเตอร์นี้จะเพิกเฉยไปเอง)
  const { currentYearKey } = useAcademicYear()
  if (currentYearKey.value) {
    if (config.data instanceof FormData) {
      // multipart/form-data (เช่น /import/*) แนบผ่าน form field แทน query param
      if (!config.data.has('year_key')) {
        config.data.append('year_key', currentYearKey.value)
      }
    } else {
      config.params = { year_key: currentYearKey.value, ...(config.params || {}) }
    }
  }

  // แนบ plan_id (แผนภาระงานสอน/ตารางสอนที่กำลังใช้งานอยู่) ไปกับทุก request โดยอัตโนมัติเช่นกัน
  // จุดเลือกแผนอยู่แค่ในหน้า "จัดภาระงานสอน" แต่ค่านี้มีผลกับทุกหน้าที่เกี่ยวข้องกับภาระงาน/ตารางสอน
  const { currentPlanId } = usePlan()
  if (currentPlanId.value) {
    if (config.data instanceof FormData) {
      if (!config.data.has('plan_id')) {
        config.data.append('plan_id', currentPlanId.value)
      }
    } else {
      config.params = { plan_id: currentPlanId.value, ...(config.params || {}) }
    }
  }

  return config
})

createApp(App).mount('#app')
