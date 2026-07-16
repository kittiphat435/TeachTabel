<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import axios from 'axios'
import { CalendarDays, Loader2, Trash2, AlertTriangle, CheckCircle2, Users, MapPin, BookOpen, Info, Search, Pencil, X, Home, FileDown } from 'lucide-vue-next'
import SearchableSelect from './SearchableSelect.vue'

const API_BASE = 'http://localhost:8000'

interface Classroom { id: string; grade_level: string; room_name: string }
interface Teacher { id: string; full_name: string; department: string; teacher_code?: string | null }
interface Subject { id: string; subject_code: string; subject_name: string }
interface Room { id: string; room_name: string }
interface ScheduleEntry {
  id: string
  day_of_week: number
  period_number: number
  subject_id: string
  subject_name: string
  teacher_ids: string[]
  teacher_names: string[]
  classroom_ids: string[]
  classroom_names: string[]
  room_id?: string | null
  room_name: string | null
  note?: string
  created_by_name?: string
}

const classrooms = ref<Classroom[]>([])
const teachers = ref<Teacher[]>([])
const subjects = ref<Subject[]>([])
const rooms = ref<Room[]>([])
const entries = ref<ScheduleEntry[]>([])

const loading = ref(true)
const loadingSchedule = ref(false)
const saving = ref(false)
const conflictErrors = ref<string[]>([])
const successMessage = ref('')

const days = [
  { val: 1, name: 'จันทร์' },
  { val: 2, name: 'อังคาร' },
  { val: 3, name: 'พุธ' },
  { val: 4, name: 'พฤหัสบดี' },
  { val: 5, name: 'ศุกร์' },
]
const periods = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

// Form state
const selectedClassroomId = ref('')
const selectedDay = ref(1)
const selectedPeriod = ref(1)
const selectedSubjectId = ref('')
const selectedTeacherIds = ref<string[]>([])
const selectedRoomId = ref('')
const note = ref('')

// โหมด "ชุมนุม/ลูกเสือ (อิสระ)" — ใช้กับทั้งชุมนุมและลูกเสือ/เนตรนารี/ยุวกาชาด เพราะมีหลักการลงตารางเดียวกัน
// คือฝั่งห้องเรียนกับฝั่งครูเป็นอิสระต่อกัน ไม่ต้องผูกครูกับห้องเรียนพร้อมกัน
const clubMode = ref(false)
const clubSubjectId = ref('')
const clubTeacherIds = ref<string[]>([])
const clubSavingClassroom = ref(false)
const clubSavingTeacher = ref(false)
const clubTeacherEntries = ref<ScheduleEntry[]>([])

const selectedClassroomLabel = computed(() => {
  const c = classrooms.value.find(c => c.id === selectedClassroomId.value)
  return c ? `${c.grade_level}/${c.room_name}` : ''
})

// ตัวเลือกสำหรับ SearchableSelect (ห้องเรียน/วิชา) — พิมพ์ค้นหาได้ เช่น "1/1" หรือชื่อวิชา
const classroomOptions = computed(() =>
  classrooms.value.map(c => ({ value: c.id, label: `${c.grade_level}/${c.room_name}` }))
)
const subjectOptions = computed(() =>
  subjects.value.map(s => ({ value: s.id, label: `${s.subject_code} - ${s.subject_name}` }))
)

// --- มุมมองภาพรวมตาราง: ห้องเรียน (นักเรียน, แก้ไขได้) / ครู (ค้นหา, ดูอย่างเดียว) / ห้อง-สถานที่ (ค้นหา, ดูอย่างเดียว) ---
const overviewMode = ref<'classroom' | 'teacher' | 'room'>('classroom')
const overviewTeacherId = ref('')
const overviewRoomId = ref('')
const teacherOverviewEntries = ref<ScheduleEntry[]>([])
const roomOverviewEntries = ref<ScheduleEntry[]>([])
const loadingOverview = ref(false)

const teacherOptions = computed(() =>
  teachers.value.map(t => ({ value: t.id, label: t.teacher_code ? `[${t.teacher_code}] ${t.full_name}` : t.full_name }))
)
const roomOptions = computed(() =>
  rooms.value.map(r => ({ value: r.id, label: r.room_name }))
)

const fetchTeacherOverview = async () => {
  if (!overviewTeacherId.value) { teacherOverviewEntries.value = []; return }
  loadingOverview.value = true
  try {
    const res = await axios.get(`${API_BASE}/schedule/`, { params: { teacher_id: overviewTeacherId.value } })
    teacherOverviewEntries.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loadingOverview.value = false
  }
}
const fetchRoomOverview = async () => {
  if (!overviewRoomId.value) { roomOverviewEntries.value = []; return }
  loadingOverview.value = true
  try {
    const res = await axios.get(`${API_BASE}/schedule/`, { params: { room_id: overviewRoomId.value } })
    roomOverviewEntries.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loadingOverview.value = false
  }
}
watch(overviewTeacherId, fetchTeacherOverview)
watch(overviewRoomId, fetchRoomOverview)

// เรียกหลังบันทึก/ลบ/แก้ไขทุกครั้ง เพื่อให้ตารางทั้ง 3 มุมมอง (ห้องเรียน/ครู/ห้อง-สถานที่) เห็นข้อมูลล่าสุดตรงกัน
// แม้ผู้ใช้จะไม่ได้อยู่หน้ามุมมองนั้นตอนบันทึกก็ตาม (กันข้อมูลค้างเมื่อสลับแท็บกลับมาดู)
const refreshAllViews = async () => {
  await fetchSchedule()
  if (overviewTeacherId.value) await fetchTeacherOverview()
  if (overviewRoomId.value) await fetchRoomOverview()
}

