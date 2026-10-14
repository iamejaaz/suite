<template>
  <div ref="container" class="px-3 pb-10 sm:px-5" @wheel="onWheel">
    <template v-for="line in lines" :key="line.key">
      <h2 v-if="line.month" class="pb-1 pt-6 text-xl font-semibold text-ink-gray-9">
        {{ line.month }}
      </h2>
      <div class="flex gap-4" :data-month="line.monthKey">
        <div
          v-for="group in line.groups"
          :key="group.key"
          class="min-w-0"
          :class="{ 'flex-1': line.groups.length === 1 }"
        >
          <div class="group/day flex h-9 items-center gap-2 pt-2">
            <span
              v-if="selection.size || isGroupSelected(group)"
              class="flex"
              @click.stop="toggleGroup(group)"
            >
              <Checkbox
                class="pointer-events-none"
                :model-value="isGroupSelected(group)"
                :aria-label="__('Select all from {0}', [group.label])"
              />
            </span>
            <span v-else class="hidden group-hover/day:flex" @click.stop="toggleGroup(group)">
              <Checkbox
                class="pointer-events-none"
                :model-value="false"
                :aria-label="__('Select all from {0}', [group.label])"
              />
            </span>
            <span class="text-sm font-medium text-ink-gray-7">{{ group.label }}</span>
          </div>
          <div v-for="(row, rowIndex) in group.rows" :key="rowIndex" class="mb-1 flex gap-1">
            <div
              v-for="tile in row"
              :key="tile.photo.name"
              class="group/tile relative shrink-0 cursor-pointer overflow-hidden bg-surface-gray-2"
              :style="{ width: `${tile.width}px`, height: `${tile.height}px` }"
              @click="onTileClick($event, tile.photo)"
            >
              <img
                :src="thumbnailUrl(tile.photo.name)"
                :alt="tile.photo.file_name"
                loading="lazy"
                decoding="async"
                draggable="false"
                class="size-full select-none object-cover"
              />
              <div
                v-if="selection.has(tile.photo.name)"
                class="pointer-events-none absolute inset-0 bg-surface-white/20 ring-2 ring-inset ring-outline-gray-5"
              />
              <span
                class="absolute left-2 top-2 flex rounded p-0.5 transition-opacity"
                :class="
                  selection.size || selection.has(tile.photo.name)
                    ? 'opacity-100'
                    : 'opacity-0 group-hover/tile:opacity-100'
                "
                @click.stop="toggle(tile.photo, $event)"
              >
                <Checkbox
                  class="pointer-events-none"
                  size="md"
                  :model-value="selection.has(tile.photo.name)"
                  :aria-label="selection.has(tile.photo.name) ? __('Deselect') : __('Select')"
                />
              </span>
              <div
                v-if="isVideo(tile.photo)"
                class="absolute right-2 top-2 flex items-center gap-1 text-xs font-medium text-white drop-shadow"
              >
                <span v-if="tile.photo.duration">{{ formatDuration(tile.photo.duration) }}</span>
                <LucidePlay class="size-3.5 fill-current" />
              </div>
              <LucideStar
                v-if="tile.photo.is_favourite"
                class="absolute bottom-2 left-2 size-4 fill-white text-white drop-shadow"
              />
            </div>
          </div>
        </div>
      </div>
    </template>

    <div ref="sentinel" class="h-px" />
    <div v-if="handle.feed.loading" class="flex justify-center py-8">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>
    <div
      v-else-if="handle.feed.loaded && !handle.feed.rows.length"
      class="flex flex-col items-center justify-center gap-3 py-24 text-center"
    >
      <div class="flex size-14 items-center justify-center rounded-full bg-surface-gray-2">
        <component :is="emptyIcon" class="size-6 text-ink-gray-6" />
      </div>
      <div class="text-lg font-medium text-ink-gray-8">{{ emptyTitle }}</div>
      <div class="max-w-sm text-base text-ink-gray-5">{{ emptyText }}</div>
      <slot name="empty-action" />
    </div>
    <ErrorMessage v-if="handle.feed.error" class="py-4 text-center" :message="handle.feed.error" />
  </div>
</template>

<script setup lang="ts">
import { type Component, computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useResizeObserver } from '@vueuse/core'
import { Checkbox, ErrorMessage, LoadingIndicator } from 'frappe-ui'
import dayjs from 'dayjs'
import LucidePlay from '~icons/lucide/play'
import LucideStar from '~icons/lucide/star'

import { type Photo, isVideo, thumbnailUrl } from '../api'
import { type FeedHandle, activeFeed, changeZoom, openLightbox, selection, zoom } from '../store'

const props = defineProps<{
  handle: FeedHandle
  emptyTitle: string
  emptyText: string
  emptyIcon: Component
}>()

interface Tile {
  photo: Photo
  width: number
  height: number
}
interface Group {
  key: string
  label: string
  month: string | null
  photos: Photo[]
  rows: Tile[][]
}
interface Line {
  key: string
  month: string | null
  groups: Group[]
  packable: boolean
  monthKey: string
}

const GAP = 4
const DAY_GAP = 16
const container = ref<HTMLElement>()
const sentinel = ref<HTMLElement>()
const width = ref(0)
let lastClicked: string | null = null

