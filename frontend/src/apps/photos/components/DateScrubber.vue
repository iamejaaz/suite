<template>
  <nav
    v-if="years.length > 1"
    class="sticky top-0 hidden h-[calc(100vh-3rem)] w-14 shrink-0 select-none flex-col py-4 text-right sm:flex"
    :aria-label="__('Jump to date')"
  >
    <div
      v-for="year in years"
      :key="year.year"
      class="group/year flex flex-col"
      :style="{ flexGrow: year.weight }"
    >
      <button
        class="pr-3 text-xs font-medium text-ink-gray-5 hover:text-ink-gray-9"
        @click="jump(year.year, year.months[0].month)"
      >
        {{ year.year }}
      </button>
      <div class="hidden flex-col group-hover/year:flex">
        <button
          v-for="month in year.months"
          :key="month.month"
          class="pr-3 text-xs text-ink-gray-5 hover:text-ink-gray-9"
          @click="jump(year.year, month.month)"
        >
          {{
            dayjs()
              .month(month.month - 1)
              .format('MMM')
          }}
        </button>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import dayjs from 'dayjs'

import { type MonthCount, getMonths } from '../api'
import type { FeedHandle } from '../store'

const props = defineProps<{ handle: FeedHandle }>()
const months = ref<MonthCount[]>([])
getMonths().then((data) => (months.value = data))

const years = computed(() => {
  const grouped = new Map<number, MonthCount[]>()
  for (const row of months.value) {
    if (!grouped.has(row.year)) grouped.set(row.year, [])
    grouped.get(row.year)!.push(row)
  }
  return [...grouped].map(([year, rows]) => ({
    year,
    months: rows,
    weight: Math.max(1, Math.log2(1 + rows.reduce((sum, row) => sum + row.count, 0))),
  }))
})

async function jump(year: number, month: number) {
  const key = `${year}-${String(month).padStart(2, '0')}`
  for (let attempt = 0; attempt < 30; attempt++) {
    const target = [...document.querySelectorAll<HTMLElement>('[data-month]')].find(
      (el) => (el.dataset.month ?? '') <= key,
    )
    if (target && (target.dataset.month === key || !props.handle.feed.hasNext)) {
      target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      return
    }
    if (!props.handle.feed.hasNext) return
    await props.handle.loadMore()
    await nextTick()
  }
}
</script>
