<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { LayoutDashboard, Users, BookOpen, Home, CheckCircle2, AlertCircle, Loader2 } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

const stats = ref({
  teachers: 0,
  subjects: 0,
  classrooms: 0,
  assignments: 0,
  totalPeriods: 0
})

const teacherWorkload = ref<any[]>([])
const loading = ref(true)

const fetchData = async () => {
  loading.value = true
  try {
    const [tRes, sRes, cRes, aRes] = await Promise.all([
      axios.get(`${API_BASE}/teachers/`),
      axios.get(`${API_BASE}/subjects/`),
      axios.get(`${API_BASE}/classrooms/`),
      axios.get(`${API_BASE}/assignments/`)
    ])

    stats.value = {
      teachers: tRes.data.length,
      subjects: sRes.data.length,
      classrooms: cRes.data.length,
      assignments: aRes.data.length,
      totalPeriods: aRes.data.reduce((sum: number, a: any) => sum + (a.total_periods || 0), 0)
    }

    // คำนวณภาระงานครูแบบง่าย (ในอนาคตควรดึงจากตารางเชื่อมโยง assignment_teachers)
    // สำหรับ Prototype นี้เราแสดงเป็นภาพรวมก่อน
    teacherWorkload.value = tRes.data.slice(0, 5).map((t: any) => ({
        name: t.full_name,
        dept: t.department,
        status: 'พร้อมจัดตาราง'
    }))

  } catch (error) {
    console.error('Error fetching dashboard data:', error)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <h2 class="text-2xl font-bold flex items-center gap-2 text-gray-800">
        <LayoutDashboard class="w-7 h-7 text-blue-600" /> สรุปภาพรวมข้อมูล (Dashboard)
      </h2>
      <button @click="fetchData" class="text-sm text-blue-600 hover:underline flex items-center gap-1">
        <Loader2 v-if="loading" class="w-3 h-3 animate-spin" /> รีเฟรชข้อมูล
      </button>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center gap-4">
        <div class="p-3 bg-blue-100 rounded-full text-blue-600"><Users class="w-6 h-6" /></div>
        <div>
          <p class="text-sm text-gray-500 font-medium">ครูทั้งหมด</p>
          <p class="text-2xl font-bold">{{ stats.teachers }} ท่าน</p>
        </div>
      </div>
      <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center gap-4">
        <div class="p-3 bg-green-100 rounded-full text-green-600"><BookOpen class="w-6 h-6" /></div>
        <div>
          <p class="text-sm text-gray-500 font-medium">วิชาทั้งหมด</p>
          <p class="text-2xl font-bold">{{ stats.subjects }} วิชา</p>
        </div>
      </div>
      <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center gap-4">
        <div class="p-3 bg-purple-100 rounded-full text-purple-600"><Home class="w-6 h-6" /></div>
        <div>
          <p class="text-sm text-gray-500 font-medium">ห้องเรียน</p>
          <p class="text-2xl font-bold">{{ stats.classrooms }} ห้อง</p>
        </div>
      </div>
      <div class="bg-white p-4 rounded-lg shadow-sm border border-gray-100 flex items-center gap-4">
        <div class="p-3 bg-orange-100 rounded-full text-orange-600"><CheckCircle2 class="w-6 h-6" /></div>
        <div>
          <p class="text-sm text-gray-500 font-medium">ภาระงานรวม</p>
          <p class="text-2xl font-bold">{{ stats.totalPeriods }} คาบ</p>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Status Check -->
      <div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 class="font-bold mb-4 text-gray-700">สถานะความพร้อมก่อนจัดตาราง (Pre-check)</h3>
        <ul class="space-y-4">
          <li class="flex items-start gap-3">
            <CheckCircle2 class="w-5 h-5 text-green-500 mt-0.5" />
            <div>
              <p class="font-medium text-sm">ข้อมูลครูและวิชา</p>
              <p class="text-xs text-gray-500">นำเข้าข้อมูลพื้นฐานเรียบร้อยแล้ว</p>
            </div>
          </li>
          <li class="flex items-start gap-3">
            <CheckCircle2 v-if="stats.assignments > 0" class="w-5 h-5 text-green-500 mt-0.5" />
            <AlertCircle v-else class="w-5 h-5 text-orange-500 mt-0.5" />
            <div>
              <p class="font-medium text-sm">การกำหนดภาระงาน (Assignments)</p>
              <p class="text-xs text-gray-500" v-if="stats.assignments > 0">มีการสร้างภาระงานแล้ว {{ stats.assignments }} รายการ</p>
              <p class="text-xs text-orange-500" v-else>ยังไม่มีการกำหนดภาระงานสอน</p>
            </div>
          </li>
          <li class="flex items-start gap-3">
            <Info class="w-5 h-5 text-blue-500 mt-0.5" />
            <div>
              <p class="font-medium text-sm">การตรวจสอบเงื่อนไข (Constraints)</p>
              <p class="text-xs text-gray-500">ระบบจะตรวจสอบครูสอนซ้ำและห้องเรียนซ้ำให้อัตโนมัติ</p>
            </div>
          </li>
        </ul>
        
        <div class="mt-8 p-4 bg-blue-50 border border-blue-100 rounded-lg">
          <p class="text-sm text-blue-800 font-medium mb-1">พร้อมเข้าสู่ Flow 3?</p>
          <p class="text-xs text-blue-600 mb-3">เมื่อตรวจสอบข้อมูลครบถ้วนแล้ว คุณสามารถกดปุ่ม "ประมวลผลจัดตาราง" เพื่อให้อัลกอริทึมเริ่มทำงาน</p>
          <button 
            :disabled="stats.assignments === 0"
            class="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-bold hover:bg-blue-700 transition disabled:bg-gray-300"
          >
            เริ่มประมวลผลจัดตาราง (AI Solver)
          </button>
        </div>
      </div>

      <!-- Quick View List -->
      <div class="bg-white p-6 rounded-lg shadow-sm border border-gray-200">
        <h3 class="font-bold mb-4 text-gray-700">รายชื่อครูและสถานะภาระงาน (ตัวอย่าง)</h3>
        <div class="space-y-3">
          <div v-for="t in teacherWorkload" :key="t.name" class="flex items-center justify-between p-3 bg-gray-50 rounded-md border border-gray-100">
            <div>
              <p class="text-sm font-bold text-gray-800">{{ t.name }}</p>
              <p class="text-xs text-gray-500">{{ t.dept }}</p>
            </div>
            <span class="text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-bold uppercase">{{ t.status }}</span>
          </div>
          <p v-if="teacherWorkload.length === 0" class="text-center py-8 text-gray-400 italic text-sm">ไม่มีข้อมูลครูในระบบ</p>
        </div>
      </div>
    </div>
  </div>
</template>
