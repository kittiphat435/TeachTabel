<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import axios from 'axios'
import { Plus, Users, BookOpen, Home, Clock, Loader2, MapPin, Search, UserPlus, Flag, Pencil, Trash2, X, Layers, Check, Copy } from 'lucide-vue-next'
import SearchableSelect from './SearchableSelect.vue'
import { usePlan } from '../composables/usePlan'
import { useAcademicYear } from '../composables/useAcademicYear'

const API_BASE = 'http://localhost:8000'

interface Teacher { id: string; full_name: string; department: string; teacher_code?: string | null }
interface Subject { id: string; subject_code: string; subject_name: string }
interface Classroom { id: string; grade_level: string; room_name: string }
interface Room { id: string; room_name: string; room_type: string }

const teachers = ref<Teacher[]>([])
const subjects = ref<Subject[]>([])
const classrooms = ref<Classroom[]>([])
const rooms = ref<Room[]>([])
const assignments = ref<any[]>([])

const loading = ref(true)
const saving = ref(false)

// --- แผนภาระงานสอน (Plan) ---
// ใช้แยกภาระงานสอน+ตารางสอนหลายเวอร์ชันภายในปี/เทอมเดียวกัน เช่น กรณีจำนวนครูในกลุ่มสาระเปลี่ยนกลางเทอม
const { plans, currentPlanId, currentPlanLabel, setPlans, setCurrentPlanId } = usePlan()
const { currentYearKey } = useAcademicYear()
const showNewPlanModal = ref(false)
const newPlanLabel = ref('')
const duplicateFromCurrent = ref(true)
const renamingPlan = ref(false)
const renamePlanLabel = ref('')
const planBusy = ref(false)

const fetchPlans = async () => {
  try {
    const res = await axios.get(`${API_BASE}/plans/`)
    setPlans(res.data)
  } catch (e) { console.error('Error fetching plans:', e) }
}

const onSelectPlan = (e: Event) => {
  setCurrentPlanId((e.target as HTMLSelectElement).value)
}

const openNewPlanModal = () => {
  newPlanLabel.value = `แผน ${plans.value.length + 1}`
  duplicateFromCurrent.value = true
  showNewPlanModal.value = true
}

const createNewPlan = async () => {
  if (!newPlanLabel.value.trim()) {
    alert('กรุณาระบุชื่อแผน')
    return
  }
  planBusy.value = true
  try {
    const res = await axios.post(`${API_BASE}/plans/`, {
      label: newPlanLabel.value.trim(),
      duplicate_from: duplicateFromCurrent.value ? currentPlanId.value : null,
    })
    showNewPlanModal.value = false
    await fetchPlans()
    setCurrentPlanId(res.data.plan_id)
  } catch (e) {
    alert('สร้างแผนไม่สำเร็จ')
  } finally {
    planBusy.value = false
  }
}

const startRenamePlan = () => {
  renamePlanLabel.value = currentPlanLabel.value
  renamingPlan.value = true
}
const cancelRenamePlan = () => { renamingPlan.value = false }

const saveRenamePlan = async () => {
  if (!renamePlanLabel.value.trim() || !currentPlanId.value) return
  try {
    await axios.put(`${API_BASE}/plans/${currentPlanId.value}`, { label: renamePlanLabel.value.trim() })
    renamingPlan.value = false
    await fetchPlans()
  } catch (e) {
    alert('บันทึกไม่สำเร็จ')
  }
}

const deleteCurrentPlan = async () => {
  if (plans.value.length <= 1) {
    alert('ต้องมีอย่างน้อย 1 แผนเสมอ สร้างแผนใหม่ก่อนถึงจะลบแผนนี้ได้')
    return
  }
  if (!confirm(`ลบแผน "${currentPlanLabel.value}" ทิ้ง? ภาระงานสอนและตารางสอนทั้งหมดในแผนนี้จะหายไปด้วย (แผนอื่นไม่ถูกกระทบ)`)) return
  try {
    await axios.delete(`${API_BASE}/plans/${currentPlanId.value}`)
    await fetchPlans()
  } catch (e) {
    alert('ลบไม่สำเร็จ')
  }
}

