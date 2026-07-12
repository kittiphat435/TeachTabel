import { ref, computed } from 'vue'

// สถานะ "ปีการศึกษา/เทอม" ที่กำลังใช้งานอยู่ทั้งแอป (global reactive state)
// ทุก component ที่ import useAcademicYear() จะได้ตัวแปรตัวเดียวกัน (singleton)
// เก็บค่าไว้ใน localStorage เพื่อจำค่าล่าสุดไว้ข้าม session

export interface AcademicYear {
  id: string
  year: string
  term: number
  year_key: string
  label: string
}

const STORAGE_KEY = 'teachtabel_year_key'

const currentYearKey = ref<string>(localStorage.getItem(STORAGE_KEY) || '')
const academicYears = ref<AcademicYear[]>([])
const loaded = ref(false)

const currentYearLabel = computed(() => {
  const found = academicYears.value.find(y => y.year_key === currentYearKey.value)
  return found?.label || 'ยังไม่ได้เลือกปีการศึกษา'
})

function setCurrentYearKey(yearKey: string) {
  currentYearKey.value = yearKey
  localStorage.setItem(STORAGE_KEY, yearKey)
}

function setAcademicYears(years: AcademicYear[]) {
  academicYears.value = years
  loaded.value = true
  // ถ้ายังไม่เคยเลือก หรือค่าที่เลือกไว้ไม่มีอยู่จริงแล้ว ให้ auto-select ตัวล่าสุด (เรียงมาจาก backend อยู่แล้ว)
  if (years.length > 0 && !years.some(y => y.year_key === currentYearKey.value)) {
    setCurrentYearKey(years[0].year_key)
  }
}

export function useAcademicYear() {
  return {
    currentYearKey,
    currentYearLabel,
    academicYears,
    loaded,
    setCurrentYearKey,
    setAcademicYears,
  }
}
