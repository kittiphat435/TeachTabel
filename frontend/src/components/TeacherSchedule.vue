<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import axios from 'axios'
import { UserCog, Loader2, MapPin, Home } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

interface Teacher { id: string; full_name: string; department: string; teacher_code?: string | null }
interface ScheduleEntry {
  id: string
  day_of_week: number
  period_number: number
  subject_name: string
  classroom_ids: string[]
  classroom_names: string[]
  room_name: string | null
  note?: string
}

const teachers = ref<Teacher[]>([])
const selectedTeacherId = ref('')
const entries = ref<ScheduleEntry[]>([])
const loading = ref(true)
const loadingSchedule = ref(false)

const days = [
  { val: 1, name: 'จันทร์' },
  { val: 2, name: 'อังคาร' },
  { val: 3, name: 'พุธ' },
  { val: 4, name: 'พฤหัสบดี' },
  { val: 5, name: 'ศุกร์' },
]
const periods = [1, 2, 3, 4, 5, 6, 7, 8]

const fetchTeachers = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/teachers/`)
    teachers.value = res.data
    if (teachers.value.length > 0 && !selectedTeacherId.value) {
      selectedTeacherId.value = teachers.value[0].id
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// หมายเหตุ: ตารางนี้เป็นมุมมองของ "ตัวครูเอง" โดยเจตนา จึงไม่แสดงชื่อครูท่านอื่นที่สอนร่วมในคาบเดียวกัน
// (เห็นแค่ว่าไปสอนห้องอะไร วิชาอะไร สถานที่ไหน) ต่างจากตารางฝั่งห้องเรียนที่จะเห็นชื่อครูทุกคนที่สอนร่วม
const fetchSchedule = async () => {
  if (!selectedTeacherId.value) { entries.value = []; return }
  loadingSchedule.value = true
  try {
    const res = await axios.get(`${API_BASE}/schedule/`, { params: { teacher_id: selectedTeacherId.value } })
    entries.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loadingSchedule.value = false
  }
}

onMounted(async () => {
  await fetchTeachers()
  await fetchSchedule()
})

watch(selectedTeacherId, fetchSchedule)

const entryAt = (day: number, period: number) =>
  entries.value.find(e => e.day_of_week === day && e.period_number === period)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-2">
      <UserCog class="w-7 h-7 text-blue-600" />
      <h2 class="text-2xl font-bold text-gray-800">ตารางสอนรายบุคคล (มุมมองครู)</h2>
    </div>

    <p class="text-xs text-gray-500 bg-blue-50 border border-blue-100 rounded-lg p-3">
      แสดงเฉพาะห้องเรียน/วิชา/สถานที่ที่ครูท่านนี้ไปสอน — ไม่แสดงชื่อครูท่านอื่นที่อาจสอนร่วมในคาบเดียวกัน
    </p>

    <div v-if="loading" class="text-center py-12 text-gray-400">
      <Loader2 class="w-10 h-10 animate-spin mx-auto mb-2" /> กำลังโหลดข้อมูล...
    </div>

    <div v-else class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
      <div class="mb-4 max-w-xs">
        <label class="block text-xs font-bold text-gray-500 mb-1 uppercase">เลือกครู</label>
        <select v-model="selectedTeacherId" class="w-full border rounded-md p-2 text-sm">
          <option v-for="t in teachers" :key="t.id" :value="t.id">{{ t.teacher_code ? `[${t.teacher_code}] ` : '' }}{{ t.full_name }} ({{ t.department }})</option>
        </select>
      </div>

      <div class="flex items-center justify-between mb-2">
        <span class="text-xs text-gray-400"></span>
        <Loader2 v-if="loadingSchedule" class="w-4 h-4 animate-spin text-blue-500" />
      </div>

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
                :class="['p-2 border align-top min-w-[130px]', entryAt(d.val, p) ? 'bg-blue-50' : '']"
              >
                <template v-if="entryAt(d.val, p)">
                  <p class="font-bold text-blue-800 leading-tight">{{ entryAt(d.val, p)!.subject_name }}</p>
                  <p v-if="entryAt(d.val, p)!.classroom_names.length" class="text-[10px] text-gray-600 flex items-center gap-1 mt-0.5">
                    <Home class="w-3 h-3 shrink-0" /> {{ entryAt(d.val, p)!.classroom_names.join(', ') }}
                  </p>
                  <p v-else class="text-[10px] text-gray-500 italic mt-0.5">เดินไปหานักเรียนเอง</p>
                  <p v-if="entryAt(d.val, p)!.room_name" class="text-[10px] text-gray-500 flex items-center gap-1">
                    <MapPin class="w-3 h-3 shrink-0" /> {{ entryAt(d.val, p)!.room_name }}
                  </p>
                </template>
                <span v-else class="text-gray-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