// Form State
const selectedSubject = ref('')
const selectedTeachers = ref<string[]>([])
const selectedClassrooms = ref<string[]>([])
// ห้องปฏิบัติการที่ครูวิชานี้สอนได้ (เลือกได้หลายห้อง เช่น ครูคอมเลือก 123, 125, 138)
// ถ้าไม่เลือกเลย = สอนที่ห้องประจำของนักเรียนเอง ไม่ต้องจองห้องแยก
const selectedRoomIds = ref<string[]>([])
// เลือก "ห้องประจำ" เป็นตัวเลือกได้ชัดเจน — ถ้าติ๊กไว้คู่กับห้องปฏิบัติการ ระบบจะใช้ห้องประจำเป็นตัวสำรองถ้าห้องปฏิบัติการที่เลือกไม่ว่างเลย
const includeHomeRoom = ref(false)
const totalPeriods = ref(2)
const selectedSplitPattern = ref<number[]>([2])
const editingAssignmentId = ref<string | null>(null)

// Search States
const teacherSearch = ref('')
const filteredTeachers = computed(() => {
  if (!teacherSearch.value) return teachers.value
  const q = teacherSearch.value
  return teachers.value.filter(t => t.full_name.includes(q) || (t.teacher_code || '').includes(q))
})

const classroomSearch = ref('')
const filteredClassrooms = computed(() => {
  if (!classroomSearch.value) return classrooms.value
  return classrooms.value.filter(c => `${c.grade_level}/${c.room_name}`.includes(classroomSearch.value))
})

const subjectOptions = computed(() =>
  subjects.value.map(s => ({ value: s.id, label: `${s.subject_code} - ${s.subject_name}` }))
)

// เฉพาะห้องปฏิบัติการให้เลือกทีละห้อง (ห้องประจำชั้นไม่ต้องเลือกเบอร์ห้อง เพราะระบบผูกไว้แล้วว่านักเรียนแต่ละชั้นอยู่ห้องไหน — ใช้อัตโนมัติถ้าไม่เลือกห้องปฏิบัติการเลย)
const labRooms = computed(() => rooms.value.filter(r => r.room_type === 'ห้องปฏิบัติการ'))
const roomSearch = ref('')
const filteredRooms = computed(() => {
  if (!roomSearch.value) return labRooms.value
  return labRooms.value.filter(r => r.room_name.includes(roomSearch.value))
})

// Quick Add Teacher
const showQuickAddTeacher = ref(false)
const quickTeacherName = ref('')
const quickTeacherDept = ref('')

const addQuickTeacher = async () => {
  if (!quickTeacherName.value) return
  try {
    await axios.post(`${API_BASE}/teachers/manual`, {
      full_name: quickTeacherName.value,
      department: quickTeacherDept.value
    })
    quickTeacherName.value = ''
    quickTeacherDept.value = ''
    showQuickAddTeacher.value = false
    await fetchData() // Refresh list
  } catch (e) { alert('เพิ่มไม่สำเร็จ') }
}

// Dynamic Split Patterns
const availablePatterns = computed(() => {
  const p = totalPeriods.value
  if (p === 1) return [[1]]
  if (p === 2) return [[2], [1, 1]]
  if (p === 3) return [[2, 1], [1, 1, 1]]
  if (p === 4) return [[2, 2], [2, 1, 1], [1, 1, 1, 1]]
  if (p === 5) return [[2, 2, 1], [2, 1, 1, 1], [1, 1, 1, 1, 1]]
  return [[p]]
})

watch(totalPeriods, () => {
  selectedSplitPattern.value = availablePatterns.value[0]
})

const fetchData = async () => {
  loading.value = true
  try {
    const [tRes, sRes, cRes, rRes, aRes] = await Promise.all([
      axios.get(`${API_BASE}/teachers/`),
      axios.get(`${API_BASE}/subjects/`),
      axios.get(`${API_BASE}/classrooms/`),
      axios.get(`${API_BASE}/rooms/`),
      axios.get(`${API_BASE}/assignments/`)
    ])
    teachers.value = tRes.data
    subjects.value = sRes.data
    classrooms.value = cRes.data
    rooms.value = rRes.data
    assignments.value = aRes.data
  } catch (error) {
    console.error('Error fetching data:', error)
  } finally {
    loading.value = false
  }
}

