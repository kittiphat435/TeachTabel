<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { Plus, Users, Home, Clock, Loader2, Trash2, Calendar, MapPin } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

interface Classroom { id: string; grade_level: string; room_name: string }
interface Teacher { id: string; full_name: string }
interface Room { id: string; room_name: string }
interface FixedEvent { id: string; event_name: string; day_of_week: number; period_number: number; classroom_names: string[]; teacher_names: string[]; room_name: string }

const classrooms = ref<Classroom[]>([])
const teachers = ref<Teacher[]>([])
const rooms = ref<Room[]>([])
const events = ref<FixedEvent[]>([])

const loading = ref(true)
const saving = ref(false)

// Form State
const eventName = ref('')
const selectedDay = ref(1)
const selectedPeriod = ref(1)
const selectedClassrooms = ref<string[]>([])
const selectedTeachers = ref<string[]>([])
const selectedRoom = ref('')

const days = [
  { val: 1, name: 'จันทร์' },
  { val: 2, name: 'อังคาร' },
  { val: 3, name: 'พุธ' },
  { val: 4, name: 'พฤหัสบดี' },
  { val: 5, name: 'ศุกร์' }
]

const fetchData = async () => {
  loading.value = true
  try {
    const [cRes, tRes, rRes, eRes] = await Promise.all([
      axios.get(`${API_BASE}/classrooms/`),
      axios.get(`${API_BASE}/teachers/`),
      axios.get(`${API_BASE}/rooms/`),
      axios.get(`${API_BASE}/fixed-events/`)
    ])
    classrooms.value = cRes.data
    teachers.value = tRes.data
    rooms.value = rRes.data
    events.value = eRes.data
  } catch (error) { console.error(error) }
  finally { loading.value = false }
}

onMounted(fetchData)

const addEvent = async () => {
  if (!eventName.value || selectedClassrooms.value.length === 0) {
    alert('กรุณาระบุชื่อกิจกรรมและเลือกอย่างน้อย 1 ชั้นเรียน')
    return
  }

  saving.value = true
  try {
    await axios.post(`${API_BASE}/fixed-events/`, {
      event_name: eventName.value,
      day_of_week: selectedDay.value,
      period_number: selectedPeriod.value,
      classroom_ids: selectedClassrooms.value,
      teacher_ids: selectedTeachers.value,
      room_id: selectedRoom.value || null
    })
    alert('บันทึกกิจกรรมสำเร็จ')
    await fetchData()
    // Reset
    eventName.value = ''
    selectedClassrooms.value = []
    selectedTeachers.value = []
  } catch (error) { alert('Error saving') }
  finally { saving.value = false }
}

const deleteEvent = async (id: string) => {
  if (!confirm('ยืนยันการลบกิจกรรมนี้?')) return
  try {
    await axios.delete(`${API_BASE}/fixed-events/${id}`)
    await fetchData()
  } catch (error) { alert('Error deleting') }
}
</script>

<template>
  <div class="grid grid-cols-1 xl:grid-cols-4 gap-6">
    <!-- Form -->
    <div class="xl:col-span-1 bg-white p-6 rounded-xl shadow-sm border border-gray-200 h-fit sticky top-6">
      <h2 class="text-lg font-bold mb-4 flex items-center gap-2 text-red-600">
        <Calendar class="w-5 h-5" /> เพิ่มภาระงานนักเรียน (กิจกรรมบังคับ)
      </h2>

      <div class="space-y-4">
        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">1. ชื่อกิจกรรม / ภาระงาน</label>
          <input v-model="eventName" placeholder="เช่น ลูกเสือ, ชุมนุม, พักเที่ยง" class="w-full border rounded-md p-2 text-sm">
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
            <input type="number" v-model="selectedPeriod" min="1" max="8" class="w-full border rounded-md p-2 text-sm">
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">4. ชั้นเรียนที่ต้องร่วม</label>
          <div class="max-h-32 overflow-y-auto border rounded-md p-2 space-y-1 bg-gray-50">
            <div v-for="c in classrooms" :key="c.id" class="flex items-center">
              <input type="checkbox" :id="'fe-c-'+c.id" :value="c.id" v-model="selectedClassrooms" class="rounded text-red-600">
              <label :for="'fe-c-'+c.id" class="ml-2 text-xs text-gray-700">{{ c.grade_level }}/{{ c.room_name }}</label>
            </div>
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">5. ครูที่เกี่ยวข้อง (ถ้ามี)</label>
          <div class="max-h-32 overflow-y-auto border rounded-md p-2 space-y-1 bg-gray-50">
            <div v-for="t in teachers" :key="t.id" class="flex items-center">
              <input type="checkbox" :id="'fe-t-'+t.id" :value="t.id" v-model="selectedTeachers" class="rounded text-red-600">
              <label :for="'fe-t-'+t.id" class="ml-2 text-xs text-gray-700">{{ t.full_name }}</label>
            </div>
          </div>
        </div>

        <button 
          @click="addEvent" 
          :disabled="saving"
          class="w-full bg-red-600 text-white font-bold py-3 rounded-lg hover:bg-red-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          บันทึกกิจกรรมบังคับ
        </button>
      </div>
    </div>

    <!-- List -->
    <div class="xl:col-span-3 bg-white p-6 rounded-xl shadow-sm border border-gray-200">
      <h2 class="text-xl font-bold text-gray-800 mb-6">รายการกิจกรรมบังคับ / เวลาล็อกนักเรียน</h2>

      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead class="bg-gray-50 text-gray-600 font-bold">
            <tr>
              <th class="px-4 py-4 text-left border-b">วัน/คาบ</th>
              <th class="px-4 py-4 text-left border-b">ชื่อกิจกรรม</th>
              <th class="px-4 py-4 text-left border-b">ชั้นเรียน</th>
              <th class="px-4 py-4 text-left border-b">ครูที่เกี่ยวข้อง</th>
              <th class="px-4 py-4 text-center border-b">จัดการ</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="e in events" :key="e.id" class="hover:bg-red-50">
              <td class="px-4 py-4 font-bold text-red-700">
                {{ days.find(d => d.val === e.day_of_week)?.name }} คาบ {{ e.period_number }}
              </td>
              <td class="px-4 py-4 font-bold text-gray-900">{{ e.event_name }}</td>
              <td class="px-4 py-4">
                <div class="flex flex-wrap gap-1">
                  <span v-for="c in e.classroom_names" :key="c" class="bg-purple-100 text-purple-700 px-2 py-0.5 rounded text-[10px] font-bold border border-purple-200">
                    {{ c }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-4">
                <div class="flex flex-wrap gap-1">
                  <span v-for="t in e.teacher_names" :key="t" class="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-[10px] font-bold border border-blue-200">
                    {{ t }}
                  </span>
                </div>
              </td>
              <td class="px-4 py-4 text-center">
                <button @click="deleteEvent(e.id)" class="text-gray-400 hover:text-red-600 transition">
                  <Trash2 class="w-4 h-4" />
                </button>
              </td>
            </tr>
            <tr v-if="events.length === 0 && !loading">
              <td colspan="5" class="px-4 py-12 text-center text-gray-400 italic">ยังไม่มีกิจกรรมบังคับ</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
