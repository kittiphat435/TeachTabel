<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { Plus, Users, Trash2, Calendar, Loader2, Search, Info, Pencil, X } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

interface Teacher { id: string; full_name: string; department: string }
interface Unavailability { id: string; teacher_id: string; teacher_name: string; day_of_week: number; period_number: number; reason: string }

const teachers = ref<Teacher[]>([])
const unavailabilities = ref<Unavailability[]>([])
const loading = ref(true)
const saving = ref(false)

// Form State
const selectedTeacherIds = ref<string[]>([])
const selectedDay = ref(1)
const selectedPeriod = ref(1)
const editingUnavId = ref<string | null>(null)

// สาเหตุ/ภาระงาน — เลือกได้หลายข้อ (checkbox) + พิมพ์เพิ่มเติมเองได้ถ้าไม่ตรงกับตัวเลือก
const reasonOptions = [
  'ลูกเสือ-เนตรนารี',
  'ยุวกาชาด',
  'ประชุมระดับ',
  'ประชุมวิชาการ',
  'ประชุมบุคคล',
  'ประชุมแผน/การเงิน',
  'ประชุมทั่วไป',
  'PLC',
  'ขายของ',
  'โฮมรูม',
]
const selectedReasons = ref<string[]>([])
const customReason = ref('')
const combinedReason = computed(() => {
  const parts = [...selectedReasons.value]
  if (customReason.value.trim()) parts.push(customReason.value.trim())
  return parts.join(', ')
})

const days = [
  { val: 1, name: 'จันทร์' },
  { val: 2, name: 'อังคาร' },
  { val: 3, name: 'พุธ' },
  { val: 4, name: 'พฤหัสบดี' },
  { val: 5, name: 'ศุกร์' }
]

// Search
const teacherSearch = ref('')
const filteredTeachers = computed(() => {
  if (!teacherSearch.value) return teachers.value
  return teachers.value.filter(t => t.full_name.includes(teacherSearch.value))
})

const fetchData = async () => {
  loading.value = true
  try {
    const [tRes, uRes] = await Promise.all([
      axios.get(`${API_BASE}/teachers/`),
      axios.get(`${API_BASE}/unavailabilities/`)
    ])
    teachers.value = tRes.data
    unavailabilities.value = uRes.data
  } catch (error) { console.error(error) }
  finally { loading.value = false }
}

onMounted(fetchData)

const resetForm = () => {
  selectedTeacherIds.value = []
  selectedDay.value = 1
  selectedPeriod.value = 1
  selectedReasons.value = []
  customReason.value = ''
  editingUnavId.value = null
}

const selectAllTeachers = () => {
  selectedTeacherIds.value = filteredTeachers.value.map(t => t.id)
}
const clearAllTeachers = () => {
  selectedTeacherIds.value = []
}

const addUnavailability = async () => {
  if (selectedTeacherIds.value.length === 0) {
    alert('กรุณาเลือกครูอย่างน้อย 1 ท่าน')
    return
  }
  if (!combinedReason.value) {
    alert('กรุณาเลือกสาเหตุ/ภาระงานอย่างน้อย 1 ข้อ หรือระบุเอง')
    return
  }

  saving.value = true
  try {
    if (editingUnavId.value) {
      if (selectedTeacherIds.value.length !== 1) {
        alert('ตอนแก้ไข กรุณาเลือกครูเพียง 1 ท่าน')
        saving.value = false
        return
      }
      await axios.put(`${API_BASE}/unavailabilities/${editingUnavId.value}`, {
        teacher_id: selectedTeacherIds.value[0],
        day_of_week: selectedDay.value,
        period_number: selectedPeriod.value,
        reason: combinedReason.value
      })
      alert('แก้ไขเวลาไม่ว่างสำเร็จ')
    } else {
      await axios.post(`${API_BASE}/unavailabilities/`, {
        teacher_ids: selectedTeacherIds.value,
        day_of_week: selectedDay.value,
        period_number: selectedPeriod.value,
        reason: combinedReason.value
      })
      alert('บันทึกเวลาไม่ว่างสำเร็จ')
    }
    await fetchData()
    resetForm()
  } catch (error) { alert('เกิดข้อผิดพลาดในการบันทึก') }
  finally { saving.value = false }
}

