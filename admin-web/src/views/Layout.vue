<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'">
      <div class="logo">
        <span v-if="!isCollapse">ShareYourAi</span>
        <span v-else>SA</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        router
        background-color="#1e1e2d"
        text-color="#b0b0b0"
        active-text-color="#fff"
      >
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <span>首页</span>
        </el-menu-item>

        <el-menu-item index="/test">
          <el-icon><VideoPlay /></el-icon>
          <span>调用测试</span>
        </el-menu-item>

        <el-menu-item index="/users">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>

        <el-menu-item index="/nodes">
          <el-icon><Monitor /></el-icon>
          <span>节点管理</span>
        </el-menu-item>

        <el-menu-item index="/models">
          <el-icon><Setting /></el-icon>
          <span>模型管理</span>
        </el-menu-item>

        <el-menu-item index="/strategy">
          <el-icon><Aim /></el-icon>
          <span>派单策略</span>
        </el-menu-item>

        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span>任务管理</span>
        </el-menu-item>

        <el-menu-item index="/earnings">
          <el-icon><Coin /></el-icon>
          <span>收益审核</span>
        </el-menu-item>

        <el-menu-item index="/withdrawals">
          <el-icon><Wallet /></el-icon>
          <span>提现管理</span>
        </el-menu-item>

        <el-menu-item index="/storage">
          <el-icon><FolderOpened /></el-icon>
          <span>存储配置</span>
        </el-menu-item>

        <el-menu-item index="/risk">
          <el-icon><Warning /></el-icon>
          <span>风控中心</span>
        </el-menu-item>

        <el-menu-item index="/platforms">
          <el-icon><Connection /></el-icon>
          <span>平台客户</span>
        </el-menu-item>

        <el-menu-item index="/settings">
          <el-icon><Tools /></el-icon>
          <span>系统配置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主体区域 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header>
        <div class="header-left">
          <el-icon
            class="collapse-btn"
            @click="isCollapse = !isCollapse"
          >
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
        </div>

        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">{{ authStore.user?.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区域 -->
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Odometer, User, Monitor, Setting, Aim, List,
  Coin, Wallet, FolderOpened, Warning, Tools,
  Fold, Expand, UserFilled, VideoPlay, Connection
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const isCollapse = ref(false)
const activeMenu = computed(() => route.path)

async function handleCommand(command) {
  if (command === 'logout') {
    await authStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.el-aside {
  background-color: #1e1e2d;
  transition: width 0.3s;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  border-bottom: 1px solid #2d2d3d;
}

.el-menu {
  border-right: none;
}

.el-menu-item.is-active {
  background-color: #4F46E5 !important;
}

.el-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
}

.collapse-btn {
  font-size: 20px;
  cursor: pointer;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.username {
  color: #333;
}

.el-main {
  background: #f5f7fa;
  padding: 20px;
}
</style>