const initialize = async () => {
  await fetchPlans()
  await fetchData()
}
onMounted(initialize)

// สลับแผน หรือสลับปีการศึกษา (จาก dropdown บนสุดของแอป) ต้องโหลดแผน+ภาระงานใหม่ให้ตรงกับบริบทปัจจุบัน
watch(currentPlanId, () => {
  fetchData()
  resetForm()
})
watch(currentYearKey, () => {
  initialize()
})

const resetForm = () => {
  selectedTeachers.value = []
  selectedClassrooms.value = []
  selectedSubject.value = ''
  selectedRoomIds.value = []
  includeHomeRoom.value = false
  totalPeriods.value = 2
  selectedSplitPattern.value = [2]
  editingAssignmentId.value = null
}

const saveAssignment = async () => {
  if (!selectedSubject.value || selectedTeachers.value.length === 0 || selectedClassrooms.value.length === 0) {
    alert('กรุณากรอกข้อมูลให้ครบถ้วน')
    return
  }

  saving.value = true
  const payload = {
    subject_id: selectedSubject.value,
    teacher_ids: selectedTeachers.value,
    classroom_ids: selectedClassrooms.value,
    room_ids: selectedRoomIds.value,
    include_home_room: includeHomeRoom.value,
    total_periods: totalPeriods.value,
    period_split: selectedSplitPattern.value
  }
  try {
    if (editingAssignmentId.value) {
      await axios.put(`${API_BASE}/assignments/${editingAssignmentId.value}`, payload)
      alert('แก้ไขภาระงานสำเร็จ')
    } else {
      await axios.post(`${API_BASE}/assignments/`, payload)
      alert('บันทึกภาระงานสำเร็จ')
    }
    await fetchData()
    resetForm()
  } catch (error) {
    alert('เกิดข้อผิดพลาดในการบันทึก')
  } finally {
    saving.value = false
  }
}