const startEditUnav = (u: Unavailability) => {
  editingUnavId.value = u.id
  selectedTeacherIds.value = [u.teacher_id]
  selectedDay.value = u.day_of_week
  selectedPeriod.value = u.period_number
  // แยกสาเหตุเดิม (คั่นด้วย comma) กลับเป็น checkbox ที่ตรงกับตัวเลือก ส่วนที่เหลือใส่ในช่อง "อื่นๆ"
  const parts = (u.reason || '').split(',').map(p => p.trim()).filter(Boolean)
  selectedReasons.value = parts.filter(p => reasonOptions.includes(p))
  customReason.value = parts.filter(p => !reasonOptions.includes(p)).join(', ')
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const cancelEditUnav = () => {
  resetForm()
}

const deleteUnav = async (id: string) => {
  if (!confirm('ยืนยันการลบ?')) return
  try {
    await axios.delete(`${API_BASE}/unavailabilities/${id}`)
    if (editingUnavId.value === id) resetForm()
    await fetchData()
  } catch (error) { alert('Error deleting') }
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-4 gap-6">
    <!-- Form -->
    <div class="xl:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit sticky top-6 text-gray-900">
      <h2 class="text-lg font-bold mb-4 flex items-center gap-2 text-blue-600">
        <Calendar class="w-5 h-5" /> {{ editingUnavId ? 'แก้ไขเวลาล็อก' : 'ล็อกเวลาปฏิบัติงานครู' }}
      </h2>
      <p v-if="editingUnavId" class="text-[10px] text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-md p-2 -mt-2 mb-3">กำลังแก้ไข — เลือกครูได้เพียง 1 ท่านตอนแก้ไข</p>

      <div class="space-y-4">
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">1. ระบุสาเหตุ / ภาระงาน (เลือกได้หลายข้อ)</label>
          <div class="grid grid-cols-2 gap-x-2 gap-y-1 mb-2 border rounded-md p-2 bg-gray-50">
            <label v-for="opt in reasonOptions" :key="opt" class="flex items-center gap-1.5 text-xs text-gray-700 cursor-pointer hover:bg-blue-50 p-1 rounded">
              <input type="checkbox" :value="opt" v-model="selectedReasons" class="rounded text-blue-600 w-3.5 h-3.5 shrink-0">
              <span class="truncate">{{ opt }}</span>
            </label>
          </div>
          <input v-model="customReason" placeholder="อื่นๆ (ระบุเพิ่มเติม ถ้ามี)" class="w-full border rounded-md p-2 text-sm">
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">2. วัน</label>
            <select v-model="selectedDay" class="w-full border rounded-md p-2 text-sm">
              <option v-for="d in days" :key="d.val" :value="d.val">{{ d.name }}</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">3. คาบที่</label>
            <input type="number" v-model="selectedPeriod" min="1" max="11" class="w-full border rounded-md p-2 text-sm text-center">
          </div>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="block text-xs font-bold text-gray-500 uppercase">4. เลือกครูที่ต้องล็อกเวลา</label>
            <div v-if="!editingUnavId" class="flex items-center gap-2">
              <button @click="selectAllTeachers" type="button" class="text-[10px] font-bold text-blue-600 hover:underline">เลือกครูทั้งหมด</button>
              <span class="text-gray-300">|</span>
              <button @click="clearAllTeachers" type="button" class="text-[10px] font-bold text-gray-400 hover:underline">ลบครูทั้งหมด</button>
            </div>
          </div>
          <div class="relative mb-2">
            <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
            <input v-model="teacherSearch" placeholder="ค้นหาครู..." class="w-full text-xs pl-7 py-2 border rounded-md bg-gray-50">
          </div>
          <div class="max-h-48 overflow-y-auto border rounded-md p-2 space-y-1 bg-white">
            <div v-for="t in filteredTeachers" :key="t.id" class="flex items-center hover:bg-blue-50 p-1 rounded">
              <input type="checkbox" :id="'unav-t-'+t.id" :value="t.id" v-model="selectedTeacherIds" class="rounded text-blue-600">
              <label :for="'unav-t-'+t.id" class="ml-2 text-xs text-gray-700 cursor-pointer flex-1">{{ t.full_name }}</label>
            </div>
          </div>
          <div class="mt-1 text-[10px] text-blue-600 font-bold" v-if="selectedTeacherIds.length > 0">
            เลือกแล้ว {{ selectedTeacherIds.length }} ท่าน
          </div>
        </div>

        <button
          @click="addUnavailability"
          :disabled="saving"
          class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 shadow-md"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          {{ editingUnavId ? 'บันทึกการแก้ไข' : 'บันทึกเวลาล็อก' }}
        </button>
        <button
          v-if="editingUnavId"
          @click="cancelEditUnav"
          class="w-full text-gray-500 text-sm font-bold py-2 rounded-lg hover:bg-gray-100 transition flex items-center justify-center gap-1"
        >
          <X class="w-3.5 h-3.5" /> ยกเลิกการแก้ไข
        </button>
      </div>
    </div>

    <!-- List -->
    <div class="xl:col-span-3 bg-white p-6 rounded-xl shadow-sm border border-gray-200 text-gray-900">
      <h2 class="text-xl font-bold text-gray-800 mb-6">รายการเวลาที่ครูไม่ว่าง (ล็อกคาบสอน)</h2>

      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-gray-600 font-bold text-gray-900">
            <tr>
              <th class="px-4 py-4 text-left border-b">วัน/คาบ</th>
              <th class="px-4 py-4 text-left border-b">ครูผู้สอน</th>
              <th class="px-4 py-4 text-left border-b">เหตุผล / ภาระงาน</th>
              <th class="px-4 py-4 text-center border-b">จัดการ</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="u in unavailabilities" :key="u.id" :class="['hover:bg-blue-50', editingUnavId === u.id ? 'bg-yellow-50' : '']">
              <td class="px-4 py-4 font-bold text-blue-700">
                {{ days.find(d => d.val === u.day_of_week)?.name }} คาบ {{ u.period_number }}
              </td>
              <td class="px-4 py-4 font-medium">{{ u.teacher_name }}</td>
              <td class="px-4 py-4 text-gray-500 italic">{{ u.reason }}</td>
              <td class="px-4 py-4 text-center text-gray-900 whitespace-nowrap">
                <button @click="startEditUnav(u)" class="text-gray-400 hover:text-blue-600 transition mr-2">
                  <Pencil class="w-4 h-4" />
                </button>
                <button @click="deleteUnav(u.id)" class="text-gray-400 hover:text-red-600 transition">
                  <Trash2 class="w-4 h-4" />
                </button>
              </td>
            </tr>
            <tr v-if="unavailabilities.length === 0 && !loading">
              <td colspan="4" class="px-4 py-12 text-center text-gray-400 italic">ยังไม่มีข้อมูลเวลาล็อกของครู</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
