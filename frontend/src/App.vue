<template>
  <el-container class="app-container">
    <el-aside width="200px">
      <div class="logo">智能广告基建</div>
      <el-menu
        :default-active="$route.path"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon>
          <span>诊断看板</span>
        </el-menu-item>
        <el-menu-item index="/strategy">
          <el-icon><Setting /></el-icon>
          <span>策略配置</span>
        </el-menu-item>
        <el-menu-item index="/decisions">
          <el-icon><Document /></el-icon>
          <span>决策日志</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header>
        <div class="header-title">{{ $route.meta.title || '智能广告基建系统' }}</div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { DataAnalysis, Setting, Document } from '@element-plus/icons-vue'
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
  background: #f5f7fa;
}

.sidebar-menu {
  border-right: none;
}

.el-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
}

.header-title {
  font-size: 18px;
  font-weight: 500;
}

.el-main {
  background: #f5f7fa;
}
</style>
