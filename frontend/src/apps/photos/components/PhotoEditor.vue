<template>
  <Teleport to="body">
    <div v-if="photo" class="fixed inset-0 z-[60] flex flex-col bg-black text-white">
      <div class="flex items-center justify-between p-3">
        <button class="editor-button" :aria-label="__('Cancel')" @click="emit('close')">
          <LucideX class="size-5" />
        </button>
        <div class="flex items-center gap-2">
          <button class="rounded-full px-4 py-2 text-sm text-white/80 hover:bg-white/10" @click="reset">
            {{ __('Reset') }}
          </button>
          <Button variant="solid" :loading="saving" :disabled="!ready" @click="save">{{
            __('Save copy')
          }}</Button>
        </div>
      </div>

      <div class="flex min-h-0 flex-1 items-center justify-center p-4">
        <canvas v-show="ready" ref="canvas" class="max-h-full max-w-full" />
        <LoadingIndicator v-if="!ready" class="size-6" />
      </div>

      <div class="mx-auto flex w-full max-w-3xl flex-col gap-4 p-4">
        <div class="flex justify-center gap-1">
          <button
            v-for="tab in tabs"
            :key="tab.value"
            class="rounded-full px-4 py-1.5 text-sm"
            :class="active === tab.value ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'"
            @click="active = tab.value"
          >
            {{ tab.label }}
          </button>
        </div>

        <div v-if="active === 'filters'" class="flex justify-center gap-3 overflow-x-auto pb-1">
          <button
            v-for="filter in FILTERS"
            :key="filter.name"
            class="flex w-20 shrink-0 flex-col items-center gap-1.5 text-xs"
            @click="state.filter = filter.name"
          >
            <img
              :src="thumbnailUrl(photo.name)"
              class="size-16 rounded-lg object-cover"
              :class="{ 'ring-2 ring-white ring-offset-2 ring-offset-black': state.filter === filter.name }"
              :style="{ filter: filter.css }"
              alt=""
            />
            {{ filter.label }}
          </button>
        </div>

        <div v-else-if="active === 'adjust'" class="grid gap-3 sm:grid-cols-2">
          <label v-for="slider in SLIDERS" :key="slider.key" class="flex items-center gap-3 text-sm">
            <span class="w-24 shrink-0 text-white/80">{{ slider.label }}</span>
            <input
              v-model.number="state[slider.key]"
              type="range"
              min="-100"
              max="100"
              class="flex-1 accent-white"
            />
            <span class="w-8 text-right tabular-nums text-white/60">{{ state[slider.key] }}</span>
          </label>
        </div>

        <div v-else class="flex flex-wrap items-center justify-center gap-2">
          <button
            v-for="ratio in RATIOS"
            :key="ratio.label"
            class="rounded-full px-3 py-1.5 text-sm"
            :class="state.ratio === ratio.value ? 'bg-white text-black' : 'text-white/80 hover:bg-white/10'"
            @click="state.ratio = ratio.value"
          >
            {{ ratio.label }}
          </button>
          <span class="mx-2 h-5 w-px bg-white/20" />
          <button
            class="editor-button"
            :aria-label="__('Rotate')"
            @click="state.rotation = (state.rotation + 90) % 360"
          >
            <LucideRotateCw class="size-5" />
          </button>
          <button class="editor-button" :aria-label="__('Flip')" @click="state.flip = !state.flip">
            <LucideFlipHorizontal2 class="size-5" />
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Button, LoadingIndicator, toast } from 'frappe-ui'
import LucideFlipHorizontal2 from '~icons/lucide/flip-horizontal-2'
import LucideRotateCw from '~icons/lucide/rotate-cw'
import LucideX from '~icons/lucide/x'

import { type Photo, contentUrl, getUploadFolder, thumbnailUrl, uploadFile } from '../api'

