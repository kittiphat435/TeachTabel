import { ref, computed } from 'vue'

// สถานะ "แผนภาระงานสอน" ที่กำลังใช้งานอยู่ทั้งแอป (global reactive state) — เหมือน useAcademicYear.ts
// ใช้แยกภาระงานสอน (assignments) และตารางสอนที่จัดไว้แล้ว (schedule_entries) ออกจากกันหลายเวอร์ชันภายในปี/เทอมเดียวกัน
// เช่น กรณีครูเกษียณ/ลาออก จำนวนครูในกลุ่มสาระเปลี่ยน ก็สร้างแผนใหม่มาลองจัดสรรใหม่ได้โดยไม่ทับแผนเดิม
// จุดเลือก/จัดการแผนอยู่แค่ในหน้า "จัดภาระงานสอน" เท่านั้น แต่ค่าที่เลือกไว้จะมีผลกับทั้งแอป (ตารางสอน, Dashboard ฯลฯ)

export interface Plan {
  id: string
  label: string
  year_key: string
  created_at?: string
}

const STORAGE_KEY = 'teachtabel_plan_id'

const currentPlanId = ref<string>(localStorage.getItem(STORAGE_KEY) || '')
const plans = ref<Plan[]>([])
const loaded = ref(false)

const currentPlanLabel = computed(() => {
  const found = plans.value.find(p => p.id === currentPlanId.value)
  return found?.label || 'ยังไม่ได้เลือกแผน'
})

function setCurrentPlanId(planId: string) {
  currentPlanId.value = planId
  localStorage.setItem(STORAGE_KEY, planId)
}

function setPlans(newPlans: Plan[]) {
  plans.value = newPlans
  loaded.value = true
  // ถ้ายังไม่เคยเลือก หรือค่าที่เลือกไว้ไม่มีอยู่จริงแล้ว (เช่น สลับปีการศึกษา) ให้ auto-select แผนแรก
  if (newPlans.length > 0 && !newPlans.some(p => p.id === currentPlanId.value)) {
    setCurrentPlanId(newPlans[0].id)
  }
}

export function usePlan() {
  return {
    currentPlanId,
    currentPlanLabel,
    plans,
    loaded,
    setCurrentPlanId,
    setPlans,
  }
}
