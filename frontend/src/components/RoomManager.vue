<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { Home, School, Plus, BookOpen, Users, Upload, Loader2, AlertCircle, Trash2, Pencil, Search, Check, X } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

interface Classroom { id?: string; grade_level: string; room_name: string; lunch_period?: number }
interface Room { id?: string; room_name: string; room_type: string; home_classroom_id?: string | null; home_classroom_label?: string | null }
interface Subject { id?: string; subject_code: string; subject_name: string }
interface Teacher { id?: string; full_name: string; department: string; teacher_code?: string | null }

const classrooms = ref<Classroom[]>([])
const rooms = ref<Room[]>([])
const subjects = ref<Subject[]>([])
const teachers = ref<Teacher[]>([])

const loading = ref(true)
const uploadingType = ref('')
const uploadProgress = ref(0)
const clearingType = ref('')

type MasterType = 'subjects' | 'teachers' | 'classrooms' | 'rooms'

const typeLabels: Record<MasterType, string> = {
  subjects: 'วิชา',
  teachers: 'ครู',
  classrooms: 'ชั้นเรียน',
  rooms: 'สถานที่/ห้อง',
}

// Form states
const newClassroom = ref<Classroom>({ grade_level: '', room_name: '', lunch_period: 4 })
const newRoom = ref<Room>({ room_name: '', room_type: 'ห้องปฏิบัติการ', home_classroom_id: '' })

// ป้ายบอกว่าห้องเรียนไหนถูกผูกเป็นห้องประจำชั้นไปแล้ว (กันเลือกซ้ำโดยไม่ตั้งใจ)
const classroomOptionsForHomeRoom = computed(() =>
  classrooms.value.map(c => {
    const takenBy = rooms.value.find(r => r.home_classroom_id === c.id && r.id !== (editingType.value === 'rooms' ? editingId.value : undefined))
    return {
      id: c.id as string,
      label: `${c.grade_level}/${c.room_name}` + (takenBy ? ` (มีห้อง ${takenBy.room_name} ผูกไว้แล้ว)` : ''),
    }
  })
)
const newSubject = ref<Subject>({ subject_code: '', subject_name: '' })
const newTeacher = ref<Teacher>({ full_name: '', department: '', teacher_code: '' })

// ค้นหาในตาราง
const searchSubjects = ref('')
const filteredSubjects = computed(() => {
  const q = searchSubjects.value.trim()
  if (!q) return subjects.value
  return subjects.value.filter(s => s.subject_code.includes(q) || s.subject_name.includes(q))
})

const searchTeachers = ref('')
const filteredTeachersTable = computed(() => {
  const q = searchTeachers.value.trim()
  if (!q) return teachers.value
  return teachers.value.filter(t => t.full_name.includes(q) || (t.teacher_code || '').includes(q) || (t.department || '').includes(q))
})

const searchClassrooms = ref('')
const filteredClassrooms = computed(() => {
  const q = searchClassrooms.value.trim()
  if (!q) return classrooms.value
  return classrooms.value.filter(c => c.grade_level.includes(q) || c.room_name.includes(q) || `${c.grade_level}/${c.room_name}`.includes(q))
})

const searchRooms = ref('')
const filteredRooms = computed(() => {
  const q = searchRooms.value.trim()
  if (!q) return rooms.value
  return rooms.value.filter(r => r.room_name.includes(q) || r.room_type.includes(q))
})

// แก้ไขข้อมูล — แก้ได้ทีละแถวทั่วทั้งหน้า
const editingType = ref<MasterType | ''>('')
const editingId = ref<string | null>(null)
const editDraft = ref<any>({})

const startEdit = (type: MasterType, item: any) => {
  editingType.value = type
  editingId.value = item.id
  editDraft.value = { ...item }
  // กันค่า room_type เก่าที่พิมพ์มาไม่ตรงเป๊ะ (เช่น "ห้องประจำ" แทน "ห้องประจำชั้น")
  // ให้กลายเป็นค่ามาตรฐานตอนเริ่มแก้ไข ไม่งั้น dropdown จะว่างและช่องเลือกห้องเรียนจะไม่โผล่มา
  if (type === 'rooms') {
    editDraft.value.room_type = (item.room_type || '').includes('ประจำ') ? 'ห้องประจำชั้น' : 'ห้องปฏิบัติการ'
  }
}