const startEditAssignment = async (a: any) => {
  editingAssignmentId.value = a.id
  selectedSubject.value = a.subject_id
  selectedTeachers.value = [...(a.teacher_ids || [])]
  selectedClassrooms.value = [...(a.classroom_ids || [])]
  selectedRoomIds.value = [...(a.room_ids || [])]
  includeHomeRoom.value = !!a.include_home_room
  totalPeriods.value = a.total_periods
  await nextTick() // รอ watch(totalPeriods) รีเซ็ต selectedSplitPattern ก่อน แล้วค่อยตั้งค่าที่ถูกต้องทับ
  const match = availablePatterns.value.find(p => JSON.stringify(p) === JSON.stringify(a.period_split))
  selectedSplitPattern.value = match || a.period_split
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const cancelEditAssignment = () => {
  resetForm()
}

const deleteAssignment = async (id: string) => {
  if (!confirm('ยืนยันการลบภาระงานนี้?')) return
  try {
    await axios.delete(`${API_BASE}/assignments/${id}`)
    if (editingAssignmentId.value === id) resetForm()
    await fetchData()
  } catch (error) {
    alert('ลบไม่สำเร็จ')
  }
}
</script>

<template>
  <div class="space-y-4">
    <!-- แผนภาระงานสอน -->
    <div class="bg-white p-4 rounded-xl shadow-sm border border-purple-200">
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-2 flex-wrap">
          <Layers class="w-4 h-4 text-purple-600 shrink-0" />
          <span class="text-xs font-bold text-gray-500 uppercase shrink-0">แผนภาระงานสอน:</span>

          <template v-if="!renamingPlan">
            <select
              :value="currentPlanId"
              @change="onSelectPlan"
              class="text-sm font-bold border border-purple-200 rounded-md px-2 py-1.5 bg-purple-50 text-purple-700 outline-none"
            >
              <option v-if="plans.length === 0" value="">ยังไม่มีแผน</option>
              <option v-for="p in plans" :key="p.id" :value="p.id">{{ p.label }}</option>
            </select>
            <button @click="startRenamePlan" :disabled="!currentPlanId" class="p-1.5 rounded border border-gray-200 text-gray-400 hover:text-purple-600 hover:bg-purple-50 disabled:opacity-30">
              <Pencil class="w-3.5 h-3.5" />
            </button>
          </template>
          <template v-else>
            <input
              v-model="renamePlanLabel"
              class="text-sm font-bold border border-purple-300 rounded-md px-2 py-1.5"
              @keyup.enter="saveRenamePlan"
              @keyup.esc="cancelRenamePlan"
            >
            <button @click="saveRenamePlan" class="p-1.5 rounded border border-green-200 text-green-600 hover:bg-green-50">
              <Check class="w-3.5 h-3.5" />
            </button>
            <button @click="cancelRenamePlan" class="p-1.5 rounded border border-gray-200 text-gray-400 hover:bg-gray-50">
              <X class="w-3.5 h-3.5" />
            </button>
          </template>
        </div>

        <div class="flex items-center gap-2">
          <button @click="openNewPlanModal" class="text-xs bg-purple-600 text-white font-bold px-3 py-2 rounded-md hover:bg-purple-700 flex items-center gap-1">
            <Plus class="w-3.5 h-3.5" /> แผนใหม่
          </button>
          <button @click="deleteCurrentPlan" :disabled="plans.length <= 1" class="p-2 rounded-md border border-gray-200 text-red-400 hover:bg-red-50 disabled:opacity-30 disabled:cursor-not-allowed" title="ลบแผนนี้">
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
      <p class="text-[10px] text-gray-400 mt-2">แต่ละแผนแยกภาระงานสอนและตารางสอนออกจากกันอิสระ (ครู/วิชา/ห้องเรียน/ห้อง ยังใช้ชุดเดียวกันทุกแผน) — เหมาะกับกรณีทดลองจัดสรรภาระงานหลายแบบ เช่น ครูในกลุ่มสาระเปลี่ยนจำนวนกลางเทอม</p>
    </div>

    <!-- Modal: สร้างแผนใหม่ -->
    <div v-if="showNewPlanModal" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" @click.self="showNewPlanModal = false">
      <div class="bg-white rounded-xl shadow-xl max-w-sm w-full p-6 space-y-4">
        <div class="flex items-center justify-between">
          <h3 class="font-bold text-gray-800 flex items-center gap-2"><Layers class="w-4 h-4 text-purple-600" /> สร้างแผนใหม่</h3>
          <button @click="showNewPlanModal = false"><X class="w-5 h-5 text-gray-400" /></button>
        </div>
        <div>
          <label class="text-xs font-bold text-gray-500 block mb-1">ชื่อแผน</label>
          <input v-model="newPlanLabel" placeholder="เช่น แผน 2 (ครู 6 คน)" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm">
        </div>
        <label v-if="currentPlanId" class="flex items-start gap-2 text-xs text-gray-600 bg-gray-50 p-3 rounded-lg border border-gray-100 cursor-pointer">
          <input type="checkbox" v-model="duplicateFromCurrent" class="w-4 h-4 mt-0.5">
          <span class="flex items-center gap-1"><Copy class="w-3.5 h-3.5 text-purple-500 shrink-0" /> คัดลอกภาระงานสอน + ตารางสอนจากแผน "{{ currentPlanLabel }}" มาเป็นจุดเริ่มต้น (แนะนำ)</span>
        </label>
        <button
          @click="createNewPlan"
          :disabled="planBusy"
          class="w-full bg-purple-600 text-white font-bold py-3 rounded-lg hover:bg-purple-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2"
        >
          <Loader2 v-if="planBusy" class="w-4 h-4 animate-spin" />
          สร้างแผน
        </button>
      </div>
    </div>

  <div class="grid grid-cols-1 xl:grid-cols-4 gap-6">
    <!-- Left: Entry Form -->
    <div class="xl:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit sticky top-6">
      <h2 class="text-lg font-bold mb-4 flex items-center gap-2 text-blue-600">
        <Plus class="w-5 h-5" /> {{ editingAssignmentId ? 'แก้ไขภาระงาน' : 'มอบหมายภาระงาน' }}
      </h2>
      
      <div v-if="loading" class="text-center py-4 text-gray-400">กำลังโหลด...</div>
      
      <div v-else class="space-y-4">
        <!-- Subject -->
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase tracking-tight">1. เลือกวิชา</label>
          <SearchableSelect v-model="selectedSubject" :options="subjectOptions" placeholder="ค้นหาวิชา เช่น รหัสวิชาหรือชื่อวิชา" />
        </div>

        <!-- Teachers -->
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-xs font-bold text-gray-500 uppercase tracking-tight">2. ครูผู้สอน (สอนร่วมเลือกได้หลายคน)</label>
            <button @click="showQuickAddTeacher = !showQuickAddTeacher" class="text-blue-600 hover:text-blue-800 transition">
              <UserPlus class="w-4 h-4" />
            </button>
          </div>

          <!-- Quick Add Form -->
          <div v-if="showQuickAddTeacher" class="mb-3 p-3 bg-blue-50 rounded-lg border border-blue-100 space-y-2">
            <input v-model="quickTeacherName" placeholder="ชื่อ-นามสกุลครู" class="w-full text-xs p-2 border rounded">
            <div class="flex gap-2">
              <input v-model="quickTeacherDept" placeholder="กลุ่มสาระ" class="w-full text-xs p-2 border rounded">
              <button @click="addQuickTeacher" class="bg-blue-600 text-white text-[10px] px-2 rounded font-bold uppercase">เพิ่ม</button>
            </div>
          </div>

          <div class="relative mb-2">
            <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
            <input v-model="teacherSearch" placeholder="ค้นหาชื่อครู..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
          </div>

          <div class="max-h-40 overflow-y-auto border border-gray-200 rounded-md p-2 space-y-1 bg-white text-sm">
            <div v-for="t in filteredTeachers" :key="t.id" class="flex items-center hover:bg-blue-50 p-1 rounded transition-colors">
              <input type="checkbox" :id="'t-'+t.id" :value="t.id" v-model="selectedTeachers" class="rounded text-blue-600 focus:ring-blue-500 w-4 h-4">
              <label :for="'t-'+t.id" class="ml-2 text-xs text-gray-700 cursor-pointer flex-1">
                <span v-if="t.teacher_code" class="text-gray-400 font-mono">[{{ t.teacher_code }}]</span>
                {{ t.full_name }}
              </label>
            </div>
            <div v-if="filteredTeachers.length === 0" class="text-center py-4 text-xs text-gray-400">ไม่พบรายชื่อครู</div>
          </div>
          <div class="mt-1 text-[10px] text-blue-600 font-bold" v-if="selectedTeachers.length > 0">
            เลือกแล้ว {{ selectedTeachers.length }} ท่าน
          </div>
        </div>

        <!-- Classrooms -->
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase tracking-tight">3. ชั้นเรียน (เลือกได้หลายห้อง)</label>
          <div class="relative mb-2">
            <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
            <input v-model="classroomSearch" placeholder="ค้นหาห้องเรียน เช่น 1/1" class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
          </div>
          <div class="max-h-32 overflow-y-auto border border-gray-200 rounded-md p-2 space-y-1 bg-gray-50 text-sm">
            <div v-for="c in filteredClassrooms" :key="c.id" class="flex items-center">
              <input type="checkbox" :id="'c-'+c.id" :value="c.id" v-model="selectedClassrooms" class="rounded text-blue-600 w-4 h-4">
              <label :for="'c-'+c.id" class="ml-2 text-xs text-gray-600 cursor-pointer">{{ c.grade_level }}/{{ c.room_name }}</label>
            </div>
            <p v-if="filteredClassrooms.length === 0" class="text-center text-xs text-gray-400 py-2">ไม่พบห้องเรียน</p>
          </div>
        </div>

        <!-- Room -->
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase tracking-tight">4. ห้องที่สอนได้ (ถ้ามี)</label>
          <p class="text-[10px] text-gray-400 mb-1.5">เลือกห้องปฏิบัติการได้หลายห้อง (เช่น ครูคอมเลือกห้องคอมที่ใกล้กัน) และ/หรือติ๊ก "ห้องประจำ" ไว้เป็นตัวสำรอง — ไม่ต้องเลือกเบอร์ห้องประจำเอง เพราะระบบผูกไว้แล้วว่านักเรียนแต่ละชั้นอยู่ห้องไหน (ผูกได้ที่เมนู "สถานที่/ห้อง")</p>

          <label class="flex items-center gap-2 mb-2 p-2 rounded-md border-2 cursor-pointer transition-colors" :class="includeHomeRoom ? 'border-purple-400 bg-purple-50' : 'border-gray-200 bg-white hover:bg-gray-50'">
            <input type="checkbox" v-model="includeHomeRoom" class="rounded text-purple-600 w-4 h-4">
            <span class="text-xs font-bold text-purple-700">ห้องประจำ</span>
            <span class="text-[10px] text-gray-400">(ใช้ห้องประจำของนักเรียนแต่ละชั้นอัตโนมัติ)</span>
          </label>

          <div class="relative mb-2">
            <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
            <input v-model="roomSearch" placeholder="ค้นหาห้องปฏิบัติการ..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
          </div>
          <div class="max-h-32 overflow-y-auto border border-gray-200 rounded-md p-2 space-y-1 bg-gray-50 text-sm">
            <div v-for="r in filteredRooms" :key="r.id" class="flex items-center">
              <input type="checkbox" :id="'r-'+r.id" :value="r.id" v-model="selectedRoomIds" class="rounded text-blue-600 w-4 h-4">
              <label :for="'r-'+r.id" class="ml-2 text-xs text-gray-600 cursor-pointer">{{ r.room_name }}</label>
            </div>
            <p v-if="filteredRooms.length === 0" class="text-center text-xs text-gray-400 py-2">ไม่พบห้องปฏิบัติการ (เพิ่มได้ที่ "จัดการข้อมูลพื้นฐาน")</p>
          </div>
          <div class="mt-1 text-[10px] text-blue-600 font-bold" v-if="selectedRoomIds.length > 0">
            เลือกแล้ว {{ selectedRoomIds.length }} ห้อง
          </div>
        </div>

        <!-- Period Split -->
        <div class="grid grid-cols-2 gap-2 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <div class="col-span-1">
            <label class="block text-[10px] font-bold text-blue-800 mb-1 uppercase">จำนวนคาบรวม</label>
            <input type="number" v-model="totalPeriods" class="w-full border-blue-200 rounded p-1 text-sm font-bold text-center">
          </div>
          <div class="col-span-1">
            <label class="block text-[10px] font-bold text-blue-800 mb-1 uppercase">รูปแบบการจัด</label>
            <select v-model="selectedSplitPattern" class="w-full border-blue-200 rounded p-1 text-sm font-bold">
              <option v-for="(p, i) in availablePatterns" :key="i" :value="p">{{ p.join(' + ') }}</option>
            </select>
          </div>
        </div>

        <button
          @click="saveAssignment"
          :disabled="saving"
          class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 mt-2 shadow-md"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          {{ editingAssignmentId ? 'บันทึกการแก้ไข' : 'บันทึกภาระงาน' }}
        </button>
        <button
          v-if="editingAssignmentId"
          @click="cancelEditAssignment"
          class="w-full text-gray-500 text-sm font-bold py-2 rounded-lg hover:bg-gray-100 transition flex items-center justify-center gap-1"
        >
          <X class="w-3.5 h-3.5" /> ยกเลิกการแก้ไข
        </button>
      </div>
    </div>

    <!-- Right: List -->
    <div class="xl:col-span-3 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-bold text-gray-800">รายการภาระงานทั้งหมด</h2>
        <span class="text-xs font-bold px-3 py-1 bg-gray-100 text-gray-500 rounded-full">ทั้งหมด {{ assignments.length }} รายการ</span>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-gray-600 font-bold">
            <tr>
              <th class="px-4 py-4 text-left border-b">ครูผู้สอน</th>
              <th class="px-4 py-4 text-left border-b">ชั้นเรียน</th>
              <th class="px-4 py-4 text-left border-b">วิชา</th>
              <th class="px-4 py-4 text-center border-b">คาบ</th>
              <th class="px-4 py-4 text-center border-b">รูปแบบ</th>
              <th class="px-4 py-4 text-left border-b">สถานที่</th>
              <th class="px-4 py-4 text-center border-b">จัดการ</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="a in assignments" :key="a.id" :class="['hover:bg-blue-50 transition-colors', editingAssignmentId === a.id ? 'bg-yellow-50' : '']">
              <!-- ครู -->
              <td class="px-4 py-4">
                <div class="flex flex-wrap gap-1">
                  <span v-for="name in a.teacher_names" :key="name" class="inline-flex items-center gap-1 bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-[11px] font-bold border border-blue-100">
                    <Users class="w-3 h-3" /> {{ name }}
                  </span>
                </div>
              </td>
              <!-- ชั้นเรียน -->
              <td class="px-4 py-4">
                <div class="flex flex-wrap gap-1">
                  <span v-for="name in a.classroom_names" :key="name" class="inline-flex items-center gap-1 bg-purple-50 text-purple-700 px-2 py-0.5 rounded text-[11px] font-bold border border-purple-100">
                    <Home class="w-3 h-3" /> {{ name }}
                  </span>
                </div>
              </td>
              <!-- วิชา -->
              <td class="px-4 py-4">
                <p class="font-bold text-gray-900 leading-tight flex items-center gap-1">
                  {{ a.subject_name.split(' ')[0] }}
                  <span v-if="a.is_scout" title="วิชาลูกเสือ/เนตรนารี/ยุวกาชาด" class="inline-flex items-center gap-0.5 bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded text-[9px] font-black border border-yellow-300">
                    <Flag class="w-2.5 h-2.5" /> ลูกเสือ
                  </span>
                </p>
                <p class="text-[10px] text-gray-500 font-medium">{{ a.subject_name.split(' ').slice(1).join(' ') }}</p>
              </td>
              <!-- คาบรวม -->
              <td class="px-4 py-4 text-center font-bold text-blue-600">{{ a.total_periods }}</td>
              <!-- รูปแบบ -->
              <td class="px-4 py-4">
                <div class="flex justify-center gap-1">
                  <span v-for="(p, i) in a.period_split" :key="i" 
                    :class="p > 1 ? 'bg-orange-500 text-white border-orange-600' : 'bg-green-500 text-white border-green-600'"
                    class="px-2 py-0.5 rounded text-[10px] font-black border"
                  >
                    {{ p }}
                  </span>
                </div>
              </td>
              <!-- สถานที่ -->
              <td class="px-4 py-4 text-gray-600">
                <div v-if="(a.room_names && a.room_names.length) || a.include_home_room" class="flex flex-wrap gap-1">
                  <span v-for="name in a.room_names" :key="name" class="inline-flex items-center gap-1 bg-red-50 text-red-700 px-2 py-0.5 rounded text-[11px] font-bold border border-red-100">
                    <MapPin class="w-3 h-3" /> {{ name }}
                  </span>
                  <span v-if="a.include_home_room" class="inline-flex items-center gap-1 bg-purple-50 text-purple-700 px-2 py-0.5 rounded text-[11px] font-bold border border-purple-100">
                    <Home class="w-3 h-3" /> ห้องประจำ
                  </span>
                </div>
                <span v-else class="text-xs text-gray-400 italic">ห้องประจำของนักเรียนเอง</span>
              </td>
              <td class="px-4 py-4 text-center whitespace-nowrap">
                <button @click="startEditAssignment(a)" class="text-gray-400 hover:text-blue-600 transition mr-2">
                  <Pencil class="w-4 h-4" />
                </button>
                <button @click="deleteAssignment(a.id)" class="text-gray-400 hover:text-red-600 transition">
                  <Trash2 class="w-4 h-4" />
                </button>
              </td>
            </tr>
            <tr v-if="assignments.length === 0 && !loading">
              <td colspan="7" class="px-4 py-12 text-center text-gray-400 italic bg-gray-50 rounded-b-xl">
                ยังไม่มีการมอบหมายภาระงานสอน
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  </div>
</template>
