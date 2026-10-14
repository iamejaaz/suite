import type { RouteRecordRaw } from 'vue-router'

export const routes: RouteRecordRaw[] = [
  {
    path: '',
    component: () => import('@/apps/photos/pages/PhotosLayout.vue'),
    children: [
      {
        path: '',
        name: 'photos-home',
        component: () => import('@/apps/photos/pages/Timeline.vue'),
      },
      {
        path: 'search',
        name: 'photos-search',
        component: () => import('@/apps/photos/pages/Search.vue'),
      },
      {
        path: 'explore',
        name: 'photos-explore',
        component: () => import('@/apps/photos/pages/Explore.vue'),
      },
      {
        path: 'sharing',
        name: 'photos-sharing',
        component: () => import('@/apps/photos/pages/Albums.vue'),
        props: { shared: true },
      },
      {
        path: 'favourites',
        name: 'photos-favourites',
        component: () => import('@/apps/photos/pages/Collection.vue'),
        props: { kind: 'favourites' },
      },
      {
        path: 'archive',
        name: 'photos-archive',
        component: () => import('@/apps/photos/pages/Collection.vue'),
        props: { kind: 'archive' },
      },
      {
        path: 'trash',
        name: 'photos-trash',
        component: () => import('@/apps/photos/pages/Collection.vue'),
        props: { kind: 'trash' },
      },
      {
        path: 'people',
        name: 'photos-people',
        component: () => import('@/apps/photos/pages/People.vue'),
      },
      {
        path: 'people/:person',
        name: 'photos-person',
        component: () => import('@/apps/photos/pages/PersonPage.vue'),
        props: true,
      },
      {
        path: 'duplicates',
        name: 'photos-duplicates',
        component: () => import('@/apps/photos/pages/Duplicates.vue'),
      },
      {
        path: 'albums',
        name: 'photos-albums',
        component: () => import('@/apps/photos/pages/Albums.vue'),
      },
      {
        path: 'albums/:album',
        name: 'photos-album',
        component: () => import('@/apps/photos/pages/Album.vue'),
        props: true,
        meta: { allowGuest: true },
      },
    ],
  },
]
