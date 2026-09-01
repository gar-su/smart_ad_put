import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/dashboard'
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/pages/Dashboard/index.vue'),
      meta: { title: '诊断看板' }
    },
    {
      path: '/decisions',
      name: 'Decisions',
      component: () => import('@/pages/Decisions/index.vue'),
      meta: { title: '决策日志' }
    },
    {
      path: '/config',
      name: 'Config',
      component: () => import('@/pages/Config/index.vue'),
      meta: { title: '信号配置' }
    }
  ]
})

export default router
