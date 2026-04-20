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
      path: '/strategy',
      name: 'Strategy',
      component: () => import('@/pages/Strategy/index.vue'),
      meta: { title: '策略配置' }
    },
    {
      path: '/decisions',
      name: 'Decisions',
      component: () => import('@/pages/Decisions/index.vue'),
      meta: { title: '决策日志' }
    }
  ]
})

export default router
