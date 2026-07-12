<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { CalendarRange, Plus, Trash2, Loader2, CheckCircle2, Copy, X, Pencil, Check } from 'lucide-vue-next'
import { useAcademicYear } from '../composables/useAcademicYear'
import SchoolSettings from './SchoolSettings.vue'

const API_BASE = 'http://localhost:8000'

const { academicYears, currentYearKey, setAcademicYears, setCurrentYearKey } = useAcademicYear()
const loading = ref(true)

const fetchYears = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/academic-years/`)
    setAcademicYears(res.data)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchYears)

// --- ฟอร์มสร้างปีการศึกษาใหม่ ---
const showCreateForm = ref(false)
const newYear = ref('')
const newTerm = ref(1)
const creating = ref(false)

// ตัวเลือก "ใช้ข้อมูลเดิม" — ถามทุกครั้งตอนสร้างปี/เทอมใหม่ ว่าจะดึงครู/วิชา/ห้องเรียน/ห้อง จากปีก่อนหน้ามาใช้หรือไม่
const useOldData = ref(true)
const sourceYearKey = ref('')
const copyTeachers = ref(true)
const copySubjects = ref(true)
const copyClassrooms = ref(true)
const copyRooms = ref(true)
const copyDeptPriority = ref(true)

const hasExistingYears = computed(() => academicYears.value.length > 0)

const openCreateForm = () => {
  showCreateForm.value = true
  newYear.value = ''
  newTerm.value = 1
  useOldData.value = hasExistingYears.value
  sourceYearKey.value = academicYears.value[0]?.year_key || ''
}

const createYear = async () => {
  if (!newYear.value.trim()) {
    alert('กรุณากรอกปีการศึกษา (พ.ศ.)')
    return
  }
  if (useOldData.value && !sourceYearKey.value) {
    alert('กรุณาเลือกปีการศึกษาต้นทางที่จะคัดลอกข้อมูล')
    return
  }
  creating.value = true
  try {
    const res = await axios.post(`${API_BASE}/academic-years/`, {
      year: newYear.value.trim(),
      term: newTerm.value,
    })
    const newYearKey = res.data.year_key

    if (useOldData.value) {
      await axios.post(`${API_BASE}/academic-years/${newYearKey}/duplicate`, {
        source_year_key: sourceYearKey.value,
        copy_teachers: copyTeachers.value,
        copy_subjects: copySubjects.value,
        copy_classrooms: copyClassrooms.value,
        copy_rooms: copyRooms.value,
        copy_department_priority: copyDeptPriority.value,
      })
    }

    await fetchYears()
    setCurrentYearKey(newYearKey)
    showCreateForm.value = false
  } catch (e: any) {
    if (e?.response?.status === 409) {
      alert('ปีการศึกษา/เทอมนี้มีอยู่แล้ว')
    } else if (e?.response?.status === 403) {
      alert('เฉพาะผู้ดูแลระบบเท่านั้นที่สร้างปีการศึกษาใหม่ได้')
    } else {
      alert('สร้างปีการศึกษาไม่สำเร็จ')
    }
  } finally {
    creating.value = false
  }
}

const deleteYear = async (id: string, label: string) => {
  if (!confirm(`ลบ "${label}" ออกจากระบบ? (รายการนี้จะหายไปจากตัวเลือก แต่ข้อมูลที่เคยผูกไว้จะยังอยู่ใน Firestore)`)) return
  try {
    await axios.delete(`${API_BASE}/academic-years/${id}`)
    await fetchYears()
  } catch (e: any) {
    alert(e?.response?.status === 403 ? 'เฉพาะผู้ดูแลระบบเท่านั้น' : 'ลบไม่สำเร็จ')
  }
}

// แก้ไขชื่อ (label) ปีการศึกษา — แก้ได้ทีละรายการ
const editingYearId = ref<string | null>(null)
const editingLabel = ref('')
const savingLabel = ref(false)

const startEditLabel = (id: string, label: string) => {
  editingYearId.value = id
  editingLabel.value = label
}

const cancelEditLabel = () => {
  editingYearId.value = null
  editingLabel.value = ''
}

const saveLabel = async () => {
  if (!editingYearId.value || !editingLabel.value.trim()) return
  savingLabel.value = true
  try {
    await axios.put(`${API_BASE}/academic-years/${editingYearId.value}`, { label: editingLabel.value.trim() })
    cancelEditLabel()
    await fetchYears()
  } catch (e: any) {
    alert(e?.response?.status === 403 ? 'เฉพาะผู้ดูแลระบบเท่านั้น' : 'บันทึกไม่สำเร็จ')
  } finally {
    savingLabel.value = false
  }
}
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <div class="flex items-center gap-2">
      <CalendarRange class="w-7 h-7 text-blue-600" />
      <h2 class="text-2xl font-bold text-gray-800">ปีการศึกษา / ตั้งค่าโรงเรียน</h2>
    </div>

    <SchoolSettings />

    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="font-bold text-gray-800">รายการปีการศึกษา/เทอม</h3>
        <button @click="openCreateForm" class="bg-blue-600 text-white text-sm font-bold px-3 py-2 rounded-md hover:bg-blue-700 flex items-center gap-1">
          <Plus class="w-4 h-4" /> สร้างปีการศึกษาใหม่
        </button>
      </div>

      <div v-if="loading" class="text-center py-8 text-gray-400">
        <Loader2 class="w-8 h-8 animate-spin mx-auto" />
      </div>

      <div v-else-if="academicYears.length === 0" class="text-center py-8 text-gray-400 italic text-sm">
        ยังไม่มีปีการศึกษาในระบบ กด "สร้างปีการศึกษาใหม่" เพื่อเริ่มต้น
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="y in academicYears"
          :key="y.id"
          class="flex items-center justify-between p-3 rounded-lg border"
          :class="y.year_key === currentYearKey ? 'bg-blue-50 border-blue-300' : 'bg-gray-50 border-gray-100'"
        >
          <div class="flex items-center gap-3 flex-1 min-w-0">
            <CheckCircle2 v-if="y.year_key === currentYearKey" class="w-5 h-5 text-blue-600 shrink-0" />
            <div class="w-5 h-5 shrink-0" v-else></div>
            <input
              v-if="editingYearId === y.id"
              v-model="editingLabel"
              class="text-sm font-bold text-gray-800 border rounded-md px-2 py-1 flex-1 min-w-0"
              @keyup.enter="saveLabel"
              @keyup.esc="cancelEditLabel"
            >
            <span v-else class="text-sm font-bold text-gray-800">{{ y.label }}</span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <template v-if="editingYearId === y.id">
              <button @click="saveLabel" :disabled="savingLabel" class="p-1.5 rounded border border-green-200 text-green-600 hover:bg-green-50">
                <Loader2 v-if="savingLabel" class="w-3.5 h-3.5 animate-spin" />
                <Check v-else class="w-3.5 h-3.5" />
              </button>
              <button @click="cancelEditLabel" class="p-1.5 rounded border border-gray-200 text-gray-400 hover:bg-gray-50">
                <X class="w-3.5 h-3.5" />
              </button>
            </template>
            <template v-else>
              <button
                v-if="y.year_key !== currentYearKey"
                @click="setCurrentYearKey(y.year_key)"
                class="text-xs bg-white border border-gray-300 px-3 py-1.5 rounded-md font-bold text-gray-600 hover:bg-gray-100"
              >
                ใช้งานปีนี้
              </button>
              <button @click="startEditLabel(y.id, y.label)" class="p-1.5 rounded border border-gray-200 text-gray-400 hover:text-blue-600 hover:bg-blue-50">
                <Pencil class="w-3.5 h-3.5" />
              </button>
              <button @click="deleteYear(y.id, y.label)" class="p-1.5 rounded border border-gray-200 text-red-400 hover:bg-red-50">
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </template>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: สร้างปีการศึกษาใหม่ -->
    <div v-if="showCreateForm" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" @click.self="showCreateForm = false">
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
        <div class="flex items-center justify-between">
          <h3 class="font-bold text-gray-800">สร้างปีการศึกษาใหม่</h3>
          <button @click="showCreateForm = false"><X class="w-5 h-5 text-gray-400" /></button>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="text-xs font-bold text-gray-500 block mb-1">ปีการศึกษา (พ.ศ.)</label>
            <input v-model="newYear" type="text" placeholder="เช่น 2569" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" />
          </div>
          <div>
            <label class="text-xs font-bold text-gray-500 block mb-1">เทอม</label>
            <select v-model.number="newTerm" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm">
              <option :value="1">เทอม 1</option>
              <option :value="2">เทอม 2</option>
            </select>
          </div>
        </div>

        <div v-if="hasExistingYears" class="border-t pt-4 space-y-3">
          <label class="flex items-center gap-2 text-sm font-bold text-gray-700">
            <input type="checkbox" v-model="useOldData" class="w-4 h-4" />
            <Copy class="w-4 h-4 text-blue-600" />
            ใช้ข้อมูลครู/วิชา/ห้องเรียน/ห้อง จากปีก่อนหน้า
          </label>

          <div v-if="useOldData" class="pl-6 space-y-3">
            <div>
              <label class="text-xs font-bold text-gray-500 block mb-1">คัดลอกข้อมูลจากปี/เทอม</label>
              <select v-model="sourceYearKey" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm">
                <option v-for="y in academicYears" :key="y.year_key" :value="y.year_key">{{ y.label }}</option>
              </select>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs text-gray-600">
              <label class="flex items-center gap-1"><input type="checkbox" v-model="copyTeachers" /> ครู</label>
              <label class="flex items-center gap-1"><input type="checkbox" v-model="copySubjects" /> วิชา</label>
              <label class="flex items-center gap-1"><input type="checkbox" v-model="copyClassrooms" /> ห้องเรียน</label>
              <label class="flex items-center gap-1"><input type="checkbox" v-model="copyRooms" /> ห้อง</label>
              <label class="flex items-center gap-1 col-span-2"><input type="checkbox" v-model="copyDeptPriority" /> ลำดับความสำคัญกลุ่มสาระ</label>
            </div>
            <p class="text-[10px] text-gray-400">หมายเหตุ: จะไม่คัดลอกภาระงานสอน/ตารางสอน/ล็อกเวลาครู เพราะเป็นข้อมูลเฉพาะปี/เทอมนั้น ๆ</p>
          </div>
        </div>

        <button
          @click="createYear"
          :disabled="creating"
          class="w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2"
        >
          <Loader2 v-if="creating" class="w-4 h-4 animate-spin" />
          สร้างปีการศึกษา
        </button>
      </div>
    </div>
  </div>
</template>
