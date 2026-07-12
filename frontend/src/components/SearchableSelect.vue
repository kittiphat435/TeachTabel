<script setup lang="ts">
// Combobox แบบค้นหาได้ — พิมพ์เพื่อกรองรายการจากฐานข้อมูล แล้วคลิกเลือกได้เหมือน dropdown ปกติ
// ใช้แทน <select> ธรรมดาในจุดที่มีตัวเลือกเยอะ (ห้องเรียน/วิชา/ครู) ให้หาได้ง่ายขึ้น
import { ref, computed } from 'vue'
import { Search, X } from 'lucide-vue-next'

interface Option {
  value: string
  label: string
  sublabel?: string
}

const props = defineProps<{
  modelValue: string
  options: Option[]
  placeholder?: string
}>()

const emit = defineEmits<{ (e: 'update:modelValue', value: string): void }>()

const isOpen = ref(false)
const query = ref('')

const selectedOption = computed(() => props.options.find(o => o.value === props.modelValue) || null)

const filteredOptions = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return props.options
  return props.options.filter(
    o => o.label.toLowerCase().includes(q) || (o.sublabel || '').toLowerCase().includes(q)
  )
})

const openDropdown = () => {
  isOpen.value = true
  query.value = ''
}

const onInput = (e: Event) => {
  query.value = (e.target as HTMLInputElement).value
  isOpen.value = true
}

const selectOption = (opt: Option) => {
  emit('update:modelValue', opt.value)
  query.value = ''
  isOpen.value = false
}

const clearSelection = () => {
  emit('update:modelValue', '')
  query.value = ''
}

const closeDropdown = () => {
  // หน่วงเล็กน้อยเพื่อให้ event click บนตัวเลือกทำงานก่อน blur จะปิด dropdown
  setTimeout(() => { isOpen.value = false }, 150)
}
</script>

<template>
  <div class="relative">
    <div class="relative">
      <Search class="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
      <input
        :value="isOpen ? query : (selectedOption?.label || '')"
        @input="onInput"
        @focus="openDropdown"
        @blur="closeDropdown"
        :placeholder="placeholder || 'ค้นหา...'"
        class="w-full border border-gray-300 rounded-md pl-8 pr-7 py-2 text-sm focus:ring-2 focus:ring-blue-400 outline-none"
      />
      <button v-if="modelValue" type="button" @mousedown.prevent="clearSelection" class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300 hover:text-gray-500">
        <X class="w-3.5 h-3.5" />
      </button>
    </div>

    <div v-if="isOpen" class="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-gray-200 rounded-md shadow-lg text-sm">
      <button
        v-for="opt in filteredOptions"
        :key="opt.value"
        type="button"
        @mousedown.prevent="selectOption(opt)"
        :class="['w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center justify-between gap-2', opt.value === modelValue ? 'bg-blue-50 font-bold text-blue-700' : 'text-gray-700']"
      >
        <span>{{ opt.label }}</span>
        <span v-if="opt.sublabel" class="text-[10px] text-gray-400">{{ opt.sublabel }}</span>
      </button>
      <div v-if="filteredOptions.length === 0" class="px-3 py-4 text-center text-xs text-gray-400">ไม่พบรายการ</div>
    </div>
  </div>
</template>
