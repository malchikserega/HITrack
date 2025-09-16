import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import TagImagesView from '../views/TagImagesView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/repositories',
      name: 'repositories',
      component: () => import('../views/RepositoriesView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/images',
      name: 'images',
      component: () => import('../views/ImagesView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/images/:uuid',
      name: 'image-detail',
      component: () => import('../views/ImageDetailView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/components',
      name: 'components',
      component: () => import('../views/ComponentsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/vulnerabilities',
      name: 'vulnerabilities',
      component: () => import('../views/VulnerabilitiesView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/vulnerabilities/:uuid',
      name: 'vulnerability-detail',
      component: () => import('../views/VulnerabilityDetailView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/acr',
      name: 'ACR',
      component: () => import('../views/ACRView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/reports',
      name: 'reports',
      component: () => import('../views/ReportGeneratorView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/repositories/:uuid',
      name: 'RepositoryDetail',
      component: () => import('../views/RepositoryDetailView.vue'),
    },
    {
      path: '/repository-tags/:uuid/images',
      name: 'tag-images',
      component: TagImagesView,
      props: true,
      meta: {
        requiresAuth: true,
        title: 'Tag Images'
      }
    },
    {
      path: '/component-matrix',
      name: 'component-matrix',
      component: () => import('../views/ComponentMatrixView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/releases',
      name: 'releases',
      component: () => import('../views/ReleasesView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('../views/TaskManagementView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/images/:uuid/component-locations',
      name: 'component-locations',
      component: () => import('../views/ComponentLocationsView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/components/:uuid',
      name: 'component-detail',
      component: () => import('../views/ComponentDetailView.vue'),
      meta: { requiresAuth: true }
    },
    {
      path: '/component-versions/:uuid',
      name: 'component-version',
      component: () => import('../views/ComponentVersionView.vue'),
      meta: { requiresAuth: true }
    }
  ]
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

  if (requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/')
  } else {
    next()
  }
})

export default router 