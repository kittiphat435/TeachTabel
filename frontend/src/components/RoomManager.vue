<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { Home, School, Plus, BookOpen, Users, Upload, Loader2, AlertCircle } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

interface Classroom { id?: string; grade_level: string; room_name: string; lunch_period?: number }
interface Room { id?: string; room_name: string; room_type: string }
interface Subject { id?: string; subject_code: string; subject_name: string }
interface Teacher { id?: string; full_name: string; department: string }

const classrooms = ref<Classroom[]>([])
const rooms = ref<Room[]>([])
const subjects = ref<Subject[]>([])
const teachers = ref<Teacher[]>([])

const loading = ref(true)
const importing = ref(false)

// Form states
const newClassroom = ref<Classroom>({ grade_level: '', room_name: '', lunch_period: 4 })
const newRoom = ref<Room>({ room_name: '', room_type: 'ห้องเรียนประจำ' })
const newSubject = ref<Subject>({ subject_code: '', subject_name: '' })
const newTeacher = ref<Teacher>({ full_name: '', department: '' })

const fetchData = async () => {
  loading.value = true
  try {
    const [cRes, rRes, sRes, tRes] = await Promise.all([
      axios.get(`${API_BASE}/classrooms/`),
      axios.get(`${API_BASE}/rooms/`),
      axios.get(`${API_BASE}/subjects/`),
      axios.get(`${API_BASE}/teachers/`)
    ])
    classrooms.value = cRes.data
    rooms.value = rRes.data
    subjects.value = sRes.data
    teachers.value = tRes.data
  } catch (error) {
    console.error('Error fetching data:', error)
  } finally {
    loading.value = false
  }
}

// Manual Add Functions
const addClassroom = async () => {
  if (!newClassroom.value.grade_level || !newClassroom.value.room_name) return
  try {
    await axios.post(`${API_BASE}/classrooms/manual`, newClassroom.value)
    newClassroom.value = { grade_level: '', room_name: '', lunch_period: 4 }
    fetchData()
  } catch (error) { alert('บันทึกไม่สำเร็จ') }
}

const addRoom = async () => {
  if (!newRoom.value.room_name) return
  try {
    await axios.post(`${API_BASE}/rooms/manual`, newRoom.value)
    newRoom.value = { room_name: '', room_type: 'ห้องเรียนประจำ' }
    fetchData()
  } catch (error) { alert('บันทึกไม่สำเร็จ') }
}

const addSubject = async () => {
  if (!newSubject.value.subject_code || !newSubject.value.subject_name) return
  try {
    await axios.post(`${API_BASE}/subjects/manual`, newSubject.value)
    newSubject.value = { subject_code: '', subject_name: '' }
    fetchData()
  } catch (error) { alert('บันทึกไม่สำเร็จ') }
}

const addTeacher = async () => {
  if (!newTeacher.value.full_name || !newTeacher.value.department) {
    alert('กรุณากรอกชื่อและกลุ่มสาระ')
    return
  }
  try {
    await axios.post(`${API_BASE}/teachers/manual`, newTeacher.value)
    newTeacher.value = { full_name: '', department: '' }
    fetchData()
  } catch (error) { alert('บันทึกไม่สำเร็จ') }
}

