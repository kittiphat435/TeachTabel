<script setup lang="ts">
import { ref } from 'vue'
import { useAuth } from '../composables/useAuth'
import { Loader2 } from 'lucide-vue-next'

const { signInWithGoogle, errorMessage } = useAuth()
const signingIn = ref(false)

const handleSignIn = async () => {
  signingIn.value = true
  await signInWithGoogle()
  signingIn.value = false
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-600 to-blue-800 px-4">
    <div class="bg-white rounded-2xl shadow-xl p-10 max-w-sm w-full text-center">
      <h1 class="text-2xl font-extrabold text-gray-800 mb-1">TeachTabel</h1>
      <p class="text-sm text-gray-500 mb-8">ระบบจัดตารางสอน — เข้าสู่ระบบเพื่อเริ่มใช้งาน</p>

      <button
        @click="handleSignIn"
        :disabled="signingIn"
        class="w-full flex items-center justify-center gap-3 border border-gray-300 rounded-lg py-3 font-bold text-gray-700 hover:bg-gray-50 transition disabled:opacity-60"
      >
        <Loader2 v-if="signingIn" class="w-5 h-5 animate-spin" />
        <svg v-else class="w-5 h-5" viewBox="0 0 48 48">
          <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3c-1.6 4.6-6 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 6.1 29.6 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.5z"/>
          <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.6 15.6 18.9 13 24 13c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.6 7.1 29.6 5 24 5c-7.5 0-14 4.2-17.7 10.4z"/>
          <path fill="#4CAF50" d="M24 43c5.5 0 10.4-1.9 14.1-5.1l-6.5-5.5C29.7 34 27 35 24 35c-5.2 0-9.6-3.3-11.2-8l-6.6 5.1C9.9 38.9 16.4 43 24 43z"/>
          <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-1 2.9-2.9 5.3-5.3 6.9l6.5 5.5C39.9 37.4 44 31.7 44 24c0-1.3-.1-2.7-.4-3.5z"/>
        </svg>
        เข้าสู่ระบบด้วย Google
      </button>

      <p v-if="errorMessage" class="mt-4 text-xs text-red-500">{{ errorMessage }}</p>

      <p class="mt-8 text-[11px] text-gray-400">
        ครู เจ้าหน้าที่ และผู้ดูแลระบบ สามารถเข้าสู่ระบบด้วยบัญชี Google ของโรงเรียนเพื่อกรอกและจัดตารางสอนร่วมกันได้
      </p>
    </div>
  </div>
</template>