const cancelEdit = () => {
  editingType.value = ''
  editingId.value = null
  editDraft.value = {}
}

const saveEdit = async () => {
  if (!editingId.value || !editingType.value) return
  const payload = { ...editDraft.value }
  if (editingType.value === 'rooms') {
    if (payload.room_type === 'ห้องประจำชั้น' && !payload.home_classroom_id) {
      alert('กรุณาเลือกว่าห้องนี้เป็นห้องประจำของชั้นเรียนไหน (หรือเปลี่ยนประเภทเป็น "ห้องปฏิบัติการ" ถ้ายังไม่ต้องการผูก)')
      return
    }
    // ถ้าไม่ใช่ห้องประจำชั้นแล้ว ให้เคลียร์การผูกห้องเรียนทิ้งเสมอ (กันค่าเก่าตกค้าง)
    if (payload.room_type !== 'ห้องประจำชั้น') {
      payload.home_classroom_id = null
    }
  }
  try {
    await axios.put(`${API_BASE}/${editingType.value}/${editingId.value}`, payload)
    cancelEdit()
    fetchData()
  } catch (error: any) {
    alert(error?.response?.status === 403 ? 'เฉพาะผู้ดูแลระบบเท่านั้น' : 'บันทึกไม่สำเร็จ')
  }
}

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
  if (newRoom.value.room_type === 'ห้องประจำชั้น' && !newRoom.value.home_classroom_id) {
    alert('กรุณาเลือกว่าห้องนี้เป็นห้องประจำของชั้นเรียนไหน (หรือเปลี่ยนประเภทเป็น "ห้องปฏิบัติการ" ถ้ายังไม่ต้องการผูก)')
    return
  }
  try {
    await axios.post(`${API_BASE}/rooms/manual`, {
      room_name: newRoom.value.room_name,
      room_type: newRoom.value.room_type,
      home_classroom_id: newRoom.value.room_type === 'ห้องประจำชั้น' ? (newRoom.value.home_classroom_id || null) : null,
    })
    newRoom.value = { room_name: '', room_type: 'ห้องปฏิบัติการ', home_classroom_id: '' }
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
    newTeacher.value = { full_name: '', department: '', teacher_code: '' }
    fetchData()
  } catch (error) { alert('บันทึกไม่สำเร็จ') }
}

const handleFileUpload = async (event: any, type: string) => {
  const file = event.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  uploadingType.value = type
  uploadProgress.value = 0
  try {
    const res = await axios.post(`${API_BASE}/import/${type}/`, formData, {
      onUploadProgress: (evt) => {
        if (evt.total) uploadProgress.value = Math.round((evt.loaded / evt.total) * 100)
      },
    })
    uploadProgress.value = 100
    const detected = res.data?.detected_columns as Record<string, string | null> | undefined
    let msg = `นำเข้าข้อมูลสำเร็จ ${res.data?.imported_count ?? ''} รายการ`
    if (detected) {
      const missing = Object.entries(detected).filter(([, v]) => !v).map(([k]) => k)
      const found = Object.entries(detected).filter(([, v]) => v).map(([k, v]) => `${k} ← "${v}"`)
      msg += `\n\nคอลัมน์ที่พบในไฟล์: ${found.join(', ') || '(ไม่พบเลย)'}`
      if (missing.length) {
        msg += `\n⚠️ ไม่พบคอลัมน์: ${missing.join(', ')} (แถวที่ขาดข้อมูลจำเป็นจะถูกข้ามไป)`
      }
    }
    const unmatched = res.data?.unmatched_links as string[] | undefined
    if (unmatched && unmatched.length) {
      msg += `\n\n⚠️ ผูกห้องประจำชั้นไม่สำเร็จ (ไม่พบชั้นเรียนตรงกัน): ${unmatched.join(', ')}`
    }
    alert(msg)
    fetchData()
  } catch (error) {
    alert('เกิดข้อผิดพลาดในการนำเข้าไฟล์')
  } finally {
    setTimeout(() => { uploadingType.value = ''; uploadProgress.value = 0 }, 500)
    event.target.value = ''
  }
}

