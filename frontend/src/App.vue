<script setup lang="ts">
import { ref } from 'vue'
import AssignmentForm from './components/AssignmentForm.vue'
import TeacherUnavailability from './components/TeacherUnavailability.vue'
import Dashboard from './components/Dashboard.vue'
import RoomManager from './components/RoomManager.vue'
import FixedEventManager from './components/FixedEventManager.vue'

const currentTab = ref('dashboard')
</script>

<template>
  <div class="min-h-screen bg-gray-50 text-gray-900">
    <header class="bg-blue-600 text-white shadow-lg">
      <div class="container mx-auto px-4 pt-6">
        <div class="flex flex-col items-center mb-6">
          <h1 class="text-3xl font-extrabold tracking-tight">TeachTabel</h1>
          <p class="text-blue-100 text-sm mt-1">ระบบจัดตารางสอนอัตโนมัติด้วย AI</p>
        </div>
        
        <nav class="flex justify-center gap-1 overflow-x-auto pb-2">
          <button 
            @click="currentTab = 'dashboard'"
            :class="['px-5 py-3 rounded-t-xl font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap', currentTab === 'dashboard' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            Dashboard
          </button>
          <button 
            @click="currentTab = 'rooms'"
            :class="['px-5 py-3 rounded-t-xl font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap', currentTab === 'rooms' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            จัดการข้อมูลพื้นฐาน
          </button>
          <button 
            @click="currentTab = 'student-tasks'"
            :class="['px-5 py-3 rounded-t-xl font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap', currentTab === 'student-tasks' ? 'bg-gray-50 text-red-700 shadow-sm' : 'text-white hover:bg-red-500']"
          >
            กิจกรรมบังคับ (นักเรียน)
          </button>
          <button 
            @click="currentTab = 'assignments'"
            :class="['px-5 py-3 rounded-t-xl font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap', currentTab === 'assignments' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            จัดการภาระงานสอน
          </button>
          <button 
            @click="currentTab = 'unavailability'"
            :class="['px-5 py-3 rounded-t-xl font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap', currentTab === 'unavailability' ? 'bg-gray-50 text-blue-700 shadow-sm' : 'text-white hover:bg-blue-500']"
          >
            ล็อกเวลาครู
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
          <TeacherUnavailability v-else-if="currentTab === 'unavailability'" />
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
