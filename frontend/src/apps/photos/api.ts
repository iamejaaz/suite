import { call } from 'frappe-ui'

export interface Photo {
  name: string
  file_name: string
  folder: string
  mime_type: string
  file_size: number
  taken: string
  width: number | null
  height: number | null
  duration: number | null
  camera: string | null
  latitude: number | null
  longitude: number | null
  is_favourite: string | null
  owner: string
  added_by?: string
  write?: number
}

export interface Page {
  rows: Photo[]
  has_next: boolean
  next_start: number
}

export interface Album {
  name: string
  title: string
  cover: string | null
  count: number
  owner: string
  owner_name: string
  general: 'public' | 'site' | null
  shared: boolean
  shared_on?: string
  access?: { read: number; write: number; share: number; owner: number }
}

export interface Memory {
  year: number
  years_ago: number
  photos: Photo[]
}

export interface Place {
  latitude: number
  longitude: number
  count: number
  cover: string
}

export interface MonthCount {
  year: number
  month: number
  count: number
}

const PHOTOS = 'suite.photos.api.photos'
const ALBUMS = 'suite.photos.api.albums'
const DRIVE = 'suite.drive.api.files'
const CHUNK_SIZE = 20 * 1024 * 1024

export const thumbnailUrl = (name: string) => `/api/method/${DRIVE}.get_thumbnail?entity_name=${name}`
export const contentUrl = (name: string) => `/api/method/${DRIVE}.get_file_content?entity_name=${name}`
export const streamUrl = (name: string) => `/api/method/${DRIVE}.stream_file_content?entity_name=${name}`
export const downloadUrl = (name: string) => `${contentUrl(name)}&trigger_download=1`
export const isVideo = (photo: Photo) => photo.mime_type?.startsWith('video/')

export const fetchPage = (method: string, params: Record<string, unknown>) =>
  call(method.includes('.') ? method : `${PHOTOS}.${method}`, params) as Promise<Page>

export const getDetails = (name: string) => call(`${PHOTOS}.get_details`, { name })
export const getMemories = () => call(`${PHOTOS}.memories`) as Promise<Memory[]>
export const getPlaces = () => call(`${PHOTOS}.places`) as Promise<Place[]>
export const getMonths = () => call(`${PHOTOS}.months`) as Promise<MonthCount[]>
export const getExplore = () =>
  call(`${PHOTOS}.explore`) as Promise<{
    places: Place[]
    cameras: { camera: string; cover: string; count: number }[]
    videos: { count: number; cover: string | null }
  }>
export const setArchived = (files: string[], archived: boolean) =>
  call(`${PHOTOS}.set_archived`, { files, archived })
export const getUploadFolder = () => call(`${PHOTOS}.get_upload_folder`) as Promise<string>

export const ALBUM_PHOTOS = `${ALBUMS}.album_photos`
export const getAlbums = () => call(`${ALBUMS}.albums`) as Promise<Album[]>
export const getSharedAlbums = () => call(`${ALBUMS}.shared_albums`) as Promise<Album[]>
export const getAlbum = (album: string) => call(`${ALBUMS}.get_album`, { album }) as Promise<Album>
export const createAlbum = (title: string, files: string[] = []) =>
  call(`${ALBUMS}.create_album`, { title, files }) as Promise<string>
export const renameAlbum = (album: string, title: string) => call(`${ALBUMS}.rename_album`, { album, title })
export const setCover = (album: string, file: string) => call(`${ALBUMS}.set_cover`, { album, file })
export const deleteAlbum = (album: string) => call(`${ALBUMS}.delete_album`, { album })
export const leaveAlbum = (album: string) => call(`${ALBUMS}.leave_album`, { album })
export const addToAlbum = (album: string, files: string[]) => call(`${ALBUMS}.add_to_album`, { album, files })
export const removeFromAlbum = (album: string, files: string[]) =>
  call(`${ALBUMS}.remove_from_album`, { album, files })
export const ALBUM_SHARING = {
  list: `${ALBUMS}.get_shared_with_list`,
  update: `${ALBUMS}.update_access`,
  general: `${ALBUMS}.get_general_access`,
}

export const setFavourite = (names: string[], value: boolean) =>
  call(`${DRIVE}.set_favourite`, {
    entities: names.map((name) => ({ name, is_favourite: JSON.stringify(value) })),
  })
export const toggleTrash = (names: string[]) => call(`${DRIVE}.remove_or_restore`, { entity_names: names })
export const deleteForever = (names: string[]) => call(`${DRIVE}.delete_entities`, { entity_names: names })

export async function uploadFile(file: File, parent: string, onProgress: (loaded: number) => void) {
  const uuid = crypto.randomUUID()
  const total = Math.max(1, Math.ceil(file.size / CHUNK_SIZE))
  for (let index = 0; index < total; index++) {
    const offset = index * CHUNK_SIZE
    const form = new FormData()
    form.append('file', file.slice(offset, offset + CHUNK_SIZE), file.name)
    form.append('parent', parent)
    form.append('uuid', uuid)
    form.append('total_file_size', String(file.size))
    form.append('file_modified', String(file.lastModified))
    form.append('chunk_index', String(index))
    form.append('total_chunk_count', String(total))
    form.append('chunk_byte_offset', String(offset))
    const response = await fetch(`/api/method/${DRIVE}.upload_file`, {
      method: 'POST',
      body: form,
      headers: { 'X-Frappe-CSRF-Token': window.csrf_token ?? '' },
    })
    if (!response.ok) throw new Error(await errorMessage(response))
    onProgress(Math.min(file.size, offset + CHUNK_SIZE))
    if (index === total - 1) return ((await response.json()).message?.name as string | undefined) ?? null
  }
  return null
}

async function errorMessage(response: Response) {
  try {
    const body = await response.json()
    const messages = JSON.parse(body._server_messages || '[]')
    return messages.length ? JSON.parse(messages[0]).message : body.exception || response.statusText
  } catch {
    return response.statusText
  }
}
