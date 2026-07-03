<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import axios from 'axios'
import { Plus, Users, BookOpen, Home, Clock, Loader2, MapPin, Search, UserPlus } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

interface Teacher { id: string; full_name: string; department: string }
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

// Form State
const selectedSubject = ref('')
const selectedTeachers = ref<string[]>([])
const selectedClassrooms = ref<string[]>([])
const selectedRoom = ref('')
const totalPeriods = ref(2)
const selectedSplitPattern = ref<number[]>([2])

// Search States
const teacherSearch = ref('')
const filteredTeachers = computed(() => {
  if (!teacherSearch.value) return teachers.value
  return teachers.value.filter(t => t.full_name.includes(teacherSearch.value))
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

onMounted(fetchData)

const addAssignment = async () => {
  if (!selectedSubject.value || selectedTeachers.value.length === 0 || selectedClassrooms.value.length === 0) {
    alert('กรุณากรอกข้อมูลให้ครบถ้วน')
    return
  }

  saving.value = true
  try {
    const payload = {
      subject_id: selectedSubject.value,
      teacher_ids: selectedTeachers.value,
      classroom_ids: selectedClassrooms.value,
      room_id: selectedRoom.value || null,
      total_periods: totalPeriods.value,
      period_split: selectedSplitPattern.value
    }

    await axios.post(`${API_BASE}/assignments/`, payload)
    alert('บันทึกภาระงานสำเร็จ')
    await fetchData()
    
    // Reset
    selectedTeachers.value = []
    selectedClassrooms.value = []
    selectedSubject.value = ''
    selectedRoom.value = ''
  } catch (error) {
    alert('เกิดข้อผิดพลาดในการบันทึก')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-4 gap-6">
    <!-- Left: Entry Form -->
    <div class="xl:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit sticky top-6">
      <h2 class="text-lg font-bold mb-4 flex items-center gap-2 text-blue-600">
        <Plus class="w-5 h-5" /> มอบหมายภาระงาน
      </h2>
      
      <div v-if="loading" class="text-center py-4 text-gray-400">กำลังโหลด...</div>
      
      <div v-else class="space-y-4">
        <!-- Subject -->
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase tracking-tight">1. เลือกวิชา</label>
          <select v-model="selectedSubject" class="w-full border border-gray-300 rounded-md p-2 text-sm focus:ring-blue-500">
            <option value="">-- เลือกวิชา --</option>
            <option v-for="s in subjects" :key="s.id" :value="s.id">{{ s.subject_code }} - {{ s.subject_name }}</option>
          </select>
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
              <label :for="'t-'+t.id" class="ml-2 text-xs text-gray-700 cursor-pointer flex-1">{{ t.full_name }}</label>
              <span class="text-[9px] text-gray-400 font-medium uppercase">{{ t.department }}</span>
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
          <div class="max-h-32 overflow-y-auto border border-gray-200 rounded-md p-2 space-y-1 bg-gray-50 text-sm">
            <div v-for="c in classrooms" :key="c.id" class="flex items-center">
              <input type="checkbox" :id="'c-'+c.id" :value="c.id" v-model="selectedClassrooms" class="rounded text-blue-600 w-4 h-4">
              <label :for="'c-'+c.id" class="ml-2 text-xs text-gray-600 cursor-pointer">{{ c.grade_level }}/{{ c.room_name }}</label>
            </div>
          </div>
        </div>

        <!-- Room -->
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase tracking-tight">4. สถานที่เรียน (ถ้ามี)</label>
          <select v-model="selectedRoom" class="w-full border border-gray-300 rounded-md p-2 text-sm">
            <option value="">-- ตามความเหมาะสม (สุ่ม) --</option>
            <option v-for="r in rooms" :key="r.id" :value="r.id">{{ r.room_name }}</option>
          </select>
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
          @click="addAssignment" 
          :disabled="saving"
          class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 mt-2 shadow-md"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          บันทึกภาระงาน
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
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="a in assignments" :key="a.id" class="hover:bg-blue-50 transition-colors">
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
                <p class="font-bold text-gray-900 leading-tight">{{ a.subject_name.split(' ')[0] }}</p>
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
                <div class="flex items-center gap-1 font-medium">
                  <MapPin class="w-3 h-3 text-red-400" /> {{ a.room_name }}
                </div>
              </td>
            </tr>
            <tr v-if="assignments.length === 0 && !loading">
              <td colspan="6" class="px-4 py-12 text-center text-gray-400 italic bg-gray-50 rounded-b-xl">
                ยังไม่มีการมอบหมายภาระงานสอน
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
