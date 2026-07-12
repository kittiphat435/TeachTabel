<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { Image, Loader2, CheckCircle2 } from 'lucide-vue-next'

const API_BASE = 'http://localhost:8000'

const schoolName = ref('')
const logoBase64 = ref<string | null>(null)
const loading = ref(true)
const saving = ref(false)
const successMessage = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const fetchInfo = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_BASE}/settings/school-info`)
    schoolName.value = res.data?.school_name || ''
    logoBase64.value = res.data?.logo_base64 || null
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchInfo)

const onLogoSelected = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 1.5 * 1024 * 1024) {
    alert('ไฟล์โลโก้ใหญ่เกินไป กรุณาใช้ไฟล์ไม่เกิน 1.5MB')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    logoBase64.value = reader.result as string
  }
  reader.readAsDataURL(file)
}

const save = async () => {
  saving.value = true
  successMessage.value = ''
  try {
    await axios.put(`${API_BASE}/settings/school-info`, {
      school_name: schoolName.value,
      logo_base64: logoBase64.value,
    })
    successMessage.value = 'บันทึกข้อมูลโรงเรียนสำเร็จ'
  } catch (e: any) {
    alert(e?.response?.status === 403 ? 'เฉพาะผู้ดูแลระบบเท่านั้น' : 'บันทึกไม่สำเร็จ')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
    <h3 class="font-bold text-gray-800 flex items-center gap-2">
      <Image class="w-5 h-5 text-blue-600" /> ข้อมูลสถานศึกษา / โลโก้
    </h3>

    <div v-if="loading" class="text-center py-6 text-gray-400">
      <Loader2 class="w-6 h-6 animate-spin mx-auto" />
    </div>

    <div v-else class="space-y-4">
      <div>
        <label class="text-xs font-bold text-gray-500 block mb-1">ชื่อสถานศึกษา</label>
        <input v-model="schoolName" type="text" placeholder="เช่น โรงเรียนตัวอย่างวิทยา" class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm" />
      </div>

      <div>
        <label class="text-xs font-bold text-gray-500 block mb-1">โลโก้สถานศึกษา</label>
        <div class="flex items-center gap-4">
          <div class="w-16 h-16 rounded-lg border border-gray-200 bg-gray-50 flex items-center justify-center overflow-hidden shrink-0">
            <img v-if="logoBase64" :src="logoBase64" class="w-full h-full object-contain" />
            <Image v-else class="w-6 h-6 text-gray-300" />
          </div>
          <div class="flex flex-col gap-1">
            <button @click="fileInput?.click()" type="button" class="text-xs bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-md font-bold text-gray-700 w-fit">
              เลือกไฟล์รูปภาพ
            </button>
            <input ref="fileInput" type="file" accept="image/*" class="hidden" @change="onLogoSelected" />
            <p class="text-[10px] text-gray-400">รองรับไฟล์ไม่เกิน 1.5MB (PNG/JPG)</p>
          </div>
        </div>
      </div>

      <div v-if="successMessage" class="p-2 bg-green-50 border border-green-200 rounded-md text-xs text-green-700 flex items-center gap-1">
        <CheckCircle2 class="w-4 h-4" /> {{ successMessage }}
      </div>

      <button
        @click="save"
        :disabled="saving"
        class="bg-blue-600 text-white font-bold px-4 py-2 rounded-md text-sm hover:bg-blue-700 transition disabled:bg-gray-300 flex items-center gap-2"
      >
        <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
        บันทึกข้อมูลโรงเรียน
      </button>
    </div>
  </div>
</template>
