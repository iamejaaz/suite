<template>
  <ShareDialog
    v-if="open"
    v-model="open"
    :file="file"
    :users-with-access="usersWithAccess"
    :update-access="updateAccess"
    :general-access-url="ALBUM_SHARING.general"
    @success="emit('changed')"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { createResource, toast } from 'frappe-ui'

import { ShareDialog } from '@/apps/drive/ui/drive'
import { ALBUM_SHARING, type Album } from '../api'

const props = defineProps<{ album: Album }>()
const open = defineModel<boolean>({ default: false })
const emit = defineEmits<{ changed: [] }>()

const file = computed(() => ({
  name: props.album.name,
  file_name: props.album.title,
  owner: props.album.owner,
  write: props.album.access?.write,
  is_folder: 0,
  file_type: 'Link',
  file_url: `${window.location.origin}/photos/albums/${props.album.name}`,
}))

const usersWithAccess = createResource({ url: ALBUM_SHARING.list, makeParams: (params: object) => params })
const updateAccess = createResource({
  url: ALBUM_SHARING.update,
  makeParams: (params: Record<string, unknown>) => ({ ...params, method: params.method || 'share' }),
  onError: (error: { messages?: string[] }) =>
    toast.error(error.messages?.[0] ?? __('Could not update access')),
})
</script>
