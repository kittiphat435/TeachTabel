<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ListOrdered, ArrowUp, ArrowDown, Loader2, CheckCircle2, Info, Zap, AlertTriangle, AlertCircle } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

const order = ref<string[]>([])
const loading = ref(true)
const saving = ref(false)
const successMessage = ref('')

// --- กดจัดตารางทีละกลุ่มสาระ (เฉพาะวิชาคาบคู่ของกลุ่มสาระนั้น) — ไม่กดก็ยังไม่ทำอะไร ---
const solvingDept = ref<string | null>(null)
const deptResults = ref<Record<string, any>>({})
const deptError = ref<Record<string, string>>({})

const runDeptSolve = async (dept: string) => {
  solvingDept.value = dept
  deptError.value = { ...deptError.value, [dept]: '' }
  try {
    const res = await axios.post(`${API_BASE}/solve/`, { category: 'double', department: dept })
    deptResults.value = { ...deptResults.value, [dept]: res.data }
  } catch (e: any) {
    let msg = 'เกิดข้อผิดพลาดในการประมวลผล'
    if (e?.response?.status === 403) msg = 'เฉพาะผู้ดูแลระบบ (admin) เท่านั้นที่เริ่มจัดตารางได้'
    else if (e?.response?.status === 401) msg = 'กรุณาเข้าสู่ระบบก่อนใช้งาน'
    else if (e?.response?.data?.detail) msg = e.response.data.detail
    deptError.value = { ...deptError.value, [dept]: msg }
  } finally {
    solvingDept.value = null
  }
}

const fetchOrder = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/settings/department-priority`)
    order.value = res.data.order
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchOrder)

const moveUp = (index: number) => {
  if (index === 0) return
  const arr = [...order.value]
  ;[arr[index - 1], arr[index]] = [arr[index], arr[index - 1]]
  order.value = arr
}

const moveDown = (index: number) => {
  if (index === order.value.length - 1) return
  const arr = [...order.value]
  ;[arr[index + 1], arr[index]] = [arr[index], arr[index + 1]]
  order.value = arr
}

const save = async () => {
  saving.value = true
  successMessage.value = ''
  try {
    await axios.put(`${API_BASE}/settings/department-priority`, { order: order.value })
    successMessage.value = 'บันทึกลำดับความสำคัญสำเร็จ'
  } catch (e: any) {
    if (e?.response?.status === 403) {
      alert('เฉพาะผู้ดูแลระบบ (admin) เท่านั้นที่ปรับลำดับนี้ได้')
    } else {
      alert('บันทึกไม่สำเร็จ')
    }
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div class="flex items-center gap-2">
      <ListOrdered class="w-7 h-7 text-blue-600" />
      <h2 class="text-2xl font-bold text-gray-800">ลำดับความสำคัญกลุ่มสาระ</h2>
    </div>

    <div class="p-4 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-800 flex items-start gap-2">
      <Info class="w-4 h-4 shrink-0 mt-0.5" />
      <span>
        ใช้ตอนจัดตารางสอนอัตโนมัติ (Auto Solver) — วิชาคาบคู่ของกลุ่มสาระที่อยู่บนสุดจะถูกจัดตารางก่อน
        เรียงลำดับโดยกดปุ่มลูกศรขึ้น/ลง แล้วกดบันทึก หรือจะกดปุ่ม "จัดตาราง" ที่แต่ละแถวเพื่อจัดตารางเฉพาะกลุ่มสาระนั้นทันทีก็ได้ —
        ถ้ายังไม่กด ระบบจะยังไม่จัดตารางให้
      </span>
    </div>

    <div v-if="loading" class="text-center py-12 text-gray-400">
      <Loader2 class="w-10 h-10 animate-spin mx-auto mb-2" /> กำลังโหลดข้อมูล...
    </div>

    <div v-else class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
      <div v-if="order.length === 0" class="text-center py-8 text-gray-400 italic text-sm">
        ยังไม่มีข้อมูลกลุ่มสาระ (ต้องเพิ่มครูพร้อมกลุ่มสาระก่อนที่หน้า "จัดการข้อมูลพื้นฐาน")
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="(dept, i) in order"
          :key="dept"
          class="p-3 bg-gray-50 rounded-lg border border-gray-100 space-y-2"
        >
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span class="w-6 h-6 flex items-center justify-center rounded-full bg-blue-600 text-white text-xs font-bold">{{ i + 1 }}</span>
              <span class="text-sm font-bold text-gray-800">{{ dept }}</span>
            </div>
            <div class="flex items-center gap-1">
              <button @click="moveUp(i)" :disabled="i === 0" class="p-1.5 rounded border border-gray-200 text-gray-500 hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed">
                <ArrowUp class="w-3.5 h-3.5" />
              </button>
              <button @click="moveDown(i)" :disabled="i === order.length - 1" class="p-1.5 rounded border border-gray-200 text-gray-500 hover:bg-white disabled:opacity-30 disabled:cursor-not-allowed">
                <ArrowDown class="w-3.5 h-3.5" />
              </button>
              <button
                @click="runDeptSolve(dept)"
                :disabled="solvingDept !== null"
                class="ml-1 bg-blue-600 text-white px-2.5 py-1.5 rounded-md text-xs font-bold hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center gap-1"
              >
                <Loader2 v-if="solvingDept === dept" class="w-3.5 h-3.5 animate-spin" />
                <Zap v-else class="w-3.5 h-3.5" />
                จัดตาราง
              </button>
            </div>
          </div>

          <div v-if="deptError[dept]" class="p-2 bg-red-50 border border-red-200 rounded-md text-xs text-red-700 flex items-center gap-1">
            <AlertTriangle class="w-3.5 h-3.5 shrink-0" /> {{ deptError[dept] }}
          </div>

          <div v-if="deptResults[dept]" class="p-2 bg-white border border-blue-200 rounded-md space-y-1">
            <p class="text-xs font-bold text-gray-800 flex items-center gap-1">
              <CheckCircle2 class="w-3.5 h-3.5 text-green-500" />
              จัดสำเร็จ {{ deptResults[dept].placed_count }} / {{ deptResults[dept].total }} รายการ
            </p>
            <div v-if="deptResults[dept].warnings?.length" class="text-xs text-orange-600 space-y-1">
              <p class="font-bold flex items-center gap-1"><AlertTriangle class="w-3 h-3" /> คำเตือน ({{ deptResults[dept].warnings.length }})</p>
              <ul class="list-disc list-inside">
                <li v-for="(w, wi) in deptResults[dept].warnings" :key="wi">{{ w }}</li>
              </ul>
            </div>
            <div v-if="deptResults[dept].unplaced?.length" class="text-xs text-red-600 space-y-1">
              <p class="font-bold flex items-center gap-1"><AlertCircle class="w-3 h-3" /> จัดไม่ลง ({{ deptResults[dept].unplaced.length }})</p>
              <ul class="list-disc list-inside">
                <li v-for="(u, ui) in deptResults[dept].unplaced" :key="ui">{{ u.subject_name }} — {{ u.reason }}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <div v-if="successMessage" class="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg text-xs text-green-700 flex items-center gap-1">
        <CheckCircle2 class="w-4 h-4" /> {{ successMessage }}
      </div>

      <button
        v-if="order.length > 0"
        @click="save"
        :disabled="saving"
        class="mt-4 w-full bg-blue-600 text-white font-bold py-3 rounded-lg hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center justify-center gap-2 shadow-md"
      >
        <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
        บันทึกลำดับความสำคัญ
      </button>
    </div>
  </div>
</template>