const handleFileUpload = async (event: any, type: string) => {
  const file = event.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  importing.value = true
  try {
    await axios.post(`${API_BASE}/import/${type}/`, formData)
    alert('นำเข้าข้อมูลสำเร็จ')
    fetchData()
  } catch (error) {
    alert('เกิดข้อผิดพลาดในการนำเข้าไฟล์')
  } finally {
    importing.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="space-y-8">
    <div class="flex items-center gap-2 mb-2">
      <School class="w-8 h-8 text-blue-600" />
      <h2 class="text-2xl font-bold text-gray-800">จัดการข้อมูลพื้นฐาน (Master Data)</h2>
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-400">
      <Loader2 class="w-10 h-10 animate-spin mx-auto mb-2" />
      กำลังโหลดข้อมูลพื้นฐาน...
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-8">
      
      <!-- Section: Subjects (วิชา) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-orange-600">
          <BookOpen class="w-5 h-5" /> 1. รายชื่อวิชา (Subjects)
        </h3>
        <div class="grid grid-cols-2 gap-2 mb-2">
          <input v-model="newSubject.subject_code" placeholder="รหัสวิชา (ว21101)" class="border p-2 rounded text-sm">
          <input v-model="newSubject.subject_name" placeholder="ชื่อวิชา (วิทยาศาสตร์)" class="border p-2 rounded text-sm">
        </div>
        <button @click="addSubject" class="w-full bg-orange-500 text-white rounded p-2 text-sm font-bold hover:bg-orange-600 mb-4">เพิ่มวิชา</button>
        
        <div class="flex items-center gap-2 mb-4">
          <label class="text-[10px] font-bold text-gray-400 uppercase">Excel:</label>
          <input type="file" @change="e => handleFileUpload(e, 'subjects')" class="text-xs text-gray-500">
        </div>

        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-left border-b">รหัส</th>
                <th class="p-2 text-left border-b">ชื่อวิชา</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in subjects" :key="s.id" class="hover:bg-gray-50">
                <td class="p-2 border-b text-xs">{{ s.subject_code }}</td>
                <td class="p-2 border-b font-medium text-xs">{{ s.subject_name }}</td>
              </tr>
              <tr v-if="subjects.length === 0"><td colspan="2" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section: Teachers (ครู) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-blue-600">
          <Users class="w-5 h-5" /> 2. รายชื่อบุคลากร (Teachers)
        </h3>
        <div class="grid grid-cols-2 gap-2 mb-2">
          <input v-model="newTeacher.full_name" placeholder="ชื่อ-นามสกุล" class="border p-2 rounded text-sm">
          <input v-model="newTeacher.department" placeholder="กลุ่มสาระ" class="border p-2 rounded text-sm">
        </div>
        <button @click="addTeacher" class="w-full bg-blue-600 text-white rounded p-2 text-sm font-bold hover:bg-blue-700 mb-4">เพิ่มครู</button>
        
        <div class="flex items-center gap-2 mb-4">
          <label class="text-[10px] font-bold text-gray-400 uppercase">Excel:</label>
          <input type="file" @change="e => handleFileUpload(e, 'teachers')" class="text-xs text-gray-500">
        </div>
        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-left border-b">ชื่อ-นามสกุล</th>
                <th class="p-2 text-left border-b">กลุ่มสาระ</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="t in teachers" :key="t.id" class="hover:bg-gray-50">
                <td class="p-2 border-b font-medium text-xs">{{ t.full_name }}</td>
                <td class="p-2 border-b text-gray-500 text-xs">{{ t.department || '-' }}</td>
              </tr>
              <tr v-if="teachers.length === 0"><td colspan="2" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section: Classrooms (ชั้นเรียน) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-purple-600">
          <School class="w-5 h-5" /> 3. รายชื่อชั้นเรียน (Classrooms)
        </h3>
        <div class="grid grid-cols-3 gap-2 mb-4">
          <input v-model="newClassroom.grade_level" placeholder="ระดับชั้น" class="border p-2 rounded text-sm">
          <input v-model="newClassroom.room_name" placeholder="ชื่อห้อง" class="border p-2 rounded text-sm">
          <button @click="addClassroom" class="bg-purple-600 text-white rounded text-sm font-bold hover:bg-purple-700 text-xs">เพิ่มชั้นเรียน</button>
        </div>
        <div class="flex items-center gap-2 mb-4">
          <label class="text-[10px] font-bold text-gray-400 uppercase">Excel:</label>
          <input type="file" @change="e => handleFileUpload(e, 'classrooms')" class="text-xs text-gray-500">
        </div>
        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-left border-b">ระดับ</th>
                <th class="p-2 text-left border-b">ห้อง</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in classrooms" :key="c.id" class="hover:bg-gray-50">
                <td class="p-2 border-b text-xs">{{ c.grade_level }}</td>
                <td class="p-2 border-b font-medium text-xs">{{ c.room_name }}</td>
              </tr>
              <tr v-if="classrooms.length === 0"><td colspan="2" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section: Rooms (สถานที่) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-green-600">
          <Home class="w-5 h-5" /> 4. สถานที่ / ห้องเรียน (Rooms)
        </h3>
        <div class="grid grid-cols-3 gap-2 mb-4">
          <input v-model="newRoom.room_name" placeholder="ชื่อสถานที่" class="border p-2 rounded text-sm col-span-2">
          <button @click="addRoom" class="bg-green-600 text-white rounded text-sm font-bold hover:bg-green-700">เพิ่มสถานที่</button>
        </div>
        <div class="flex items-center gap-2 mb-4">
          <label class="text-[10px] font-bold text-gray-400 uppercase">Excel:</label>
          <input type="file" @change="e => handleFileUpload(e, 'rooms')" class="text-xs text-gray-500">
        </div>
        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-left border-b">ชื่อสถานที่</th>
                <th class="p-2 text-left border-b text-center">ประเภท</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in rooms" :key="r.id" class="hover:bg-gray-50">
                <td class="p-2 border-b font-medium text-xs">{{ r.room_name }}</td>
                <td class="p-2 border-b text-gray-500 text-xs text-center">{{ r.room_type }}</td>
              </tr>
              <tr v-if="rooms.length === 0"><td colspan="2" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>
