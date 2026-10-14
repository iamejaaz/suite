<template>
  <PhotosHeader :title="__('Explore')" searchable hide-upload />
  <div class="flex flex-col gap-8 p-3 sm:p-5">
    <section>
      <h2 class="mb-3 text-lg font-semibold text-ink-gray-9">{{ __('Places') }}</h2>
      <div v-if="data?.places.length" class="h-80 sm:h-[420px]">
        <PlacesMap :places="allPlaces" />
      </div>
      <p v-else-if="data" class="text-base text-ink-gray-5">
        {{ __('Photos with a location show up on a map here.') }}
      </p>
    </section>

    <section v-if="data?.cameras.length">
      <h2 class="mb-3 text-lg font-semibold text-ink-gray-9">{{ __('Cameras') }}</h2>
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        <router-link
          v-for="camera in data.cameras"
          :key="camera.camera"
          :to="{ name: 'photos-search', query: { camera: camera.camera } }"
          class="group flex flex-col gap-2"
        >
          <div class="aspect-square overflow-hidden rounded-xl bg-surface-gray-2">
            <img
              :src="thumbnailUrl(camera.cover)"
              class="size-full object-cover transition-transform duration-300 group-hover:scale-105"
              alt=""
            />
          </div>
          <div>
            <div class="truncate text-base font-medium text-ink-gray-8">{{ camera.camera }}</div>
            <div class="text-sm text-ink-gray-5">{{ itemCount(camera.count) }}</div>
          </div>
        </router-link>
      </div>
    </section>

    <section v-if="data?.videos.count">
      <h2 class="mb-3 text-lg font-semibold text-ink-gray-9">{{ __('Media types') }}</h2>
      <div class="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        <router-link
          :to="{ name: 'photos-search', query: { q: 'videos' } }"
          class="group flex flex-col gap-2"
        >
          <div class="relative aspect-square overflow-hidden rounded-xl bg-surface-gray-2">
            <img
              v-if="data.videos.cover"
              :src="thumbnailUrl(data.videos.cover)"
              class="size-full object-cover transition-transform duration-300 group-hover:scale-105"
              alt=""
            />
            <LucidePlay class="absolute right-3 top-3 size-4 fill-white text-white drop-shadow" />
          </div>
          <div>
            <div class="text-base font-medium text-ink-gray-8">{{ __('Videos') }}</div>
            <div class="text-sm text-ink-gray-5">{{ itemCount(data.videos.count) }}</div>
          </div>
        </router-link>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { usePageMeta } from 'frappe-ui'
import LucidePlay from '~icons/lucide/play'

import { appPageMeta } from '@/utils/documentTitle'
import { type Place, getExplore, getPlaces, thumbnailUrl } from '../api'
import PhotosHeader from '../components/PhotosHeader.vue'
import PlacesMap from '../components/PlacesMap.vue'
import { itemCount } from '../utils'

const data = ref<Awaited<ReturnType<typeof getExplore>>>()
const allPlaces = ref<Place[]>([])
getExplore().then((result) => (data.value = result))
getPlaces().then((result) => (allPlaces.value = result))

usePageMeta(() => appPageMeta(__('Explore'), 'Photos'))
</script>