// ลบทีละรายการ — อัปโหลด CSV/Excel เป็นการเพิ่มต่อท้ายเสมอ ไม่ทับของเดิม จึงต้องลบเองถ้าไม่ต้องการรายการเก่า
const deleteItem = async (type: MasterType, id?: string) => {
  if (!id) return
  if (!confirm(`ลบรายการนี้ออกจาก${typeLabels[type]}?`)) return
  try {
    await axios.delete(`${API_BASE}/${type}/${id}`)
    fetchData()
  } catch (error: any) {
    alert(error?.response?.status === 403 ? 'เฉพาะผู้ดูแลระบบเท่านั้น' : 'ลบไม่สำเร็จ')
  }
}

// ล้างข้อมูลทั้งหมดในประเภทนี้ (เฉพาะปี/เทอมที่กำลังใช้งาน) ก่อนอัปโหลดไฟล์ใหม่ทับ
const clearAll = async (type: MasterType) => {
  if (!confirm(`ล้างข้อมูล${typeLabels[type]}ทั้งหมด (เฉพาะปีการศึกษาที่เลือกอยู่)? การกระทำนี้ไม่สามารถย้อนกลับได้`)) return
  clearingType.value = type
  try {
    const res = await axios.delete(`${API_BASE}/${type}/`)
    alert(`ล้างข้อมูลสำเร็จ (${res.data.deleted_count} รายการ)`)
    fetchData()
  } catch (error: any) {
    if (error?.response?.status === 400) {
      alert(error.response.data?.detail || 'กรุณาเลือกปีการศึกษาก่อน')
    } else if (error?.response?.status === 403) {
      alert('เฉพาะผู้ดูแลระบบเท่านั้น')
    } else {
      alert('ล้างข้อมูลไม่สำเร็จ')
    }
  } finally {
    clearingType.value = ''
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
          <span class="text-xs font-bold px-2 py-0.5 bg-orange-50 text-orange-500 rounded-full">ทั้งหมด {{ subjects.length }}</span>
        </h3>
        <div class="grid grid-cols-2 gap-2 mb-2">
          <input v-model="newSubject.subject_code" placeholder="รหัสวิชา (ว21101)" class="border p-2 rounded text-sm">
          <input v-model="newSubject.subject_name" placeholder="ชื่อวิชา (วิทยาศาสตร์)" class="border p-2 rounded text-sm">
        </div>
        <button @click="addSubject" class="w-full bg-orange-500 text-white rounded p-2 text-sm font-bold hover:bg-orange-600 mb-4">เพิ่มวิชา</button>
        
        <div class="mb-4">
          <div class="flex items-center gap-2 justify-between">
            <div class="flex items-center gap-2">
              <label class="text-[10px] font-bold text-gray-400 uppercase">นำเข้า (Excel/CSV):</label>
              <input type="file" accept=".xlsx,.xls,.csv" @change="e => handleFileUpload(e, 'subjects')" class="text-xs text-gray-500">
            </div>
            <button @click="clearAll('subjects')" :disabled="clearingType === 'subjects'" class="text-[10px] font-bold text-red-500 hover:text-red-700 flex items-center gap-1 shrink-0">
              <Loader2 v-if="clearingType === 'subjects'" class="w-3 h-3 animate-spin" />
              <Trash2 v-else class="w-3 h-3" /> ล้างข้อมูลทั้งหมด
            </button>
          </div>
          <p class="text-[10px] text-gray-400 mt-1">หัวคอลัมน์ที่ต้องมี: <code class="bg-gray-100 px-1 rounded">subject_code</code>, <code class="bg-gray-100 px-1 rounded">subject_name</code></p>
          <div v-if="uploadingType === 'subjects'" class="mt-1.5">
            <div class="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div class="bg-orange-500 h-1.5 rounded-full transition-all duration-150 ease-out" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <p class="text-[10px] text-orange-500 font-bold mt-0.5">กำลังนำเข้า... {{ uploadProgress }}%</p>
          </div>
        </div>

        <div class="relative mb-2">
          <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
          <input v-model="searchSubjects" placeholder="ค้นหารหัสหรือชื่อวิชา..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
        </div>

        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-center border-b w-10">ลำดับ</th>
                <th class="p-2 text-left border-b">รหัส</th>
                <th class="p-2 text-left border-b">ชื่อวิชา</th>
                <th class="p-2 border-b w-16"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(s, i) in filteredSubjects" :key="s.id" class="hover:bg-gray-50">
                <template v-if="editingType === 'subjects' && editingId === s.id">
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b"><input v-model="editDraft.subject_code" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b"><input v-model="editDraft.subject_name" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="saveEdit" class="text-green-600 hover:text-green-800 mr-1"><Check class="w-3.5 h-3.5 inline" /></button>
                    <button @click="cancelEdit" class="text-gray-400 hover:text-gray-600"><X class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
                <template v-else>
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b text-xs">{{ s.subject_code }}</td>
                  <td class="p-2 border-b font-medium text-xs">{{ s.subject_name }}</td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="startEdit('subjects', s)" class="text-gray-300 hover:text-blue-600 mr-1"><Pencil class="w-3.5 h-3.5 inline" /></button>
                    <button @click="deleteItem('subjects', s.id)" class="text-gray-300 hover:text-red-600"><Trash2 class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
              </tr>
              <tr v-if="filteredSubjects.length === 0"><td colspan="4" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section: Teachers (ครู) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-blue-600">
          <Users class="w-5 h-5" /> 2. รายชื่อบุคลากร (Teachers)
          <span class="text-xs font-bold px-2 py-0.5 bg-blue-50 text-blue-500 rounded-full">ทั้งหมด {{ teachers.length }}</span>
        </h3>
        <div class="grid grid-cols-3 gap-2 mb-2">
          <input v-model="newTeacher.full_name" placeholder="ชื่อ-นามสกุล" class="border p-2 rounded text-sm col-span-2">
          <input v-model="newTeacher.teacher_code" placeholder="รหัส ID" class="border p-2 rounded text-sm">
        </div>
        <div class="grid grid-cols-1 gap-2 mb-2">
          <input v-model="newTeacher.department" placeholder="กลุ่มสาระ" class="border p-2 rounded text-sm">
        </div>
        <button @click="addTeacher" class="w-full bg-blue-600 text-white rounded p-2 text-sm font-bold hover:bg-blue-700 mb-4">เพิ่มครู</button>

        <div class="mb-4">
          <div class="flex items-center gap-2 justify-between">
            <div class="flex items-center gap-2">
              <label class="text-[10px] font-bold text-gray-400 uppercase">นำเข้า (Excel/CSV):</label>
              <input type="file" accept=".xlsx,.xls,.csv" @change="e => handleFileUpload(e, 'teachers')" class="text-xs text-gray-500">
            </div>
            <button @click="clearAll('teachers')" :disabled="clearingType === 'teachers'" class="text-[10px] font-bold text-red-500 hover:text-red-700 flex items-center gap-1 shrink-0">
              <Loader2 v-if="clearingType === 'teachers'" class="w-3 h-3 animate-spin" />
              <Trash2 v-else class="w-3 h-3" /> ล้างข้อมูลทั้งหมด
            </button>
          </div>
          <p class="text-[10px] text-gray-400 mt-1">
            หัวคอลัมน์ที่ต้องมี: <code class="bg-gray-100 px-1 rounded">full_name</code> (บังคับ),
            <code class="bg-gray-100 px-1 rounded">department</code> หรือ <code class="bg-gray-100 px-1 rounded">กลุ่มสาระ</code>,
            <code class="bg-gray-100 px-1 rounded">teacher_code</code> หรือ <code class="bg-gray-100 px-1 rounded">รหัส</code> (ไม่บังคับ)
          </p>
          <div v-if="uploadingType === 'teachers'" class="mt-1.5">
            <div class="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div class="bg-blue-500 h-1.5 rounded-full transition-all duration-150 ease-out" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <p class="text-[10px] text-blue-500 font-bold mt-0.5">กำลังนำเข้า... {{ uploadProgress }}%</p>
          </div>
        </div>

        <div class="relative mb-2">
          <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
          <input v-model="searchTeachers" placeholder="ค้นหาชื่อ, รหัส ID หรือกลุ่มสาระ..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
        </div>

        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-center border-b w-10">ลำดับ</th>
                <th class="p-2 text-left border-b">รหัส ID</th>
                <th class="p-2 text-left border-b">ชื่อ-นามสกุล</th>
                <th class="p-2 text-left border-b">กลุ่มสาระ</th>
                <th class="p-2 border-b w-16"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(t, i) in filteredTeachersTable" :key="t.id" class="hover:bg-gray-50">
                <template v-if="editingType === 'teachers' && editingId === t.id">
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b"><input v-model="editDraft.teacher_code" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b"><input v-model="editDraft.full_name" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b"><input v-model="editDraft.department" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="saveEdit" class="text-green-600 hover:text-green-800 mr-1"><Check class="w-3.5 h-3.5 inline" /></button>
                    <button @click="cancelEdit" class="text-gray-400 hover:text-gray-600"><X class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
                <template v-else>
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b text-gray-400 text-xs">{{ t.teacher_code || '-' }}</td>
                  <td class="p-2 border-b font-medium text-xs">{{ t.full_name }}</td>
                  <td class="p-2 border-b text-gray-500 text-xs">{{ t.department || '-' }}</td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="startEdit('teachers', t)" class="text-gray-300 hover:text-blue-600 mr-1"><Pencil class="w-3.5 h-3.5 inline" /></button>
                    <button @click="deleteItem('teachers', t.id)" class="text-gray-300 hover:text-red-600"><Trash2 class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
              </tr>
              <tr v-if="filteredTeachersTable.length === 0"><td colspan="5" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section: Classrooms (ชั้นเรียน) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-purple-600">
          <School class="w-5 h-5" /> 3. รายชื่อชั้นเรียน (Classrooms)
          <span class="text-xs font-bold px-2 py-0.5 bg-purple-50 text-purple-500 rounded-full">ทั้งหมด {{ classrooms.length }}</span>
        </h3>
        <div class="grid grid-cols-3 gap-2 mb-4">
          <input v-model="newClassroom.grade_level" placeholder="ระดับชั้น" class="border p-2 rounded text-sm">
          <input v-model="newClassroom.room_name" placeholder="ชื่อห้อง" class="border p-2 rounded text-sm">
          <button @click="addClassroom" class="bg-purple-600 text-white rounded text-sm font-bold hover:bg-purple-700 text-xs">เพิ่มชั้นเรียน</button>
        </div>
        <div class="mb-4">
          <div class="flex items-center gap-2 justify-between">
            <div class="flex items-center gap-2">
              <label class="text-[10px] font-bold text-gray-400 uppercase">นำเข้า (Excel/CSV):</label>
              <input type="file" accept=".xlsx,.xls,.csv" @change="e => handleFileUpload(e, 'classrooms')" class="text-xs text-gray-500">
            </div>
            <button @click="clearAll('classrooms')" :disabled="clearingType === 'classrooms'" class="text-[10px] font-bold text-red-500 hover:text-red-700 flex items-center gap-1 shrink-0">
              <Loader2 v-if="clearingType === 'classrooms'" class="w-3 h-3 animate-spin" />
              <Trash2 v-else class="w-3 h-3" /> ล้างข้อมูลทั้งหมด
            </button>
          </div>
          <p class="text-[10px] text-gray-400 mt-1">หัวคอลัมน์ที่ต้องมี: <code class="bg-gray-100 px-1 rounded">grade_level</code>, <code class="bg-gray-100 px-1 rounded">room_name</code></p>
          <div v-if="uploadingType === 'classrooms'" class="mt-1.5">
            <div class="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div class="bg-purple-500 h-1.5 rounded-full transition-all duration-150 ease-out" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <p class="text-[10px] text-purple-500 font-bold mt-0.5">กำลังนำเข้า... {{ uploadProgress }}%</p>
          </div>
        </div>

        <div class="relative mb-2">
          <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
          <input v-model="searchClassrooms" placeholder="ค้นหาห้องเรียน เช่น 1/1..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
        </div>

        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-center border-b w-10">ลำดับ</th>
                <th class="p-2 text-left border-b">ระดับ</th>
                <th class="p-2 text-left border-b">ห้อง</th>
                <th class="p-2 border-b w-16"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(c, i) in filteredClassrooms" :key="c.id" class="hover:bg-gray-50">
                <template v-if="editingType === 'classrooms' && editingId === c.id">
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b"><input v-model="editDraft.grade_level" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b"><input v-model="editDraft.room_name" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="saveEdit" class="text-green-600 hover:text-green-800 mr-1"><Check class="w-3.5 h-3.5 inline" /></button>
                    <button @click="cancelEdit" class="text-gray-400 hover:text-gray-600"><X class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
                <template v-else>
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b text-xs">{{ c.grade_level }}</td>
                  <td class="p-2 border-b font-medium text-xs">{{ c.room_name }}</td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="startEdit('classrooms', c)" class="text-gray-300 hover:text-blue-600 mr-1"><Pencil class="w-3.5 h-3.5 inline" /></button>
                    <button @click="deleteItem('classrooms', c.id)" class="text-gray-300 hover:text-red-600"><Trash2 class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
              </tr>
              <tr v-if="filteredClassrooms.length === 0"><td colspan="4" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Section: Rooms (สถานที่) -->
      <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <h3 class="text-lg font-bold mb-4 flex items-center gap-2 text-green-600">
          <Home class="w-5 h-5" /> 4. สถานที่ / ห้องเรียน (Rooms)
          <span class="text-xs font-bold px-2 py-0.5 bg-green-50 text-green-500 rounded-full">ทั้งหมด {{ rooms.length }}</span>
        </h3>
        <div class="grid grid-cols-3 gap-2 mb-2">
          <input v-model="newRoom.room_name" placeholder="ชื่อสถานที่" class="border p-2 rounded text-sm col-span-2">
          <select v-model="newRoom.room_type" class="border p-2 rounded text-sm col-span-1">
            <option value="ห้องปฏิบัติการ">ห้องปฏิบัติการ</option>
            <option value="ห้องประจำชั้น">ห้องประจำชั้น</option>
          </select>
        </div>
        <p class="text-[10px] text-gray-400 mb-3">ห้องปฏิบัติการ = ห้องที่ครูหลายคนเวียนกันใช้ได้ (เช่น ห้องคอม), ห้องประจำชั้น = ผูกกับนักเรียนห้องเดียวเท่านั้น</p>
        <div v-if="newRoom.room_type === 'ห้องประจำชั้น'" class="mb-3">
          <label class="text-[10px] font-bold text-gray-400 uppercase block mb-1">เป็นห้องประจำของชั้นเรียนไหน (ต้องเลือกก่อนกดเพิ่ม)</label>
          <select v-model="newRoom.home_classroom_id" class="w-full border p-2 rounded text-sm">
            <option value="">-- เลือกห้องเรียน --</option>
            <option v-for="opt in classroomOptionsForHomeRoom" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
          </select>
        </div>
        <button @click="addRoom" class="w-full bg-green-600 text-white rounded p-2 text-sm font-bold hover:bg-green-700 mb-4">เพิ่มสถานที่</button>
        <div class="mb-4">
          <div class="flex items-center gap-2 justify-between">
            <div class="flex items-center gap-2">
              <label class="text-[10px] font-bold text-gray-400 uppercase">นำเข้า (Excel/CSV):</label>
              <input type="file" accept=".xlsx,.xls,.csv" @change="e => handleFileUpload(e, 'rooms')" class="text-xs text-gray-500">
            </div>
            <button @click="clearAll('rooms')" :disabled="clearingType === 'rooms'" class="text-[10px] font-bold text-red-500 hover:text-red-700 flex items-center gap-1 shrink-0">
              <Loader2 v-if="clearingType === 'rooms'" class="w-3 h-3 animate-spin" />
              <Trash2 v-else class="w-3 h-3" /> ล้างข้อมูลทั้งหมด
            </button>
          </div>
          <p class="text-[10px] text-gray-400 mt-1">หัวคอลัมน์: <code class="bg-gray-100 px-1 rounded">room_name</code> (ชื่อห้อง), <code class="bg-gray-100 px-1 rounded">room_type</code> (ไม่บังคับ), <code class="bg-gray-100 px-1 rounded">home_classroom</code> (ไม่บังคับ — ห้องประจำของชั้นไหน เช่น "1/1" ให้ตรงกับ เกรด/ห้อง ในตารางห้องเรียน จะผูกให้อัตโนมัติและตั้ง room_type เป็นห้องประจำชั้น)</p>
          <div v-if="uploadingType === 'rooms'" class="mt-1.5">
            <div class="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div class="bg-green-500 h-1.5 rounded-full transition-all duration-150 ease-out" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <p class="text-[10px] text-green-500 font-bold mt-0.5">กำลังนำเข้า... {{ uploadProgress }}%</p>
          </div>
        </div>

        <div class="relative mb-2">
          <Search class="w-3 h-3 absolute left-2 top-2.5 text-gray-400" />
          <input v-model="searchRooms" placeholder="ค้นหาสถานที่หรือประเภท..." class="w-full text-xs pl-7 pr-2 py-2 border rounded-md bg-gray-50 focus:bg-white outline-none">
        </div>

        <div class="max-h-48 overflow-y-auto border rounded-lg">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 sticky top-0 text-xs">
              <tr>
                <th class="p-2 text-center border-b w-10">ลำดับ</th>
                <th class="p-2 text-left border-b">ชื่อสถานที่</th>
                <th class="p-2 text-left border-b text-center">ประเภท</th>
                <th class="p-2 text-left border-b">ห้องประจำของชั้น</th>
                <th class="p-2 border-b w-16"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in filteredRooms" :key="r.id" class="hover:bg-gray-50">
                <template v-if="editingType === 'rooms' && editingId === r.id">
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b"><input v-model="editDraft.room_name" class="w-full text-xs border rounded p-1"></td>
                  <td class="p-2 border-b">
                    <select v-model="editDraft.room_type" class="w-full text-xs border rounded p-1">
                      <option value="ห้องปฏิบัติการ">ห้องปฏิบัติการ</option>
                      <option value="ห้องประจำชั้น">ห้องประจำชั้น</option>
                    </select>
                  </td>
                  <td class="p-2 border-b">
                    <select v-if="editDraft.room_type === 'ห้องประจำชั้น'" v-model="editDraft.home_classroom_id" class="w-full text-xs border rounded p-1">
                      <option value="">-- เลือกห้องเรียน --</option>
                      <option v-for="opt in classroomOptionsForHomeRoom" :key="opt.id" :value="opt.id">{{ opt.label }}</option>
                    </select>
                    <span v-else class="text-gray-300 text-xs">—</span>
                  </td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="saveEdit" class="text-green-600 hover:text-green-800 mr-1"><Check class="w-3.5 h-3.5 inline" /></button>
                    <button @click="cancelEdit" class="text-gray-400 hover:text-gray-600"><X class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
                <template v-else>
                  <td class="p-2 border-b text-center text-gray-400 text-xs">{{ i + 1 }}</td>
                  <td class="p-2 border-b font-medium text-xs">{{ r.room_name }}</td>
                  <td class="p-2 border-b text-gray-500 text-xs text-center">{{ r.room_type }}</td>
                  <td class="p-2 border-b text-xs">
                    <span v-if="r.home_classroom_label" class="text-purple-600 font-bold">{{ r.home_classroom_label }}</span>
                    <span v-else class="text-gray-300">—</span>
                  </td>
                  <td class="p-2 border-b text-center whitespace-nowrap">
                    <button @click="startEdit('rooms', r)" class="text-gray-300 hover:text-blue-600 mr-1"><Pencil class="w-3.5 h-3.5 inline" /></button>
                    <button @click="deleteItem('rooms', r.id)" class="text-gray-300 hover:text-red-600"><Trash2 class="w-3.5 h-3.5 inline" /></button>
                  </td>
                </template>
              </tr>
              <tr v-if="filteredRooms.length === 0"><td colspan="5" class="p-4 text-center text-gray-400 italic">ไม่มีข้อมูล</td></tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>
  </div>
</template>