// --- ดาวน์โหลด PDF ตารางสอน (รวมทุกคน/ทุกห้องเป็นไฟล์เดียว) ---
// ใช้ axios (ไม่ใช่ลิงก์ตรง) เพื่อให้ interceptor แนบ year_key/plan_id ของปี/แผนที่กำลังเลือกอยู่ให้อัตโนมัติ
const downloadingPdf = ref<'teachers' | 'classrooms' | 'rooms' | null>(null)
const downloadPdf = async (kind: 'teachers' | 'classrooms' | 'rooms', filename: string) => {
  downloadingPdf.value = kind
  try {
    const res = await axios.get(`${API_BASE}/export/pdf/${kind}`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    alert('ดาวน์โหลด PDF ไม่สำเร็จ')
  } finally {
    downloadingPdf.value = null
  }
}

// ตารางที่ใช้แสดงในกริดขวา สลับตามมุมมองที่เลือก
const activeEntries = computed(() => {
  if (overviewMode.value === 'teacher') return teacherOverviewEntries.value
  if (overviewMode.value === 'room') return roomOverviewEntries.value
  return entries.value
})
const activeEntryAt = (day: number, period: number) =>
  activeEntries.value.find(e => e.day_of_week === day && e.period_number === period)

// บรรทัดรองในแต่ละช่องของตาราง ปรับเนื้อหาตามมุมมอง
const cellSubtitle = (entry: ScheduleEntry) => {
  if (overviewMode.value === 'teacher') {
    // มุมมองครู: อยู่ในตารางของครูอยู่แล้ว จึงโชว์ว่าไปสอนชั้นไหน + ห้อง/สถานที่ไหน
    return [entry.classroom_names.length ? entry.classroom_names.join(', ') : 'ชุมนุม/ลูกเสือ (อิสระ)', entry.room_name]
      .filter(Boolean).join(' • ')
  }
  if (overviewMode.value === 'room') {
    // มุมมองห้อง: อยู่ในตารางของห้องนั้นอยู่แล้ว จึงโชว์ว่าใครใช้อยู่ — ชั้นไหน + ครูคนไหนบ้าง (ครบทุกคนถ้าสอนร่วม)
    return [entry.classroom_names.join(', '), entry.teacher_names.join(', ')].filter(Boolean).join(' • ')
  }
  // มุมมองห้องเรียน/นักเรียน: โชว์ครูผู้สอน (ครบทุกคนถ้าสอนร่วม) + ห้อง/สถานที่ที่ไปเรียน
  return [entry.teacher_names.join(', '), entry.room_name].filter(Boolean).join(' • ')
}

// ช่องค้นหาชื่อครู สำหรับ checkbox list (โหมดวิชาปกติ และโหมดชุมนุม/ลูกเสือ)
const teacherSearch = ref('')
const filteredTeachers = computed(() => {
  if (!teacherSearch.value) return teachers.value
  const q = teacherSearch.value
  return teachers.value.filter(t => t.full_name.includes(q) || (t.teacher_code || '').includes(q))
})
const clubTeacherSearch = ref('')
const filteredClubTeachers = computed(() => {
  if (!clubTeacherSearch.value) return teachers.value
  const q = clubTeacherSearch.value
  return teachers.value.filter(t => t.full_name.includes(q) || (t.teacher_code || '').includes(q))
})

const fetchMasterData = async () => {
  loading.value = true
  try {
    const [cRes, tRes, sRes, rRes] = await Promise.all([
      axios.get(`${API_BASE}/classrooms/`),
      axios.get(`${API_BASE}/teachers/`),
      axios.get(`${API_BASE}/subjects/`),
      axios.get(`${API_BASE}/rooms/`),
    ])
    classrooms.value = cRes.data
    teachers.value = tRes.data
    subjects.value = sRes.data
    rooms.value = rRes.data
    if (classrooms.value.length > 0 && !selectedClassroomId.value) {
      selectedClassroomId.value = classrooms.value[0].id
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchSchedule = async () => {
  if (!selectedClassroomId.value) { entries.value = []; return }
  loadingSchedule.value = true
  try {
    const res = await axios.get(`${API_BASE}/schedule/`, { params: { classroom_id: selectedClassroomId.value } })
    entries.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loadingSchedule.value = false
  }
}

const fetchClubTeacherEntries = async () => {
  try {
    const res = await axios.get(`${API_BASE}/schedule/`)
    clubTeacherEntries.value = (res.data as ScheduleEntry[]).filter(
      (e) => e.day_of_week === selectedDay.value && e.period_number === selectedPeriod.value &&
        e.classroom_ids.length === 0 && e.teacher_ids.length > 0
    )
  } catch (e) {
    console.error(e)
  }
}

onMounted(async () => {
  await fetchMasterData()
  await fetchSchedule()
  // เดาวิชา "ชุมนุม" ให้อัตโนมัติถ้ามีอยู่แล้ว ไม่บังคับ เปลี่ยนได้
  const guess = subjects.value.find(s => s.subject_name.includes('ชุมนุม'))
  if (guess) clubSubjectId.value = guess.id
})

watch(selectedClassroomId, fetchSchedule)
watch([selectedDay, selectedPeriod, clubMode], () => {
  if (clubMode.value) fetchClubTeacherEntries()
})

// คาบที่เลือกอยู่ตอนนี้ มีวิชาอยู่แล้วหรือยัง
const currentEntry = computed(() =>
  entries.value.find(e => e.day_of_week === selectedDay.value && e.period_number === selectedPeriod.value)
)

// id ของคาบที่กำลังแก้ไขอยู่ (null = โหมดเพิ่มใหม่). ไม่ลบข้อมูลเดิมจนกว่าจะกดบันทึกจริง เพื่อไม่ให้เสียข้อมูลถ้ากดยกเลิก
const editingEntryId = ref<string | null>(null)
// true เมื่อกด "สอนร่วมกับครูท่านอื่น" จากการ์ดคาบที่ชนกัน — ใช้ไฮไลต์รายชื่อครูให้เห็นชัดว่าต้องติ๊กเพิ่มตรงไหน
const coTeachHint = ref(false)

const resetForm = () => {
  selectedSubjectId.value = ''
  selectedTeacherIds.value = []
  selectedRoomId.value = ''
  note.value = ''
  editingEntryId.value = null
  coTeachHint.value = false
}

const pickSlot = (day: number, period: number) => {
  selectedDay.value = day
  selectedPeriod.value = period
  conflictErrors.value = []
  successMessage.value = ''
  // ถ้ากำลังแก้ไขคาบหนึ่งอยู่ (editingEntryId ตั้งไว้แล้ว) การคลิกช่องใหม่ = "ย้ายตำแหน่ง" ไปคาบนั้น
  // ฟอร์ม (วิชา/ครู/ห้อง) จะยังคงข้อมูลเดิมไว้ รอกดปุ่ม "บันทึกการแก้ไข" เพื่อยืนยันการย้าย
  if (!editingEntryId.value) {
    resetForm()
    clubTeacherIds.value = []
  }
}

const saveEntry = async () => {
  if (!selectedClassroomId.value || !selectedSubjectId.value || selectedTeacherIds.value.length === 0) {
    alert('กรุณาเลือกวิชาและครูผู้สอนอย่างน้อย 1 ท่าน')
    return
  }
  conflictErrors.value = []
  successMessage.value = ''
  saving.value = true
  const wasEditing = !!editingEntryId.value
  const payload = {
    day_of_week: selectedDay.value,
    period_number: selectedPeriod.value,
    subject_id: selectedSubjectId.value,
    teacher_ids: selectedTeacherIds.value,
    classroom_ids: [selectedClassroomId.value],
    room_id: selectedRoomId.value || null,
    note: note.value || null,
  }
  try {
    // แก้ไข/ย้าย = เขียนทับคาบเดิมแบบอะตอมมิก (PUT) ไม่ลบก่อนสร้างใหม่ — กันข้อมูลหายถ้าคาบที่จะย้ายไปชนกับคาบอื่น
    // (คาบเดิมจะไม่ถูกแตะต้องเลยถ้าพบว่าชนกัน เพราะ backend เช็คก่อนเขียนทับเสมอ)
    if (wasEditing) {
      await axios.put(`${API_BASE}/schedule/${editingEntryId.value}`, payload)
    } else {
      await axios.post(`${API_BASE}/schedule/`, payload)
    }
    successMessage.value = wasEditing ? 'แก้ไข/ย้ายตารางสอนคาบนี้สำเร็จ' : 'บันทึกตารางสอนคาบนี้สำเร็จ'
    resetForm()
    await refreshAllViews()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail && typeof detail === 'object' && detail.conflicts) {
      conflictErrors.value = detail.conflicts
    } else if (e?.response?.status === 401) {
      conflictErrors.value = ['กรุณาเข้าสู่ระบบก่อนบันทึกข้อมูล']
    } else {
      conflictErrors.value = ['เกิดข้อผิดพลาดในการบันทึก กรุณาลองใหม่อีกครั้ง']
    }
  } finally {
    saving.value = false
  }
}

const deleteEntry = async (id: string) => {
  if (!confirm('ยืนยันการลบตารางสอนคาบนี้?')) return
  try {
    await axios.delete(`${API_BASE}/schedule/${id}`)
    if (editingEntryId.value === id) resetForm()
    await refreshAllViews()
  } catch (e) {
    alert('ลบไม่สำเร็จ')
  }
}

// แก้ไขคาบที่ลงไว้แล้ว: เติมฟอร์มด้วยค่าเดิม (วิชา/ครู/สถานที่/หมายเหตุ) โดยยังไม่ลบข้อมูลจริงจนกว่าจะกดบันทึก
const startEditEntry = (entry: ScheduleEntry) => {
  editingEntryId.value = entry.id
  selectedSubjectId.value = entry.subject_id
  selectedTeacherIds.value = [...entry.teacher_ids]
  selectedRoomId.value = entry.room_id || ''
  note.value = entry.note || ''
  coTeachHint.value = false
}

// เหมือน "แก้ไข" ทุกอย่าง แต่เปิดคำแนะนำให้ไปติ๊กเพิ่มชื่อครูท่านอื่นในรายชื่อด้านล่างแล้วกดบันทึก (สอนร่วมกัน)
const startCoTeach = (entry: ScheduleEntry) => {
  startEditEntry(entry)
  coTeachHint.value = true
}

const cancelEditEntry = () => {
  resetForm()
}

// ฝั่งห้องเรียน: บันทึกว่าห้องนี้ วัน/คาบนี้ เป็นชุมนุม (ไม่ผูกครู)
const saveClubClassroom = async () => {
  if (!selectedClassroomId.value || !clubSubjectId.value) {
    alert('กรุณาเลือกวิชาชุมนุมก่อน')
    return
  }
  conflictErrors.value = []
  successMessage.value = ''
  clubSavingClassroom.value = true
  try {
    await axios.post(`${API_BASE}/schedule/`, {
      day_of_week: selectedDay.value,
      period_number: selectedPeriod.value,
      subject_id: clubSubjectId.value,
      teacher_ids: [],
      classroom_ids: [selectedClassroomId.value],
      note: 'ชุมนุม/ลูกเสือ (อิสระ) — นักเรียนเดินไปหาครูเอง',
    })
    successMessage.value = 'บันทึกฝั่งห้องเรียนสำเร็จ'
    await refreshAllViews()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    conflictErrors.value = detail && typeof detail === 'object' && detail.conflicts
      ? detail.conflicts
      : ['เกิดข้อผิดพลาดในการบันทึก กรุณาลองใหม่อีกครั้ง']
  } finally {
    clubSavingClassroom.value = false
  }
}

// ฝั่งครู: บันทึกว่าครูที่เลือก วัน/คาบนี้ ไปสอนชุมนุม (ไม่ผูกห้องเรียน)
const saveClubTeachers = async () => {
  if (clubTeacherIds.value.length === 0 || !clubSubjectId.value) {
    alert('กรุณาเลือกวิชาชุมนุมและครูอย่างน้อย 1 ท่าน')
    return
  }
  conflictErrors.value = []
  successMessage.value = ''
  clubSavingTeacher.value = true
  try {
    await axios.post(`${API_BASE}/schedule/`, {
      day_of_week: selectedDay.value,
      period_number: selectedPeriod.value,
      subject_id: clubSubjectId.value,
      teacher_ids: clubTeacherIds.value,
      classroom_ids: [],
      note: 'ชุมนุม/ลูกเสือ (อิสระ) — ครูเดินไปหานักเรียนเอง',
    })
    successMessage.value = 'บันทึกฝั่งครูสำเร็จ'
    clubTeacherIds.value = []
    await fetchClubTeacherEntries()
    await refreshAllViews()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    conflictErrors.value = detail && typeof detail === 'object' && detail.conflicts
      ? detail.conflicts
      : ['เกิดข้อผิดพลาดในการบันทึก กรุณาลองใหม่อีกครั้ง']
  } finally {
    clubSavingTeacher.value = false
  }
}

const deleteClubTeacherEntry = async (id: string) => {
  if (!confirm('ยืนยันการลบ?')) return
  try {
    await axios.delete(`${API_BASE}/schedule/${id}`)
    await fetchClubTeacherEntries()
    await refreshAllViews()
  } catch (e) {
    alert('ลบไม่สำเร็จ')
  }
}

// ============================================================
// โหมด "เริ่มจากครู": 1) เลือกครู 2) ชั้นเรียนที่จะสอน 3) ห้อง 4) วิชา
// 5) คลิกวัน/คาบในตาราง (ฝั่งขวา = ตารางของครูคนนี้เอง) แล้วบันทึกทันที
// ============================================================
const teClassroomIds = ref<string[]>([])
const teClassroomSearch = ref('')
const teSubjectId = ref('')
const teRoomId = ref('')
const teNote = ref('')
const teCoTeach = ref(false)
const teEditingEntryId = ref<string | null>(null)
const teSelectedDay = ref<number | null>(null)
const teSelectedPeriod = ref<number | null>(null)
const teSaving = ref(false)

const filteredClassroomsForTe = computed(() => {
  if (!teClassroomSearch.value) return classrooms.value
  const q = teClassroomSearch.value
  return classrooms.value.filter(c => `${c.grade_level}/${c.room_name}`.includes(q))
})

const teResetForm = () => {
  teClassroomIds.value = []
  teSubjectId.value = ''
  teRoomId.value = ''
  teNote.value = ''
  teCoTeach.value = false
  teEditingEntryId.value = null
  teSelectedDay.value = null
  teSelectedPeriod.value = null
}

// เปลี่ยนตัวครูที่เลือก = เริ่มฟอร์มใหม่ (กันข้อมูลชั้นเรียน/วิชาของครูคนก่อนติดค้างมาผสมกับครูคนใหม่)
watch(overviewTeacherId, () => { teResetForm() })

// คาบของ "ครูคนนี้เอง" ที่ช่องนั้น (ใช้เช็คว่าครูสอนซ้อนตัวเองไหม และเปิดโหมดแก้ไข/ย้าย/ลบ)
const teEntryAt = (day: number, period: number) =>
  teacherOverviewEntries.value.find(e => e.day_of_week === day && e.period_number === period)

const teCurrentEntry = computed(() => {
  if (teSelectedDay.value == null || teSelectedPeriod.value == null) return null
  return teEntryAt(teSelectedDay.value, teSelectedPeriod.value) || null
})

const teStartEdit = (entry: ScheduleEntry) => {
  teEditingEntryId.value = entry.id
  teClassroomIds.value = [...entry.classroom_ids]
  teSubjectId.value = entry.subject_id
  teRoomId.value = entry.room_id || ''
  teNote.value = entry.note || ''
  teCoTeach.value = entry.teacher_ids.length > 1
}

const teCancelEdit = () => {
  const day = teSelectedDay.value, period = teSelectedPeriod.value
  teResetForm()
  teSelectedDay.value = day
  teSelectedPeriod.value = period
}

const teDeleteEntry = async (id: string) => {
  if (!confirm('ยืนยันการลบตารางสอนคาบนี้?')) return
  try {
    await axios.delete(`${API_BASE}/schedule/${id}`)
    if (teEditingEntryId.value === id) teResetForm()
    await refreshAllViews()
  } catch (e) {
    alert('ลบไม่สำเร็จ')
  }
}

// บันทึก/แก้ไข/ย้าย คาบของครูคนที่เลือกไว้ — ถ้าติ๊ก "สอนร่วม" และชั้นเรียนที่เลือก (1 ห้อง) มีครูท่านอื่นสอนคาบนี้อยู่แล้ว
// จะรวมเข้าเป็นคาบสอนร่วมกัน (ใช้วิชา/ห้อง/ชั้นเรียนของคาบเดิม เพิ่มแค่ครูคนนี้เข้าไป) แทนการลงซ้ำจนชนกัน
const teSaveEntry = async () => {
  if (!overviewTeacherId.value || teSelectedDay.value == null || teSelectedPeriod.value == null) return
  if (teClassroomIds.value.length === 0 || !teSubjectId.value) {
    alert('กรุณาเลือกชั้นเรียนและวิชาก่อน แล้วค่อยคลิกวัน/คาบในตาราง')
    return
  }
  conflictErrors.value = []
  successMessage.value = ''
  teSaving.value = true
  const wasEditing = !!teEditingEntryId.value
  let teacherIdsToSave = [overviewTeacherId.value]
  let clashing: ScheduleEntry | undefined

  try {
    if (teCoTeach.value && !wasEditing && teClassroomIds.value.length === 1) {
      const res = await axios.get(`${API_BASE}/schedule/`, { params: { classroom_id: teClassroomIds.value[0] } })
      clashing = (res.data as ScheduleEntry[]).find(
        e => e.day_of_week === teSelectedDay.value && e.period_number === teSelectedPeriod.value
      )
      if (clashing) {
        teacherIdsToSave = Array.from(new Set([...clashing.teacher_ids, overviewTeacherId.value]))
      }
    }
    const payload = {
      day_of_week: teSelectedDay.value,
      period_number: teSelectedPeriod.value,
      subject_id: clashing ? clashing.subject_id : teSubjectId.value,
      teacher_ids: teacherIdsToSave,
      classroom_ids: clashing ? clashing.classroom_ids : teClassroomIds.value,
      room_id: clashing ? (clashing.room_id || null) : (teRoomId.value || null),
      note: teNote.value || (clashing ? clashing.note : null) || null,
    }
    // แก้ไข/ย้ายคาบของตัวเอง หรือเข้าร่วมสอนคาบที่มีอยู่แล้ว (สอนร่วม) = เขียนทับแบบอะตอมมิก (PUT) ไม่ลบก่อนสร้างใหม่
    // กันข้อมูลหายถ้าคาบที่จะย้าย/รวมไปชนกับคาบอื่นที่ไม่คาดคิด — เฉพาะคาบใหม่ล้วนๆ เท่านั้นที่ POST สร้างใหม่
    if (clashing) {
      await axios.put(`${API_BASE}/schedule/${clashing.id}`, payload)
    } else if (wasEditing) {
      await axios.put(`${API_BASE}/schedule/${teEditingEntryId.value}`, payload)
    } else {
      await axios.post(`${API_BASE}/schedule/`, payload)
    }
    successMessage.value = clashing
      ? 'บันทึกสำเร็จ — รวมเป็นคาบสอนร่วมกันแล้ว'
      : (wasEditing ? 'แก้ไข/ย้ายตารางสอนคาบนี้สำเร็จ' : 'บันทึกตารางสอนคาบนี้สำเร็จ')
    teResetForm()
    await refreshAllViews()
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail && typeof detail === 'object' && detail.conflicts) {
      conflictErrors.value = detail.conflicts
    } else if (e?.response?.status === 401) {
      conflictErrors.value = ['กรุณาเข้าสู่ระบบก่อนบันทึกข้อมูล']
    } else {
      conflictErrors.value = ['เกิดข้อผิดพลาดในการบันทึก กรุณาลองใหม่อีกครั้ง']
    }
    await refreshAllViews()
  } finally {
    teSaving.value = false
  }
}

// คลิกช่องในตารางของครู (มุมมอง "ตารางครู"):
// - ถ้ากำลังแก้ไข/ย้ายคาบอยู่แล้ว → คลิกช่องใหม่ = ย้ายไปคาบนั้นทันที (บันทึกทันที)
// - ถ้าช่องนั้นครูคนนี้มีคาบอยู่แล้ว (และยังไม่ได้กดแก้ไข) → แสดงตัวเลือกแก้ไข/ย้าย/ลบ ไม่บันทึกทับ
// - ถ้าช่องว่างและกรอกฟอร์ม (ชั้นเรียน/วิชา) ไว้ครบแล้ว → บันทึกทันที
const tePickSlot = async (day: number, period: number) => {
  if (!overviewTeacherId.value) return
  conflictErrors.value = []
  successMessage.value = ''

  if (teEditingEntryId.value) {
    teSelectedDay.value = day
    teSelectedPeriod.value = period
    await teSaveEntry()
    return
  }

  const existing = teEntryAt(day, period)
  if (existing) {
    teSelectedDay.value = day
    teSelectedPeriod.value = period
    return
  }

  if (teClassroomIds.value.length === 0 || !teSubjectId.value) {
    alert('กรุณาเลือกชั้นเรียนและวิชาก่อน แล้วค่อยคลิกวัน/คาบในตาราง')
    return
  }
  teSelectedDay.value = day
  teSelectedPeriod.value = period
  await teSaveEntry()
}

</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-2">
      <CalendarDays class="w-7 h-7 text-blue-600" />
      <h2 class="text-2xl font-bold text-gray-800">จัดตารางสอนแบบ Manual (ทีละคาบ)</h2>
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-400">
      <Loader2 class="w-10 h-10 animate-spin mx-auto mb-2" /> กำลังโหลดข้อมูล...
    </div>

    <div v-else class="flex flex-wrap items-center gap-2 bg-white p-3 rounded-xl shadow-sm border border-gray-200">
      <span class="text-xs font-bold text-gray-500 uppercase shrink-0">มุมมองตาราง:</span>
      <button
        @click="overviewMode = 'classroom'"
        :class="overviewMode === 'classroom' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        class="text-xs font-bold px-3 py-1.5 rounded-md transition-colors flex items-center gap-1"
      >
        <Home class="w-3.5 h-3.5" /> ตารางนักเรียน (ห้องเรียน) — แก้ไขได้
      </button>
      <button
        @click="overviewMode = 'teacher'"
        :class="overviewMode === 'teacher' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        class="text-xs font-bold px-3 py-1.5 rounded-md transition-colors flex items-center gap-1"
      >
        <Users class="w-3.5 h-3.5" /> ตารางครู — แก้ไขได้
      </button>
      <button
        @click="overviewMode = 'room'"
        :class="overviewMode === 'room' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
        class="text-xs font-bold px-3 py-1.5 rounded-md transition-colors flex items-center gap-1"
      >
        <MapPin class="w-3.5 h-3.5" /> ตารางห้อง/สถานที่
      </button>
    </div>

    <div v-if="!loading" class="flex flex-wrap items-center gap-2 bg-white p-3 rounded-xl shadow-sm border border-gray-200">
      <span class="text-xs font-bold text-gray-500 uppercase shrink-0">ดาวน์โหลด PDF (รวมทุกคน/ทุกห้องเป็นไฟล์เดียว):</span>
      <button
        @click="downloadPdf('teachers', 'teachtabel_teacher_schedules.pdf')"
        :disabled="downloadingPdf !== null"
        class="text-xs font-bold px-3 py-1.5 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1 disabled:opacity-50"
      >
        <Loader2 v-if="downloadingPdf === 'teachers'" class="w-3.5 h-3.5 animate-spin" />
        <FileDown v-else class="w-3.5 h-3.5" /> ตารางครู
      </button>
      <button
        @click="downloadPdf('classrooms', 'teachtabel_classroom_schedules.pdf')"
        :disabled="downloadingPdf !== null"
        class="text-xs font-bold px-3 py-1.5 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1 disabled:opacity-50"
      >
        <Loader2 v-if="downloadingPdf === 'classrooms'" class="w-3.5 h-3.5 animate-spin" />
        <FileDown v-else class="w-3.5 h-3.5" /> ตารางนักเรียน (ห้องเรียน)
      </button>
      <button
        @click="downloadPdf('rooms', 'teachtabel_room_schedules.pdf')"
        :disabled="downloadingPdf !== null"
        class="text-xs font-bold px-3 py-1.5 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors flex items-center gap-1 disabled:opacity-50"
      >
        <Loader2 v-if="downloadingPdf === 'rooms'" class="w-3.5 h-3.5 animate-spin" />
        <FileDown v-else class="w-3.5 h-3.5" /> ตารางห้อง/สถานที่
      </button>
    </div>

    <div v-if="!loading" class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- Form (เฉพาะมุมมองห้องเรียน — ใช้แก้ไขตารางได้) -->
      <div v-if="overviewMode === 'classroom'" class="xl:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit sticky top-6 space-y-4">
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">1. เลือกชั้นเรียน</label>
          <SearchableSelect v-model="selectedClassroomId" :options="classroomOptions" placeholder="ค้นหาห้องเรียน เช่น 1/1" />
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">2. วัน</label>
            <select v-model="selectedDay" @change="conflictErrors = []; successMessage = ''" class="w-full border rounded-md p-2 text-sm">
              <option v-for="d in days" :key="d.val" :value="d.val">{{ d.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">3. คาบที่</label>
            <select v-model="selectedPeriod" @change="conflictErrors = []; successMessage = ''" class="w-full border rounded-md p-2 text-sm">
              <option v-for="p in periods" :key="p" :value="p">คาบ {{ p }}</option>
            </select>
          </div>
        </div>

        <!-- โหมดบันทึก -->
        <div class="flex rounded-lg overflow-hidden border border-gray-200 text-xs font-bold">
          <button
            @click="clubMode = false; conflictErrors = []; successMessage = ''"
            :class="!clubMode ? 'bg-blue-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            class="flex-1 py-2 transition-colors"
          >
            วิชาปกติ
          </button>
          <button
            @click="clubMode = true; conflictErrors = []; successMessage = ''; fetchClubTeacherEntries()"
            :class="clubMode ? 'bg-green-600 text-white' : 'bg-white text-gray-500 hover:bg-gray-50'"
            class="flex-1 py-2 transition-colors"
          >
            ชุมนุม/ลูกเสือ (อิสระ)
          </button>
        </div>

        <!-- โหมดวิชาปกติ -->
        <template v-if="!clubMode">
          <!-- Slot ถูกใช้แล้ว (และไม่ได้อยู่ระหว่างแก้ไข) -->
          <div v-if="currentEntry && !editingEntryId" class="p-4 bg-orange-50 border border-orange-200 rounded-lg space-y-2">
            <p class="text-xs font-bold text-orange-700 flex items-center gap-1">
              <AlertTriangle class="w-4 h-4" /> คาบนี้มีวิชาอยู่แล้ว
            </p>
            <p class="text-sm font-bold text-gray-800">{{ currentEntry.subject_name }}</p>
            <p class="text-xs text-gray-600 flex items-center gap-1"><Users class="w-3 h-3" /> {{ currentEntry.teacher_names.join(', ') }}</p>
            <p v-if="currentEntry.room_name" class="text-xs text-gray-600 flex items-center gap-1"><MapPin class="w-3 h-3" /> {{ currentEntry.room_name }}</p>
            <p class="text-[10px] text-orange-600 pt-1">คาบนี้ใช้งานแล้ว เลือกได้ว่าจะทำอะไร:</p>
            <div class="grid grid-cols-2 gap-2">
              <button @click="startEditEntry(currentEntry)" class="text-xs font-bold text-blue-600 border border-blue-200 rounded-md py-1.5 hover:bg-blue-50 flex items-center justify-center gap-1">
                <Pencil class="w-3 h-3" /> แก้ไข/ย้าย
              </button>
              <button @click="startCoTeach(currentEntry)" class="text-xs font-bold text-purple-600 border border-purple-200 rounded-md py-1.5 hover:bg-purple-50 flex items-center justify-center gap-1">
                <Users class="w-3 h-3" /> สอนร่วม
              </button>
              <button @click="deleteEntry(currentEntry.id)" class="col-span-2 text-xs font-bold text-red-600 border border-red-200 rounded-md py-1.5 hover:bg-red-50 flex items-center justify-center gap-1">
                <Trash2 class="w-3 h-3" /> ลบคาบนี้ทิ้ง
              </button>
            </div>
          </div>

          <!-- ฟอร์มลงวิชา (โหมดเพิ่มใหม่ หรือโหมดแก้ไข) -->
          <template v-else>
            <div v-if="editingEntryId" class="p-2.5 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 space-y-1">
              <div class="flex items-center justify-between font-bold">
                <span class="flex items-center gap-1"><Pencil class="w-3 h-3" /> กำลังแก้ไข/ย้าย — วัน{{ days.find(d => d.val === selectedDay)?.name }} คาบ {{ selectedPeriod }}</span>
                <button @click="cancelEditEntry" class="text-blue-400 hover:text-blue-700"><X class="w-3.5 h-3.5" /></button>
              </div>
              <p class="text-[10px] text-blue-500">คลิกช่องอื่นในตารางเพื่อย้ายไปคาบนั้นทันที หรือแก้รายละเอียดด้านล่างแล้วกดบันทึกเพื่อเก็บไว้ที่คาบเดิม</p>
            </div>
            <div v-if="coTeachHint" class="p-2.5 bg-purple-50 border border-purple-200 rounded-lg text-xs text-purple-700 font-bold flex items-center gap-1">
              <Users class="w-3.5 h-3.5 shrink-0" /> ติ๊กเพิ่มชื่อครูท่านอื่นในรายชื่อด้านล่าง แล้วกดบันทึก เพื่อสอนร่วมกัน
            </div>
            <div>
              <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">4. วิชา</label>
              <SearchableSelect v-model="selectedSubjectId" :options="subjectOptions" placeholder="ค้นหาวิชา เช่น รหัสวิชาหรือชื่อวิชา" />
            </div>

            <div>
              <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">5. ครูผู้สอน (เลือกได้หลายคน)</label>
              <div class="relative mb-2">
                <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
                <input v-model="teacherSearch" placeholder="ค้นหาชื่อครู..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
              </div>
              <div :class="['max-h-36 overflow-y-auto border rounded-md p-2 space-y-1 bg-gray-50', coTeachHint ? 'ring-2 ring-purple-400' : '']">
                <div v-for="t in filteredTeachers" :key="t.id" class="flex items-center hover:bg-blue-50 p-1 rounded">
                  <input type="checkbox" :id="'ms-t-'+t.id" :value="t.id" v-model="selectedTeacherIds" class="rounded text-blue-600">
                  <label :for="'ms-t-'+t.id" class="ml-2 text-xs text-gray-700 cursor-pointer flex-1">
                    <span v-if="t.teacher_code" class="text-gray-400 font-mono">[{{ t.teacher_code }}]</span>
                    {{ t.full_name }}
                  </label>
                </div>
                <p v-if="filteredTeachers.length === 0" class="text-center text-xs text-gray-400 py-2">ไม่พบรายชื่อครู</p>
              </div>
            </div>

            <div>
              <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">6. สถานที่ (ถ้ามี)</label>
              <select v-model="selectedRoomId" class="w-full border rounded-md p-2 text-sm">
                <option value="">-- ตามความเหมาะสม --</option>
                <option v-for="r in rooms" :key="r.id" :value="r.id">{{ r.room_name }}</option>
              </select>
            </div>

            <div>
              <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">หมายเหตุ (ถ้ามี)</label>
              <input v-model="note" placeholder="เช่น สอนแทน, กิจกรรมพิเศษ" class="w-full border rounded-md p-2 text-sm">
            </div>

            <button
              @click="saveEntry"
              :disabled="saving"
              class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 shadow-md"
            >
              <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
              {{ editingEntryId ? 'บันทึกการแก้ไข' : 'บันทึกลงตาราง' }}
            </button>
            <button
              v-if="editingEntryId"
              @click="cancelEditEntry"
              class="w-full text-gray-500 text-xs font-bold py-2 rounded-lg hover:bg-gray-100 transition flex items-center justify-center gap-1"
            >
              <X class="w-3.5 h-3.5" /> ยกเลิกการแก้ไข
            </button>
          </template>
        </template>

        <!-- โหมดชุมนุม (อิสระ) -->
        <template v-else>
          <div class="p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-800 flex items-start gap-2">
            <Info class="w-4 h-4 shrink-0 mt-0.5" />
            <span>ใช้กับทั้ง "ชุมนุม" และ "ลูกเสือ/เนตรนารี/ยุวกาชาด" — สองกิจกรรมนี้ใช้หลักการลงตารางเดียวกัน คือฝั่งห้องเรียนกับฝั่งครูบันทึกแยกอิสระจากกัน ไม่ต้องผูกคู่กัน นักเรียนเดินไปหาครูเอง ครูเดินไปหานักเรียนเอง (ตารางฝั่งห้องเรียนจึงไม่มีชื่อครูขึ้นให้เห็น)</span>
          </div>

          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">วิชา (ชุมนุม/ลูกเสือ)</label>
            <SearchableSelect v-model="clubSubjectId" :options="subjectOptions" placeholder="ค้นหาวิชาชุมนุม/ลูกเสือ" />
          </div>

          <!-- ฝั่งห้องเรียน -->
          <div class="p-3 border border-gray-200 rounded-lg space-y-2">
            <p class="text-xs font-bold text-gray-600">ฝั่งห้องเรียน: {{ selectedClassroomLabel }}</p>
            <template v-if="currentEntry">
              <p class="text-xs text-orange-600 flex items-center gap-1"><AlertTriangle class="w-3 h-3" /> คาบนี้มี "{{ currentEntry.subject_name }}" อยู่แล้ว</p>
              <button @click="deleteEntry(currentEntry.id)" class="w-full text-xs font-bold text-red-600 border border-red-200 rounded-md py-1.5 hover:bg-red-50 flex items-center justify-center gap-1">
                <Trash2 class="w-3 h-3" /> ลบเพื่อจัดใหม่
              </button>
            </template>
            <button
              v-else
              @click="saveClubClassroom"
              :disabled="clubSavingClassroom || !clubSubjectId"
              class="w-full bg-green-600 text-white font-bold py-2 rounded-lg hover:bg-green-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 text-xs"
            >
              <Loader2 v-if="clubSavingClassroom" class="w-3.5 h-3.5 animate-spin" />
              บันทึกห้องนี้เป็นชุมนุม
            </button>
          </div>

          <!-- ฝั่งครู -->
          <div class="p-3 border border-gray-200 rounded-lg space-y-2">
            <p class="text-xs font-bold text-gray-600">ฝั่งครู (ไม่ผูกกับห้องเรียนด้านบน)</p>

            <div v-if="clubTeacherEntries.length" class="space-y-1">
              <div v-for="e in clubTeacherEntries" :key="e.id" class="flex items-center justify-between bg-green-50 border border-green-100 px-2 py-1 rounded text-[11px]">
                <span class="font-medium text-green-800">{{ e.teacher_names.join(', ') }}</span>
                <button @click="deleteClubTeacherEntry(e.id)" class="text-gray-400 hover:text-red-600"><Trash2 class="w-3 h-3" /></button>
              </div>
            </div>

            <div class="relative mb-2">
              <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
              <input v-model="clubTeacherSearch" placeholder="ค้นหาชื่อครู..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-white focus:bg-white outline-none">
            </div>
            <div class="max-h-32 overflow-y-auto border rounded-md p-2 space-y-1 bg-gray-50">
              <div v-for="t in filteredClubTeachers" :key="t.id" class="flex items-center hover:bg-green-50 p-1 rounded">
                <input type="checkbox" :id="'club-t-'+t.id" :value="t.id" v-model="clubTeacherIds" class="rounded text-green-600">
                <label :for="'club-t-'+t.id" class="ml-2 text-xs text-gray-700 cursor-pointer flex-1">
                  <span v-if="t.teacher_code" class="text-gray-400 font-mono">[{{ t.teacher_code }}]</span>
                  {{ t.full_name }}
                </label>
              </div>
              <p v-if="filteredClubTeachers.length === 0" class="text-center text-xs text-gray-400 py-2">ไม่พบรายชื่อครู</p>
            </div>

            <button
              @click="saveClubTeachers"
              :disabled="clubSavingTeacher || !clubSubjectId || clubTeacherIds.length === 0"
              class="w-full bg-green-600 text-white font-bold py-2 rounded-lg hover:bg-green-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 text-xs"
            >
              <Loader2 v-if="clubSavingTeacher" class="w-3.5 h-3.5 animate-spin" />
              บันทึกครูที่เลือกเป็นสอนชุมนุม
            </button>
          </div>
        </template>

        <div v-if="conflictErrors.length" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 space-y-1">
          <p class="font-bold flex items-center gap-1"><AlertTriangle class="w-3 h-3" /> พบตารางซ้ำซ้อน</p>
          <ul class="list-disc list-inside">
            <li v-for="(c, i) in conflictErrors" :key="i">{{ c }}</li>
          </ul>
        </div>
        <div v-if="successMessage" class="p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700 flex items-center gap-1">
          <CheckCircle2 class="w-4 h-4" /> {{ successMessage }}
        </div>
      </div>

      <!-- Form (มุมมองครู — เริ่มจากเลือกครูก่อน แล้วคลิกในตารางฝั่งขวาเพื่อบันทึกทันที) -->
      <div v-else-if="overviewMode === 'teacher'" class="xl:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit sticky top-6 space-y-4">
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">1. เลือกครู</label>
          <SearchableSelect v-model="overviewTeacherId" :options="teacherOptions" placeholder="ค้นหาชื่อครู..." />
        </div>

        <template v-if="overviewTeacherId">
          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">2. ชั้นเรียนที่จะสอน (เลือกได้หลายห้อง)</label>
            <div class="relative mb-2">
              <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
              <input v-model="teClassroomSearch" placeholder="ค้นหาห้องเรียน..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
            </div>
            <div class="max-h-36 overflow-y-auto border rounded-md p-2 space-y-1 bg-gray-50">
              <div v-for="c in filteredClassroomsForTe" :key="c.id" class="flex items-center hover:bg-blue-50 p-1 rounded">
                <input type="checkbox" :id="'te-c-'+c.id" :value="c.id" v-model="teClassroomIds" class="rounded text-blue-600">
                <label :for="'te-c-'+c.id" class="ml-2 text-xs text-gray-700 cursor-pointer flex-1">{{ c.grade_level }}/{{ c.room_name }}</label>
              </div>
              <p v-if="filteredClassroomsForTe.length === 0" class="text-center text-xs text-gray-400 py-2">ไม่พบห้องเรียน</p>
            </div>
          </div>

          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">3. สถานที่ (ถ้ามี)</label>
            <select v-model="teRoomId" class="w-full border rounded-md p-2 text-sm">
              <option value="">-- ตามความเหมาะสม --</option>
              <option v-for="r in rooms" :key="r.id" :value="r.id">{{ r.room_name }}</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">4. วิชา</label>
            <SearchableSelect v-model="teSubjectId" :options="subjectOptions" placeholder="ค้นหาวิชา เช่น รหัสวิชาหรือชื่อวิชา" />
          </div>

          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">หมายเหตุ (ถ้ามี)</label>
            <input v-model="teNote" placeholder="เช่น สอนแทน, กิจกรรมพิเศษ" class="w-full border rounded-md p-2 text-sm">
          </div>

          <label class="flex items-start gap-2 text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-md p-2 cursor-pointer">
            <input type="checkbox" v-model="teCoTeach" :disabled="teClassroomIds.length !== 1" class="mt-0.5 rounded text-blue-600">
            <span>สอนร่วมกับครูท่านอื่น — ถ้าคาบ/ชั้นเรียนนี้มีครูสอนอยู่แล้ว จะรวมเป็นคาบสอนร่วมกัน (ใช้วิชา/ห้องเดิม) แทนการลงซ้ำจนชนกัน (ใช้ได้เมื่อเลือกชั้นเรียนเดียว)</span>
          </label>

          <div class="p-3 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-700 flex items-start gap-2">
            <Info class="w-4 h-4 shrink-0 mt-0.5" />
            <span>5. คลิกวัน/คาบในตารางด้านขวา (ตารางของครูคนนี้) เพื่อบันทึกทันที</span>
          </div>

          <!-- คาบที่คลิกเลือกไว้: มีอยู่แล้ว (แก้ไข/ย้าย/ลบ) หรือกำลังแก้ไข/ย้ายอยู่ -->
          <div v-if="teSelectedDay && teSelectedPeriod">
            <div v-if="teCurrentEntry && !teEditingEntryId" class="p-4 bg-orange-50 border border-orange-200 rounded-lg space-y-2">
              <p class="text-xs font-bold text-orange-700 flex items-center gap-1">
                <AlertTriangle class="w-4 h-4" /> ครูมีคาบนี้อยู่แล้ว
              </p>
              <p class="text-sm font-bold text-gray-800">{{ teCurrentEntry.subject_name }}</p>
              <p class="text-xs text-gray-600 flex items-center gap-1"><Home class="w-3 h-3" /> {{ teCurrentEntry.classroom_names.join(', ') || 'ชุมนุม/ลูกเสือ (อิสระ)' }}</p>
              <p v-if="teCurrentEntry.room_name" class="text-xs text-gray-600 flex items-center gap-1"><MapPin class="w-3 h-3" /> {{ teCurrentEntry.room_name }}</p>
              <div class="flex gap-2 mt-2">
                <button @click="teStartEdit(teCurrentEntry)" class="flex-1 text-xs font-bold text-blue-600 border border-blue-200 rounded-md py-1.5 hover:bg-blue-50 flex items-center justify-center gap-1">
                  <Pencil class="w-3 h-3" /> แก้ไข/ย้าย
                </button>
                <button @click="teDeleteEntry(teCurrentEntry.id)" class="flex-1 text-xs font-bold text-red-600 border border-red-200 rounded-md py-1.5 hover:bg-red-50 flex items-center justify-center gap-1">
                  <Trash2 class="w-3 h-3" /> ลบ
                </button>
              </div>
            </div>

            <template v-else-if="teEditingEntryId">
              <div class="p-2.5 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 font-bold flex items-center justify-between">
                <span class="flex items-center gap-1">
                  <Pencil class="w-3 h-3" /> กำลังแก้ไข/ย้าย — วัน{{ days.find(d => d.val === teSelectedDay)?.name }} คาบ {{ teSelectedPeriod }}
                </span>
                <button @click="teCancelEdit" class="text-blue-400 hover:text-blue-700"><X class="w-3.5 h-3.5" /></button>
              </div>
              <p class="text-[10px] text-gray-400 mt-1">คลิกช่องอื่นในตารางเพื่อย้ายไปคาบนั้นทันที หรือกดปุ่มด้านล่างเพื่อบันทึกที่คาบเดิม</p>
              <button
                @click="teSaveEntry"
                :disabled="teSaving"
                class="w-full mt-2 bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 shadow-md"
              >
                <Loader2 v-if="teSaving" class="w-4 h-4 animate-spin" />
                บันทึกการแก้ไข
              </button>
            </template>

            <p v-else class="text-xs text-gray-500">
              คาบว่าง — วัน{{ days.find(d => d.val === teSelectedDay)?.name }} คาบ {{ teSelectedPeriod }} (บันทึกไปแล้วเมื่อคลิก ถ้ายังไม่ขึ้นให้ตรวจว่ากรอกชั้นเรียน/วิชาครบหรือยัง)
            </p>
          </div>
        </template>

        <div v-if="conflictErrors.length" class="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700 space-y-1">
          <p class="font-bold flex items-center gap-1"><AlertTriangle class="w-3 h-3" /> พบตารางซ้ำซ้อน</p>
          <ul class="list-disc list-inside">
            <li v-for="(c, i) in conflictErrors" :key="i">{{ c }}</li>
          </ul>
        </div>
        <div v-if="successMessage" class="p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700 flex items-center gap-1">
          <CheckCircle2 class="w-4 h-4" /> {{ successMessage }}
        </div>
      </div>

      <!-- Weekly grid -->
      <div :class="(overviewMode === 'classroom' || overviewMode === 'teacher') ? 'xl:col-span-2' : 'xl:col-span-3'" class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <div class="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <h3 class="font-bold text-gray-700 flex items-center gap-2">
            <BookOpen v-if="overviewMode === 'classroom'" class="w-5 h-5 text-blue-600" />
            <Users v-else-if="overviewMode === 'teacher'" class="w-5 h-5 text-blue-600" />
            <MapPin v-else class="w-5 h-5 text-blue-600" />
            <span v-if="overviewMode === 'classroom'">ตารางสอนของชั้นเรียนที่เลือก</span>
            <span v-else-if="overviewMode === 'teacher'">ตารางสอนของครู</span>
            <span v-else>ตารางการใช้ห้อง/สถานที่</span>
          </h3>
          <Loader2 v-if="loadingSchedule || loadingOverview" class="w-4 h-4 animate-spin text-blue-500" />
        </div>

        <div v-if="overviewMode === 'room'" class="mb-4 max-w-sm">
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">ค้นหาห้อง/สถานที่</label>
          <SearchableSelect v-model="overviewRoomId" :options="roomOptions" placeholder="ค้นหาห้อง/สถานที่..." />
        </div>

        <div
          v-if="(overviewMode === 'teacher' && !overviewTeacherId) || (overviewMode === 'room' && !overviewRoomId)"
          class="text-center py-12 text-gray-400 italic text-sm"
        >
          เลือก{{ overviewMode === 'teacher' ? 'ครูด้านซ้าย' : 'ห้อง/สถานที่ด้านบน' }}เพื่อดูตาราง
        </div>
        <template v-else>
          <div class="overflow-x-auto">
            <table class="min-w-full text-xs border-collapse">
              <thead>
                <tr>
                  <th class="p-2 border bg-gray-50 text-gray-500">คาบ</th>
                  <th v-for="d in days" :key="d.val" class="p-2 border bg-gray-50 text-gray-600 font-bold">{{ d.name }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in periods" :key="p">
                  <td class="p-2 border text-center font-bold text-gray-500 bg-gray-50">{{ p }}</td>
                  <td
                    v-for="d in days"
                    :key="d.val"
                    @click="overviewMode === 'classroom' ? pickSlot(d.val, p) : (overviewMode === 'teacher' ? tePickSlot(d.val, p) : null)"
                    :class="[
                      'p-2 border align-top min-w-[110px] transition-colors',
                      (overviewMode === 'classroom' || overviewMode === 'teacher') ? 'cursor-pointer' : '',
                      overviewMode === 'classroom' && selectedDay === d.val && selectedPeriod === p ? 'ring-2 ring-blue-500' : '',
                      overviewMode === 'teacher' && teSelectedDay === d.val && teSelectedPeriod === p ? 'ring-2 ring-blue-500' : '',
                      activeEntryAt(d.val, p) ? 'bg-blue-50 hover:bg-blue-100' : ((overviewMode === 'classroom' || overviewMode === 'teacher') ? 'hover:bg-gray-50' : '')
                    ]"
                  >
                    <template v-if="activeEntryAt(d.val, p)">
                      <p class="font-bold text-blue-800 leading-tight">{{ activeEntryAt(d.val, p)!.subject_name.split(' ')[0] }}</p>
                      <p class="text-[10px] text-gray-500 truncate">{{ cellSubtitle(activeEntryAt(d.val, p)!) }}</p>
                    </template>
                    <span v-else class="text-gray-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="overviewMode === 'classroom'" class="text-[10px] text-gray-400 mt-3">คลิกที่ช่องในตารางเพื่อเลือกวัน/คาบในฟอร์มด้านซ้ายได้ทันที</p>
          <p v-else-if="overviewMode === 'teacher'" class="text-[10px] text-gray-400 mt-3">คลิกที่ช่องว่างในตารางเพื่อบันทึกทันที (ต้องกรอกชั้นเรียน/วิชาในฟอร์มด้านซ้ายก่อน)</p>
        </template>
      </div>
    </div>
  </div>
</template>
