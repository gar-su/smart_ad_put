<template>
  <div class="dashboard">
    <!-- 概览卡片 -->
    <el-row :gutter="20">
      <el-col :span="5">
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
      <el-col :span="5">
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
      <el-col :span="5">
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
      <el-col :span="5">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.profitabilityRate || 0 }}%</div>
            <div class="stat-label">盈利率</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #909399">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">{{ stats.automationRate || 0 }}%</div>
            <div class="stat-label">自动化率</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>生命周期分布（基于ROI）</span>
            <el-radio-group v-model="lifecycleDimension" size="small" style="float: right">
              <el-radio-button label="campaign">广告单元</el-radio-button>
              <el-radio-button label="product">商品</el-radio-button>
            </el-radio-group>
          </template>
          <div ref="lifecycleChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>ROI分布</span>
          </template>
          <div ref="roiChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 决策统计 -->
    <el-row :gutter="20" style="margin-top: 20px">
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
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>基建效率趋势（最近7天）</span>
          </template>
          <div ref="efficiencyChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 告警列表 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>告警列表</span>
          </template>
          <el-table :data="alerts" size="small">
            <el-table-column prop="type" label="类型" width="80">
              <template #default="{ row }">
                <el-tag v-if="row.type === 'warning'" type="warning" size="small">警告</el-tag>
                <el-tag v-else-if="row.type === 'success'" type="success" size="small">正常</el-tag>
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
import { Goods, Promotion, Clock, Cpu, TrendCharts } from '@element-plus/icons-vue'

const lifecycleDimension = ref('campaign')
const lifecycleChart = ref<HTMLElement>()
const roiChart = ref<HTMLElement>()
const decisionChart = ref<HTMLElement>()
const efficiencyChart = ref<HTMLElement>()

// 统计数据
const stats = reactive({
  totalProducts: 1147,
  activeCampaigns: 20000,
  todayDecisions: 45,
  profitabilityRate: 27,  // ROI > 40% 的Campaign占比
  automationRate: 68
})

// 告警列表（基于ROI）
const alerts = ref([
  { type: 'warning', message: 'Campaign进入衰退期(ROI下降>50%)', count: 123 },
  { type: 'warning', message: 'Campaign冷启动失败(前24h ROI<10%)', count: 89 },
  { type: 'success', message: 'Campaign进入成长期(ROI>40%)', count: 56 },
  { type: 'info', message: 'Campaign处于验证期(ROI 10-40%)', count: 234 }
])

// 策略统计
const strategyStats = reactive({
  totalRules: 11,  // 更新为11个预置策略
  enabledRules: 8,
  triggersToday: 12,
  decisionsThisWeek: 156,
  topActions: [
    { action: 'GROWTH_BURST', count: 20 },
    { action: 'INCREASE_BUDGET', count: 15 },
    { action: 'REBUILD', count: 12 },
    { action: 'CLONE_AD', count: 8 },
    { action: 'CHANNEL_EXPAND', count: 6 },
    { action: 'GRACEFUL_SHUTDOWN', count: 5 }
  ]
})

// 生命周期数据（基于ROI）
const lifecycleData = reactive({
  // Campaign维度（基于ROI）
  campaign: {
    'campaign_cold_dead': { value: 0.243, name: '冷死亡(收入=0)' },
    'campaign_cold_start': { value: 0.40, name: '冷启动(ROI<10%)' },
    'campaign_verify': { value: 0.20, name: '验证期(ROI 10-40%)' },
    'campaign_growth': { value: 0.08, name: '成长期(ROI>40%)' },
    'campaign_sustained': { value: 0.05, name: '持续盈利(>7天)' },
    'campaign_decline': { value: 0.027, name: '衰退期' }
  },
  // Product维度（基于回测数据）
  product: {
    'product_observing': { value: 0.15, name: '待观察(<3天)' },
    'product_entry': { value: 0.12, name: '入场期(近3天ROI>40%)' },
    'product_sustained': { value: 0.20, name: '稳定期(5天ROI 30-80%)' },
    'product_growth': { value: 0.10, name: '成长期(ROI>40%上升)' },
    'product_decline': { value: 0.18, name: '衰退期(ROI下滑>30%)' },
    'product_exit': { value: 0.15, name: '退出期(ROI<10%)' },
    'product_dead': { value: 0.10, name: '无投放(cost=0)' }
  }
})

// ROI分布数据
const roiDistributionData = [
  { range: 'ROI>40%', count: 5463, color: '#67c23a' },
  { range: 'ROI 20-40%', count: 3074, color: '#e6a23c' },
  { range: 'ROI 0-20%', count: 6423, color: '#f56c6c' },
  { range: 'ROI≤0', count: 5040, color: '#909399' }
]

function formatAction(action: string) {
  const map: Record<string, string> = {
    'GROWTH_BURST': '饱和攻击',
    'CHANNEL_EXPAND': '渠道扩张',
    'CLONE_AD': '复制广告',
    'BUDGET_SMOOTH': '预算平滑',
    'MATERIAL_PREPARE': '素材预热',
    'GRACEFUL_SHUTDOWN': '有序关停',
    'REBUILD': '基建补充',
    'INCREASE_BUDGET': '增加预算',
    'REDUCE_BUDGET': '降低预算',
    'MAINTAIN': '维持现状'
  }
  return map[action] || action
}

function initLifecycleChart() {
  if (!lifecycleChart.value) return

  const chart = echarts.init(lifecycleChart.value)
  const data = lifecycleData[lifecycleDimension.value as keyof typeof lifecycleData]

  // 颜色映射
  const colorMap: Record<string, string> = {
    // Campaign
    '冷死亡(收入=0)': '#909399',
    '冷启动(ROI<10%)': '#f56c6c',
    '验证期(ROI 10-40%)': '#e6a23c',
    '成长期(ROI>40%)': '#67c23a',
    '持续盈利(>7天)': '#409eff',
    '衰退期': '#ff6600',
    // Product
    '待观察(<3天)': '#909399',
    '入场期(近3天ROI>40%)': '#67c23a',
    '稳定期(5天ROI 30-80%)': '#409eff',
    '成长期(ROI>40%上升)': '#00d084',
    '衰退期(ROI下滑>30%)': '#ff6600',
    '退出期(ROI<10%)': '#f56c6c',
    '无投放(cost=0)': '#909399'
  }

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c}% ({d}%)'
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
          value: (val.value * 100).toFixed(1),
          itemStyle: { color: colorMap[val.name] }
        }))
      }
    ]
  }

  chart.setOption(option)
}

function initROIChart() {
  if (!roiChart.value) return

  const chart = echarts.init(roiChart.value)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: '{b}: {c} 个Campaign'
    },
    xAxis: {
      type: 'category',
      data: roiDistributionData.map(d => d.range)
    },
    yAxis: { type: 'value', name: 'Campaign数' },
    series: [
      {
        type: 'bar',
        data: roiDistributionData.map(d => ({
          value: d.count,
          itemStyle: { color: d.color }
        })),
        itemStyle: { borderRadius: [4, 4, 0, 0] },
        label: {
          show: true,
          position: 'top',
          formatter: '{c}'
        }
      }
    ]
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
  const decisions = [12, 15, 18, 22, 19, 25, 28]
  const automationRate = [65, 68, 70, 72, 69, 75, 78]

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
        data: decisions,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '自动化渗透率',
        type: 'line',
        yAxisIndex: 1,
        data: automationRate,
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
  initROIChart()
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
  width: 80px;
  font-size: 13px;
}

.action-count {
  width: 30px;
  text-align: right;
  font-size: 13px;
  color: #409eff;
}
</style>
