<template>
  <div class="dashboard">
    <!-- 概览卡片 -->
    <div class="stat-row">
      <el-card v-for="card in statCards" :key="card.label" shadow="hover" class="stat-card">
        <div class="stat-icon" :style="{ background: card.color }">
          <el-icon><component :is="card.icon" /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </div>
      </el-card>
    </div>

    <!-- 生命周期分布（全宽） -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <span>生命周期分布（基于ROI）</span>
            <el-radio-group v-model="lifecycleDimension" size="small" style="float: right">
              <el-radio-button label="campaign">广告单元</el-radio-button>
              <el-radio-button label="product">商品</el-radio-button>
            </el-radio-group>
          </template>
          <el-row :gutter="20">
            <el-col :span="10">
              <div ref="lifecycleChart" class="chart-container lifecycle-chart"></div>
            </el-col>
            <el-col :span="14">
              <el-table :data="currentStageDefs" size="small" class="stage-table">
                <el-table-column width="12">
                  <template #default="{ row }">
                    <span class="color-dot" :style="{ background: row.color }"></span>
                  </template>
                </el-table-column>
                <el-table-column prop="name" label="阶段" width="90" />
                <el-table-column prop="pct" label="占比" width="70" align="right">
                  <template #default="{ row }">{{ row.pct }}%</template>
                </el-table-column>
                <el-table-column prop="desc" label="判定条件" min-width="200" />
              </el-table>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>ROI分布</span>
          </template>
          <div ref="roiChart" class="chart-container"></div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>策略触发排行</span>
          </template>
          <div ref="decisionChart" class="chart-container"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 效率趋势 + 策略摘要 -->
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <span>基建效率趋势（最近7天）</span>
          </template>
          <div ref="efficiencyChart" class="chart-container"></div>
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
              <span class="label">启用策略:</span>
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
            <div class="summary-item">
              <span class="label">跟投信号:</span>
              <span class="value">{{ strategyStats.followUpSignals }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { Goods, Promotion, Clock, Cpu, TrendCharts, Odometer } from '@element-plus/icons-vue'

const lifecycleDimension = ref('campaign')
const lifecycleChart = ref<HTMLElement>()
const roiChart = ref<HTMLElement>()
const decisionChart = ref<HTMLElement>()
const efficiencyChart = ref<HTMLElement>()

// 统计数据
const stats = reactive({
  totalProducts: 1147,
  activeCampaigns: 20000,
  profitabilityRate: 27,
  automationPlanCount: 68
})

// 策略统计
const strategyStats = reactive({
  totalRules: 11,
  enabledRules: 8,
  triggersToday: 12,
  decisionsThisWeek: 156,
  followUpSignals: 8,
  topStrategies: [
    { name: '饱和攻击-成长期Campaign', count: 20 },
    { name: '预算递增-成长期Campaign', count: 15 },
    { name: '基建补充-衰退期Campaign', count: 12 },
    { name: '复制广告-冷启动期', count: 8 },
    { name: '成长期-跟投', count: 8 },
    { name: '渠道扩张-持续盈利期', count: 6 },
    { name: '持续盈利-跟投', count: 5 },
    { name: '有序关停-关停期', count: 5 }
  ]
})

const statCards = computed(() => [
  { label: '总商品数', value: stats.totalProducts || 0, color: '#409eff', icon: Goods },
  { label: '活跃广告', value: stats.activeCampaigns || 0, color: '#67c23a', icon: Promotion },
  { label: '今日策略触发', value: strategyStats.triggersToday || 0, color: '#e6a23c', icon: Clock },
  { label: '盈利率', value: (stats.profitabilityRate || 0) + '%', color: '#f56c6c', icon: Cpu },
  { label: '自动化基建计划', value: stats.automationPlanCount || 0, color: '#909399', icon: TrendCharts },
  { label: '跟投信号', value: strategyStats.followUpSignals || 0, color: '#8e44ad', icon: Odometer },
])

// 生命周期数据（饼图用短名称）
const lifecycleData: Record<string, Record<string, { value: number; name: string }>> = {
  campaign: {
    'campaign_observing': { value: 0.12, name: '待观察' },
    'campaign_cold_dead': { value: 0.19, name: '冷死亡' },
    'campaign_cold_start': { value: 0.32, name: '冷启动' },
    'campaign_verify': { value: 0.16, name: '验证期' },
    'campaign_growth': { value: 0.06, name: '成长期' },
    'campaign_sustained': { value: 0.04, name: '持续盈利' },
    'campaign_decline': { value: 0.03, name: '衰退期' },
    'campaign_shutdown': { value: 0.08, name: '关停期' }
  },
  product: {
    'product_observing': { value: 0.15, name: '待观察' },
    'product_entry': { value: 0.12, name: '入场期' },
    'product_sustained': { value: 0.20, name: '稳定期' },
    'product_growth': { value: 0.10, name: '成长期' },
    'product_decline': { value: 0.18, name: '衰退期' },
    'product_exit': { value: 0.25, name: '退出期' },
  }
}

// 阶段定义（供下方参考表）
const stageDefs: Record<string, { name: string; desc: string; color: string }[]> = {
  campaign: [
    { name: '待观察', desc: '投放 < 24h，时间不足无法判断', color: '#909399' },
    { name: '冷死亡', desc: '投放 > 72h 且从未产生收入', color: '#909399' },
    { name: '冷启动', desc: '前24h ROI < 10%', color: '#f56c6c' },
    { name: '验证期', desc: '24-72h ROI 10-40%，关键决策点', color: '#e6a23c' },
    { name: '成长期', desc: 'ROI > 40%（含6h快速通道）', color: '#67c23a' },
    { name: '持续盈利', desc: 'ROI > 40% 超过7天', color: '#409eff' },
    { name: '衰退期', desc: 'ROI从高点下降 > 50%', color: '#ff6600' },
    { name: '关停期', desc: 'ROI < 10% 持续72h+', color: '#f56c6c' }
  ],
  product: [
    { name: '待观察', desc: '投放 < 3天，时间不足', color: '#909399' },
    { name: '入场期', desc: '近3天ROI均值 > 40%', color: '#67c23a' },
    { name: '稳定期', desc: '近5天ROI均在30-80%', color: '#409eff' },
    { name: '成长期', desc: 'ROI > 40% 且趋势上升', color: '#00d084' },
    { name: '衰退期', desc: 'ROI下滑 > 30%', color: '#ff6600' },
    { name: '退出期', desc: 'ROI < 10% 持续5天', color: '#f56c6c' },
  ]
}

// 当前维度下的阶段参考（含占比）
const currentStageDefs = computed(() => {
  const data = lifecycleData[lifecycleDimension.value]
  const defs = stageDefs[lifecycleDimension.value]
  return defs.map(d => {
    const entry = Object.values(data).find(v => v.name === d.name)
    return { ...d, pct: entry ? (entry.value * 100).toFixed(1) : '0.0' }
  })
})

// ROI分布数据
const roiDistributionData = [
  { range: 'ROI>40%', count: 5463, color: '#67c23a' },
  { range: 'ROI 20-40%', count: 3074, color: '#e6a23c' },
  { range: 'ROI 0-20%', count: 6423, color: '#f56c6c' },
  { range: 'ROI≤0', count: 5040, color: '#909399' }
]


function initLifecycleChart() {
  if (!lifecycleChart.value) return

  const chart = echarts.init(lifecycleChart.value)
  const data = lifecycleData[lifecycleDimension.value]

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => `${p.name}: ${p.value}% (${p.percent}%)`
    },
    legend: {
      top: 'bottom',
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { fontSize: 12 }
    },
    series: [
      {
        type: 'pie',
        radius: ['45%', '75%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          formatter: '{d}%',
          fontSize: 11
        },
        emphasis: {
          label: { fontSize: 16, fontWeight: 'bold' }
        },
        data: Object.entries(data).map(([key, val]) => {
          const def = stageDefs[lifecycleDimension.value].find(d => d.name === val.name)
          return {
            name: val.name,
            value: +(val.value * 100).toFixed(1),
            itemStyle: { color: def?.color }
          }
        })
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
      data: strategyStats.topStrategies.map(s => s.name),
      axisLabel: { rotate: 15, fontSize: 11 }
    },
    yAxis: { type: 'value', name: '触发次数' },
    series: [
      {
        type: 'bar',
        data: strategyStats.topStrategies.map(s => s.count),
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
  const autoPlanCounts = [8, 11, 14, 17, 15, 20, 22]

  const option = {
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['决策数', '自动化基建计划']
    },
    xAxis: { type: 'category', data: days },
    yAxis: [
      { type: 'value', name: '决策数', max: 50 },
      { type: 'value', name: '计划数', min: 0, max: 50 }
    ],
    series: [
      {
        name: '决策数',
        type: 'bar',
        data: decisions,
        itemStyle: { color: '#409eff' }
      },
      {
        name: '自动化基建计划',
        type: 'line',
        yAxisIndex: 1,
        data: autoPlanCounts,
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
.stat-row {
  display: flex;
  gap: 20px;
}

.stat-row > .stat-card {
  flex: 1;
  min-width: 0;
}

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

.lifecycle-chart {
  height: 320px;
}

.stage-table {
  margin-top: 10px;
}

.stage-table :deep(.el-table__row) {
  font-size: 13px;
}

.color-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  vertical-align: middle;
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
</style>
