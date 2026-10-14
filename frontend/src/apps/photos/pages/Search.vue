<template>
  <PhotosHeader :title="title" searchable hide-upload />
  <PhotoGrid
    :handle="handle"
    :empty-icon="LucideSearchX"
    :empty-title="__('No results')"
    :empty-text="__('Try a file name, a camera, a month like October, a year like 2025, or the word videos.')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { usePageMeta } from 'frappe-ui'
import LucideSearchX from '~icons/lucide/search-x'

import { appPageMeta } from '@/utils/documentTitle'
import PhotoGrid from '../components/PhotoGrid.vue'
import PhotosHeader from '../components/PhotosHeader.vue'
import { createFeed } from '../store'

const route = useRoute()
const params = {
  search: route.query.q || undefined,
  camera: route.query.camera || undefined,
  place: route.query.place || undefined,
}
const handle = createFeed('timeline', params)

const title = computed(() => {
  if (params.camera) return __('Taken with {0}', [String(params.camera)])
  if (params.place) return __('Photos near {0}', [String(params.place).replace(',', ', ')])
  return __('Results for “{0}”', [String(params.search)])
})

usePageMeta(() => appPageMeta(title.value, 'Photos'))
</script>
