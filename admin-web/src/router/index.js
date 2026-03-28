import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue')
      },
      {
        path: 'test',
        name: 'TestGenerator',
        component: () => import('@/views/TestGenerator.vue')
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/UserManage.vue')
      },
      {
        path: 'nodes',
        name: 'Nodes',
        component: () => import('@/views/NodeManage.vue')
      },
      {
        path: 'models',
        name: 'Models',
        component: () => import('@/views/ModelManage.vue')
      },
      {
        path: 'strategy',
        name: 'Strategy',
        component: () => import('@/views/StrategyConfig.vue')
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/TaskManage.vue')
      },
      {
        path: 'earnings',
        name: 'Earnings',
        component: () => import('@/views/EarningAudit.vue')
      },
      {
        path: 'withdrawals',
        name: 'Withdrawals',
        component: () => import('@/views/WithdrawalManage.vue')
      },
      {
        path: 'storage',
        name: 'Storage',
        component: () => import('@/views/StorageConfig.vue')
      },
      {
        path: 'risk',
        name: 'Risk',
        component: () => import('@/views/RiskControl.vue')
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/SystemConfig.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  if (to.meta.requiresAuth && !authStore.token) {
    next('/login')
  } else if (to.path === '/login' && authStore.token) {
    next('/')
  } else {
    next()
  }
})

export default router