const props = defineProps<{ photo: Photo | null; folder?: string | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

type SliderKey = 'brightness' | 'contrast' | 'saturation' | 'warmth'
const FILTERS = [
  { name: 'none', label: __('Original'), css: 'none' },
  { name: 'vivid', label: __('Vivid'), css: 'saturate(1.45) contrast(1.1)' },
  { name: 'mono', label: __('Mono'), css: 'grayscale(1) contrast(1.1)' },
  { name: 'warm', label: __('Warm'), css: 'sepia(0.3) saturate(1.2) hue-rotate(-8deg)' },
  { name: 'cool', label: __('Cool'), css: 'saturate(0.9) hue-rotate(12deg) brightness(1.03)' },
  { name: 'fade', label: __('Fade'), css: 'contrast(0.82) brightness(1.08) saturate(0.75)' },
]
const SLIDERS: { key: SliderKey; label: string }[] = [
  { key: 'brightness', label: __('Brightness') },
  { key: 'contrast', label: __('Contrast') },
  { key: 'saturation', label: __('Saturation') },
  { key: 'warmth', label: __('Warmth') },
]
const RATIOS = [
  { label: __('Original'), value: 0 },
  { label: __('Square'), value: 1 },
  { label: '4:3', value: 4 / 3 },
  { label: '3:4', value: 3 / 4 },
  { label: '16:9', value: 16 / 9 },
]
const tabs = [
  { value: 'crop', label: __('Crop') },
  { value: 'adjust', label: __('Adjust') },
  { value: 'filters', label: __('Filters') },
] as const

const initial = () => ({
  filter: 'none',
  brightness: 0,
  contrast: 0,
  saturation: 0,
  warmth: 0,
  rotation: 0,
  flip: false,
  ratio: 0,
})
const state = reactive(initial())
const active = ref<'crop' | 'adjust' | 'filters'>('crop')
const canvas = ref<HTMLCanvasElement>()
const ready = ref(false)
const saving = ref(false)
let source: HTMLImageElement | null = null

const reset = () => Object.assign(state, initial())

function cssFilter() {
  const parts = [FILTERS.find((f) => f.name === state.filter)?.css ?? 'none']
  parts.push(`brightness(${1 + state.brightness / 200})`)
  parts.push(`contrast(${1 + state.contrast / 200})`)
  parts.push(`saturate(${1 + state.saturation / 100})`)
  if (state.warmth > 0) parts.push(`sepia(${state.warmth / 250})`)
  if (state.warmth < 0) parts.push(`hue-rotate(${state.warmth / 6}deg)`)
  return parts.filter((p) => p !== 'none').join(' ') || 'none'
}

function render(target: HTMLCanvasElement, maxSide: number) {
  if (!source) return
  const turned = state.rotation % 180 !== 0
  const fullW = turned ? source.naturalHeight : source.naturalWidth
  const fullH = turned ? source.naturalWidth : source.naturalHeight
  let cropW = fullW
  let cropH = fullH
  if (state.ratio) {
    if (fullW / fullH > state.ratio) cropW = fullH * state.ratio
    else cropH = fullW / state.ratio
  }
  const scale = Math.min(1, maxSide / Math.max(cropW, cropH))
  target.width = Math.round(cropW * scale)
  target.height = Math.round(cropH * scale)
  const ctx = target.getContext('2d')!
  ctx.filter = cssFilter()
  ctx.translate(target.width / 2, target.height / 2)
  ctx.rotate((state.rotation * Math.PI) / 180)
  if (state.flip) ctx.scale(-1, 1)
  ctx.drawImage(
    source,
    (-source.naturalWidth * scale) / 2,
    (-source.naturalHeight * scale) / 2,
    source.naturalWidth * scale,
    source.naturalHeight * scale,
  )
}

watch(
  () => props.photo?.name,
  (name) => {
    ready.value = false
    reset()
    if (!name) return
    const image = new Image()
    image.onload = () => {
      source = image
      ready.value = true
      draw()
    }
    image.src = contentUrl(name)
  },
  { immediate: true },
)

function draw() {
  if (canvas.value) render(canvas.value, 1600)
}
watch(state, draw)

async function save() {
  if (!props.photo || !source) return
  saving.value = true
  try {
    const output = document.createElement('canvas')
    render(output, 8000)
    const blob = await new Promise<Blob | null>((resolve) => output.toBlob(resolve, 'image/jpeg', 0.92))
    if (!blob) throw new Error(__('Could not export the image'))
    const base = props.photo.file_name.replace(/\.[^.]+$/, '')
    const file = new File([blob], `${base}-edited.jpg`, {
      type: 'image/jpeg',
      lastModified: new Date(props.photo.taken).getTime(),
    })
    try {
      if (!props.folder) throw new Error()
      await uploadFile(file, props.folder, () => {})
    } catch {
      await uploadFile(file, await getUploadFolder(), () => {})
    }
    toast.success(__('Saved a copy next to the original'))
    emit('saved')
    emit('close')
  } catch (error) {
    toast.error((error as Error).message || __('Could not save'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.editor-button {
  @apply flex size-10 items-center justify-center rounded-full text-white/90 transition-colors hover:bg-white/15 hover:text-white;
}
</style>
