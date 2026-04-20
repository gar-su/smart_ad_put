<template>
  <div class="dashboard">
    <!-- 概览卡片 -->
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #409eff">
            <el-icon><Goods /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.totalProducts || 0 }}</div>
            <div class="stat-label">总商品数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #67c23a">
            <el-icon><Promotion /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.activeCampaigns || 0 }}</div>
            <div class="stat-label">活跃广告</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">
            <el-icon><Clock /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.todayDecisions || 0 }}</div>
            <div class="stat-label">今日决策</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.automationRate || 0 }}%</div>
            <div class="stat-label">自动化渗透率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>生命周期分布</span>
            <el-radio-group v-model="lifecycleDimension" size="small" style="float: right">
              <el-radio-button label="product">商品</el-radio-button>
              <el-radio-button label="campaign">广告单元</el-radio-button>
            </el-radio-group>
          </template>
          <div ref="lifecycleChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>决策统计</span>
            <el-button size="small" link type="primary" style="float: right" @click="$router.push('/decisions')">
              查看全部
            </el-button>
          </template>
          <div ref="decisionChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 基建效率趋势 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>基建效率趋势（最近7天）</span>
          </template>
          <div ref="efficiencyChart" class="chart-container-wide"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 告警列表 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>商品健康度告警</span>
          </template>
          <el-table :data="alerts" size="small">
            <el-table-column prop="type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.type === 'warning'" type="warning" size="small">警告</el-tag>
                <el-tag v-else type="info" size="small">提示</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" />
            <el-table-column prop="count" label="数量" width="80" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>策略执行摘要</span>
            <el-button size="small" link type="primary" style="float: right" @click="$router.push('/strategy')">
              管理策略
            </el-button>
          </template>
          <div class="strategy-summary">
            <div class="summary-item">
              <span class="label">启用规则:</span>
              <span class="value">{{ strategyStats.enabledRules }} / {{ strategyStats.totalRules }}</span>
            </div>
            <div class="summary-item">
              <span class="label">今日触发:</span>
              <span class="value">{{ strategyStats.triggersToday }}</span>
            </div>
            <div class="summary-item">
              <span class="label">本周决策:</span>
              <span class="value">{{ strategyStats.decisionsThisWeek }}</span>
            </div>
          </div>
          <el-divider />
          <div class="top-actions">
            <div class="action-title">今日动作分布</div>
            <div v-for="action in strategyStats.topActions" :key="action.action" class="action-item">
              <span class="action-name">{{ formatAction(action.action) }}</span>
              <el-progress :percentage="action.count / strategyStats.triggersToday * 100" :stroke-width="10" />
              <span class="action-count">{{ action.count }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { Goods, Promotion, Clock, Cpu } from '@element-plus/icons-vue'

const lifecycleDimension = ref('product')
const lifecycleChart = ref<HTMLElement>()
const decisionChart = ref<HTMLElement>()
const efficiencyChart = ref<HTMLElement>()

const stats = reactive({
  totalProducts: 1944,
  activeCampaigns: 109198,
  todayDecisions: 0,
  automationRate: 68
})

const alerts = ref([
  { type: 'warning', message: '商品进入衰退期', count: 123 },
  { type: 'info', message: '商品处于成长期', count: 45 },
  { type: 'info', message: '商品处于成熟期', count: 12 }
])

const strategyStats = reactive({
  totalRules: 6,
  enabledRules: 5,
  triggersToday: 12,
  decisionsThisWeek: 156,
  topActions: [
    { action: 'GROWTH_BURST', count: 20 },
    { action: 'REBUILD', count: 12 },
    { action: 'CLONE_AD', count: 8 },
    { action: 'GRACEFUL_SHUTDOWN', count: 5 }
  ]
})

const lifecycleData = reactive({
  product: {
    'product_cold_start': { value: 0.21, name: '冷启动' },
    'product_growth': { value: 0.06, name: '成长期' },
    'product_mature': { value: 0.07, name: '成熟期' },
    'product_decline': { value: 0.66, name: '衰退期' }
  },
  campaign: {
    'campaign_cold_dead': { value: 0.64, name: '冷死亡' },
    'campaign_cold_start': { value: 0.05, name: '冷启动' },
    'campaign_growth': { value: 0.09, name: '增长期' },
    'campaign_stable': { value: 0.10, name: '稳定期' },
    'campaign_decay': { value: 0.12, name: '衰退期' }
  }
})

function formatAction(action: string) {
  const map: Record<string, string> = {
    'GROWTH_BURST': '饱和攻击',
    'CHANNEL_EXPAND': '渠道扩张',
    'CLONE_AD': '复制广告',
    'BUDGET_SMOOTH': '预算平滑',
    'MATERIAL_PREPARE': '素材预热',
    'GRACEFUL_SHUTDOWN': '有序关停',
    'REBUILD': '基建补充'
  }
  return map[action] || action
}

function initLifecycleChart() {
  if (!lifecycleChart.value) return

  const chart = echarts.init(lifecycleChart.value)
  const data = lifecycleData[lifecycleDimension.value as keyof typeof lifecycleData]

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      data: Object.values(data).map(d => d.name)
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: '{b}\n{c}%'
        },
        data: Object.entries(data).map(([key, val]) => ({
          name: val.name,
          value: (val.value * 100).toFixed(1)
        }))
      }
    ],
    color: ['#909399', '#67c23a', '#e6a23c', '#f56c6c']
  }

  chart.setOption(option)
}

function initDecisionChart() {
  if (!decisionChart.value) return

  const chart = echarts.init(decisionChart.value)

  const option = {
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: strategyStats.topActions.map(a => formatAction(a.action))
    },
    yAxis: { type: 'value', name: '次数' },
    series: [
      {
        type: 'bar',
        data: strategyStats.topActions.map(a => a.count),
        itemStyle: {
          color: '#409eff',
          borderRadius: [4, 4, 0, 0]
        }
      }
    ]
  }

  chart.setOption(option)
}

function initEfficiencyChart() {
  if (!efficiencyChart.value) return

  const chart = echarts.init(efficiencyChart.value)

  const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
  const data1 = [12, 15, 18, 22, 19, 25, 28]
  const data2 = [65, 68, 70, 72, 69, 75, 78]

  const option = {
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['决策数', '自动化渗透率']
    },
    xAxis: { type: 'category', data: days },
    yAxis: [
      { type: 'value', name: '决策数', max: 50 },
      { type: 'value', name: '渗透率%', min: 0, max: 100 }
    ],
    series: [
      {
        name: '决策数',
        type: 'bar',
        data: data1,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '自动化渗透率',
        type: 'line',
        yAxisIndex: 1,
        data: data2,
        smooth: true,
        itemStyle: { color: '#67c23a' }
      }
    ]
  }

  chart.setOption(option)
}

watch(lifecycleDimension, () => {
  initLifecycleChart()
})

onMounted(() => {
  initLifecycleChart()
  initDecisionChart()
  initEfficiencyChart()
})
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.chart-container {
  height: 280px;
}

.chart-container-wide {
  height: 250px;
}

.strategy-summary {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.summary-item .label {
  color: #909399;
}

.summary-item .value {
  font-weight: 500;
  color: #303133;
}

.top-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 4px;
}

.action-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.action-name {
  width: 70px;
  font-size: 13px;
}

.action-count {
  width: 30px;
  text-align: right;
  font-size: 13px;
  color: #409eff;
}
</style>
