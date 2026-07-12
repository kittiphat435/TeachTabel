<script setup lang="ts">
import { ref, watch } from 'vue'
import axios from 'axios'
import AssignmentForm from './components/AssignmentForm.vue'
import TeacherUnavailability from './components/TeacherUnavailability.vue'
import Dashboard from './components/Dashboard.vue'
import RoomManager from './components/RoomManager.vue'
import FixedEventManager from './components/FixedEventManager.vue'
import ManualSchedule from './components/ManualSchedule.vue'
import DepartmentPriority from './components/DepartmentPriority.vue'
import AcademicYearManager from './components/AcademicYearManager.vue'
import TeacherSchedule from './components/TeacherSchedule.vue'
import Login from './components/Login.vue'
import { useAuth } from './composables/useAuth'
import { useAcademicYear } from './composables/useAcademicYear'
import { LogOut, Loader2, CalendarRange } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'
const currentTab = ref('dashboard')
const { user, profile, loading, logout } = useAuth()
const { academicYears, currentYearKey, setAcademicYears, setCurrentYearKey } = useAcademicYear()

const schoolLogo = ref<string | null>(null)
const schoolName = ref('')

const fetchYears = async () => {
  try {
    const res = await axios.get(`${API_BASE}/academic-years/`)
    setAcademicYears(res.data)
  } catch (e) { console.error(e) }
}

const fetchSchoolInfo = async () => {
  try {
    const res = await axios.get(`${API_BASE}/settings/school-info`)
    schoolLogo.value = res.data?.logo_base64 || null
    schoolName.value = res.data?.school_name || ''
  } catch (e) { console.error(e) }
}

watch(user, (u) => {
  if (u) {
    fetchYears()
    fetchSchoolInfo()
  }
}, { immediate: true })
</script>

<template>
  <div v-if="loading" class="min-h-screen flex items-center justify-center bg-gray-50">
    <Loader2 class="w-10 h-10 animate-spin text-blue-600" />
  </div>

  <Login v-else-if="!user" />

  <div v-else class="min-h-screen bg-gray-50 text-gray-900">
    <header class="bg-blue-600 text-white shadow-lg">
      <div class="container mx-auto px-4 pt-6">
        <div class="flex items-center justify-between mb-6">
          <div class="w-24 flex items-center">
            <img v-if="schoolLogo" :src="schoolLogo" class="w-10 h-10 rounded-md bg-white object-contain p-0.5" />
          </div>
          <div class="flex flex-col items-center">
            <h1 class="text-3xl font-extrabold tracking-tight">TeachTabel</h1>
            <p class="text-blue-100 text-sm mt-1">{{ schoolName || 'ระบบจัดตารางสอนอัตโนมัติด้วย AI' }}</p>
          </div>
          <div class="flex items-center gap-2 w-auto">
            <div class="flex items-center gap-1 bg-blue-700/50 rounded-md px-2 py-1.5 mr-1">
              <CalendarRange class="w-3.5 h-3.5 text-blue-100 shrink-0" />
              <select
                :value="currentYearKey"
                @change="setCurrentYearKey(($event.target as HTMLSelectElement).value)"
                class="bg-transparent text-white text-xs font-bold outline-none max-w-[140px]"
              >
                <option v-if="academicYears.length === 0" value="">ยังไม่มีปีการศึกษา</option>
                <option v-for="y in academicYears" :key="y.year_key" :value="y.year_key" class="text-gray-800">{{ y.label }}</option>
              </select>
            </div>
            <img v-if="profile?.picture" :src="profile.picture" class="w-8 h-8 rounded-full border-2 border-white" />
            <div class="text-right">
              <p class="text-xs font-bold leading-tight">{{ profile?.name || user?.email }}</p>
              <p class="text-[10px] text-blue-100 uppercase leading-tight">{{ profile?.role === 'admin' ? 'ผู้ดูแลระบบ' : 'ครู' }}</p>
            </div>
            <button @click="logout" class="p-2 hover:bg-blue-500 rounded-full transition" title="ออกจากระบบ">
              <LogOut class="w-4 h-4" />
            </button>
          </div>
        </div>

        <nav class="flex flex-wrap justify-center gap-1.5 pb-3">
          <button
            @click="currentTab = 'dashboard'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'dashboard' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            Dashboard
          </button>
          <button
            @click="currentTab = 'rooms'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'rooms' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            จัดการข้อมูลพื้นฐาน
          </button>
          <button
            @click="currentTab = 'student-tasks'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'student-tasks' ? 'bg-gray-50 text-red-700 shadow-sm' : 'text-white hover:bg-red-500']"
          >
            กิจกรรมบังคับ (นักเรียน)
          </button>
          <button
            @click="currentTab = 'assignments'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'assignments' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            จัดการภาระงานสอน
          </button>
          <button
            @click="currentTab = 'schedule-manual'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'schedule-manual' ? 'bg-gray-50 text-green-700 shadow-sm' : 'text-white hover:bg-green-600']"
          >
            จัดตารางสอน (Manual)
          </button>
          <button
            @click="currentTab = 'unavailability'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'unavailability' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            ล็อกเวลาครู
          </button>
          <button
            @click="currentTab = 'teacher-schedule'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'teacher-schedule' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            ตารางครู (รายบุคคล)
          </button>
          <button
            @click="currentTab = 'department-priority'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'department-priority' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            ลำดับความสำคัญกลุ่มสาระ
          </button>
          <button
            @click="currentTab = 'academic-year'"
            :class="['px-3 py-1.5 text-xs sm:text-sm rounded-lg font-bold transition-all duration-200 flex items-center gap-1.5 whitespace-nowrap', currentTab === 'academic-year' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            ปีการศึกษา / ตั้งค่าโรงเรียน
          </button>
        </nav>
      </div>
    </header>

    <main class="container mx-auto py-8 px-4 max-w-7xl">
      <transition name="fade" mode="out-in">
        <div :key="currentTab">
          <Dashboard v-if="currentTab === 'dashboard'" />
          <RoomManager v-else-if="currentTab === 'rooms'" />
          <FixedEventManager v-else-if="currentTab === 'student-tasks'" />
          <AssignmentForm v-else-if="currentTab === 'assignments'" />
          <ManualSchedule v-else-if="currentTab === 'schedule-manual'" />
          <TeacherUnavailability v-else-if="currentTab === 'unavailability'" />
          <TeacherSchedule v-else-if="currentTab === 'teacher-schedule'" />
          <DepartmentPriority v-else-if="currentTab === 'department-priority'" />
          <AcademicYearManager v-else-if="currentTab === 'academic-year'" />
        </div>
      </transition>
    </main>
  </div>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
