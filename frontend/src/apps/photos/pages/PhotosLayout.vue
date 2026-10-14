<template>
  <FrappeUIProvider>
    <div v-if="!loggedIn" class="flex h-full flex-col bg-surface-base">
      <header class="flex items-center justify-between border-b px-3 py-2 sm:px-5">
        <div class="flex items-center gap-2">
          <img :src="photosLogo" class="size-7" alt="" />
          <span class="text-base font-semibold text-ink-gray-9">{{ __('Photos') }}</span>
        </div>
        <Button variant="subtle" :link="`/login?redirect-to=${encodeURIComponent($route.fullPath)}`">
          {{ __('Sign in') }}
        </Button>
      </header>
      <div class="min-h-0 flex-1 overflow-y-auto">
        <router-view :key="$route.fullPath" />
      </div>
    </div>
    <DesktopShell v-else-if="isDesktop" class="isolate">
      <template #sidebar><PhotosSidebar /></template>
      <div class="relative flex min-h-full flex-col bg-surface-base" @dragover.prevent="onDragOver">
        <router-view :key="$route.fullPath" />
      </div>
    </DesktopShell>
    <MobileShell v-else class="isolate">
      <div class="relative flex min-h-full flex-col bg-surface-base">
        <router-view :key="$route.fullPath" />
      </div>
      <template #nav>
        <nav class="flex justify-around border-t bg-surface-base py-1">
          <router-link
            v-for="item in mobileNav"
            :key="item.label"
            :to="item.to"
            class="flex flex-col items-center gap-0.5 px-4 py-1 text-xs"
            :class="$route.name === item.to.name ? 'text-ink-gray-9' : 'text-ink-gray-5'"
          >
            <component :is="item.icon" class="size-5" />
            {{ item.label }}
          </router-link>
        </nav>
      </template>
    </MobileShell>
    <div
      v-if="dragging"
      class="fixed inset-0 z-40 flex items-center justify-center bg-surface-base/80 backdrop-blur-sm"
      @dragleave.self="dragging = false"
      @dragover.prevent
      @drop.prevent="onDrop"
    >
      <div
        class="pointer-events-none flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-outline-gray-3 px-16 py-12"
      >
        <LucideUpload class="size-8 text-ink-gray-6" />
        <div class="text-lg font-medium text-ink-gray-8">
          {{ __('Drop to add photos') }}
        </div>
        <div class="text-base text-ink-gray-5">
          {{ __('They are saved to the Photos folder in your Drive') }}
        </div>
      </div>
    </div>
    <Lightbox />
    <AlbumPicker />
  </FrappeUIProvider>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { Button, DesktopShell, FrappeUIProvider, MobileShell } from 'frappe-ui'
import LucideBookImage from '~icons/lucide/book-image'
import LucideImages from '~icons/lucide/images'
import LucideCompass from '~icons/lucide/compass'
import LucideUsers from '~icons/lucide/users'
import LucideUpload from '~icons/lucide/upload'

import { initSocket } from '@/apps/drive/socket'
import photosLogo from '@/assets/app-logos/photos.svg'
import { useSessionStore } from '@/boot/session'
import { setupTheme } from '@/utils/setupTheme'
import AlbumPicker from '../components/AlbumPicker.vue'
import Lightbox from '../components/Lightbox.vue'
import PhotosSidebar from '../components/PhotosSidebar.vue'
import { clearSelection, lightbox, loadAlbums, uploadPhotos } from '../store'

setupTheme()
const loggedIn = computed(() => useSessionStore().isLoggedIn)
if (loggedIn.value) {
  initSocket()
  loadAlbums()
}

const route = useRoute()
const isDesktop = useMediaQuery('(min-width: 768px)')
const dragging = ref(false)

const mobileNav = [
  { label: __('Photos'), icon: LucideImages, to: { name: 'photos-home' } },
  { label: __('Explore'), icon: LucideCompass, to: { name: 'photos-explore' } },
  { label: __('Sharing'), icon: LucideUsers, to: { name: 'photos-sharing' } },
  { label: __('Albums'), icon: LucideBookImage, to: { name: 'photos-albums' } },
]

function onDragOver(event: DragEvent) {
  if (event.dataTransfer?.types.includes('Files')) dragging.value = true
}

function onDrop(event: DragEvent) {
  dragging.value = false
  const files = [...(event.dataTransfer?.files ?? [])]
  if (files.length) uploadPhotos(files)
}

watch(
  () => route.fullPath,
  () => {
    clearSelection()
    lightbox.open = false
  },
)

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape' && !lightbox.open) clearSelection()
}
window.addEventListener('keydown', onKey)
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  clearSelection()
  lightbox.open = false
})
</script>