useResizeObserver(container, (entries) => {
  width.value = Math.floor(entries[0].contentRect.width)
})

const targetHeight = computed(() => (width.value < 640 ? 120 : width.value < 1100 ? 180 : 220) * zoom.value)

const groups = computed(() => {
  const result: Omit<Group, 'rows'>[] = []
  let previousMonth = ''
  for (const photo of props.handle.feed.rows) {
    const taken = dayjs(photo.taken)
    const key = taken.format('YYYY-MM-DD')
    let group = result[result.length - 1]
    if (!group || group.key !== key) {
      const month = taken.format('MMMM YYYY')
      group = {
        key,
        label: dayLabel(taken),
        month: month !== previousMonth && !isRecent(taken) ? month : null,
        photos: [],
      }
      previousMonth = month
      result.push(group)
    }
    group.photos.push(photo)
  }
  return result
})

const lines = computed<Line[]>(() => {
  const result: Line[] = []
  let used = 0
  for (const day of groups.value) {
    const { rows, open } = justify(day.photos)
    const group = { ...day, rows }
    const natural = rows.length === 1 && open ? rowWidth(rows[0]) : null
    const current = result[result.length - 1]
    if (natural !== null && current?.packable && !day.month && used + DAY_GAP + natural <= width.value) {
      current.groups.push(group)
      used += DAY_GAP + natural
      continue
    }
    result.push({
      key: day.key,
      month: day.month,
      monthKey: day.key.slice(0, 7),
      groups: [group],
      packable: natural !== null,
    })
    used = natural ?? width.value
  }
  return result
})

function rowWidth(row: Tile[]) {
  return row.reduce((sum, tile) => sum + tile.width, 0) + GAP * (row.length - 1)
}

const flat = computed(() => props.handle.feed.rows)

function justify(photos: Photo[]): { rows: Tile[][]; open: boolean } {
  const available = width.value
  if (!available) return { rows: [], open: false }
  const rows: Tile[][] = []
  let current: Photo[] = []
  let ratioSum = 0
  for (const photo of photos) {
    current.push(photo)
    ratioSum += ratio(photo)
    const rowWidth = ratioSum * targetHeight.value + GAP * (current.length - 1)
    if (rowWidth >= available) {
      const height = (available - GAP * (current.length - 1)) / ratioSum
      rows.push(current.map((p) => ({ photo: p, width: ratio(p) * height, height })))
      current = []
      ratioSum = 0
    }
  }
  if (current.length) {
    const height = targetHeight.value
    rows.push(current.map((p) => ({ photo: p, width: ratio(p) * height, height })))
  }
  return { rows, open: current.length > 0 }
}

function ratio(photo: Photo) {
  if (!photo.width || !photo.height) return 1
  return Math.min(3, Math.max(0.4, photo.width / photo.height))
}

function isRecent(date: dayjs.Dayjs) {
  return dayjs().diff(date, 'day') < 7
}

function dayLabel(date: dayjs.Dayjs) {
  const today = dayjs().startOf('day')
  const diff = today.diff(date.startOf('day'), 'day')
  if (diff === 0) return __('Today')
  if (diff === 1) return __('Yesterday')
  if (diff < 7) return date.format('dddd')
  return date.year() === today.year() ? date.format('ddd, D MMM') : date.format('ddd, D MMM YYYY')
}

function formatDuration(seconds: number) {
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

function toggle(photo: Photo, event?: MouseEvent) {
  if (event?.shiftKey && lastClicked) {
    const names = flat.value.map((row) => row.name)
    const [a, b] = [names.indexOf(lastClicked), names.indexOf(photo.name)].sort((x, y) => x - y)
    if (a > -1) {
      names.slice(a, b + 1).forEach((name) => selection.add(name))
      lastClicked = photo.name
      return
    }
  }
  if (selection.has(photo.name)) selection.delete(photo.name)
  else selection.add(photo.name)
  lastClicked = photo.name
}

function onWheel(event: WheelEvent) {
  if (!event.ctrlKey && !event.metaKey) return
  event.preventDefault()
  changeZoom(event.deltaY < 0 ? 0.1 : -0.1)
}

function onTileClick(event: MouseEvent, photo: Photo) {
  if (selection.size) return toggle(photo, event)
  openLightbox(props.handle, photo.name)
}

function isGroupSelected(group: Group) {
  return group.photos.every((photo) => selection.has(photo.name))
}

function toggleGroup(group: Group) {
  const select = !isGroupSelected(group)
  group.photos.forEach((photo) => (select ? selection.add(photo.name) : selection.delete(photo.name)))
}

let observer: IntersectionObserver | null = null
onMounted(() => {
  activeFeed.value = props.handle
  observer = new IntersectionObserver((entries) => entries[0].isIntersecting && props.handle.loadMore(), {
    rootMargin: '1200px',
  })
  if (sentinel.value) observer.observe(sentinel.value)
  if (!props.handle.feed.loaded) props.handle.loadMore()
})
onBeforeUnmount(() => observer?.disconnect())

watch(
  () => props.handle.feed.loading,
  (loading) => {
    if (loading || !sentinel.value || !props.handle.feed.hasNext) return
    const rect = sentinel.value.getBoundingClientRect()
    if (rect.top < window.innerHeight + 1200) props.handle.loadMore()
  },
)
</script>
